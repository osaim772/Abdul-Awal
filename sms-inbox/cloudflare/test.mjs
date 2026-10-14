import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import {Miniflare} from 'miniflare';

const password=crypto.randomUUID()+crypto.randomUUID();
const mf=new Miniflare({
  modules:true,scriptPath:'worker.mjs',compatibilityDate:'2026-08-06',
  d1Databases:['DB'],bindings:{SMS_ADMIN_PASSWORD:password},
  serviceBindings:{ASSETS:async request=>{
    const path=new URL(request.url).pathname;const filename=path==='/'?'index.html':path.slice(1);
    try{return new Response(await fs.readFile('../web/'+filename))}catch{return new Response('Not found',{status:404})}
  }}
});
try{
  const db=await mf.getD1Database('DB');
  await db.exec((await fs.readFile('migrations/0001.sql','utf8')).replaceAll('\n',' '));
  const call=async(path,body,extra={})=>mf.dispatchFetch('https://inbox.test'+path,{
    method:body===undefined?'GET':'POST',headers:{Origin:'https://inbox.test','Content-Type':'application/json',...extra},
    ...(body===undefined?{}:{body:JSON.stringify(body)})
  });
  assert.equal((await call('/')).status,200);
  assert.equal((await call('/logo.png')).status,200);
  assert.equal((await call('/api/inbox')).status,401);
  assert.equal((await call('/api/login',{password},{Origin:'https://attacker.test'})).status,403);
  assert.equal((await call('/api/login',{password:'incorrect'})).status,401);
  const login=await call('/api/login',{password});assert.equal(login.status,200);
  const raw=login.headers.get('set-cookie');assert(raw.includes('Secure'));assert(raw.includes('HttpOnly'));
  const Cookie=raw.split(';')[0];
  const pair=await call('/api/devices',{label:'My SIM phone'},{Cookie});assert.equal(pair.status,201);
  const device=await pair.json(),Authorization='Bearer '+device.token;
  const message={event:'sms-1',sender:'Test sender',body:'Synthetic OTP 123456',received:Math.floor(Date.now()/1000)};
  assert.equal((await call('/api/messages',message,{Authorization:'Bearer bad'})).status,401);
  assert.equal((await call('/api/messages',message,{Authorization})).status,200);
  assert.equal((await call('/api/messages',message,{Authorization})).status,200);
  assert.equal((await call('/api/messages',{...message,received:'bad'},{Authorization})).status,400);
  assert.equal((await call('/api/messages',{...message,body:'x'.repeat(40000)},{Authorization})).status,413);
  let inbox=await (await call('/api/inbox',undefined,{Cookie})).json();
  assert.equal(inbox.messages.length,1);assert.equal(inbox.messages[0].body,message.body);
  assert.equal(inbox.messages[0].label,'My SIM phone');assert(!('token' in inbox.devices[0]));
  await db.prepare('UPDATE messages SET created=?').bind(message.received-8*86400).run();
  inbox=await (await call('/api/inbox',undefined,{Cookie})).json();assert.equal(inbox.messages.length,0);
  assert.equal((await call('/api/clear',{},{Cookie,Origin:'https://attacker.test'})).status,403);
  assert.equal((await call('/api/revoke',{id:device.id},{Cookie})).status,200);
  assert.equal((await call('/api/messages',message,{Authorization})).status,401);
  assert.equal((await call('/api/logout',{},{Cookie})).status,200);
  assert.equal((await call('/api/inbox',undefined,{Cookie})).status,401);
  for(let i=0;i<10;i++)assert.equal((await call('/api/login',{password:'wrong'})).status,401);
  assert.equal((await call('/api/login',{password})).status,429);
  console.log('Cloudflare Worker + real local D1: login, assets, SMS ingestion, duplicate protection, retention, revocation, logout, CSRF, payload bounds and rate limiting passed.');
}finally{await mf.dispose()}
