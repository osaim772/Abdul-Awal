const encoder = new TextEncoder();
const now = () => Math.floor(Date.now() / 1000);
const token = () => [...crypto.getRandomValues(new Uint8Array(32))].map(x=>x.toString(16).padStart(2,'0')).join('');
const digest = async value => [...new Uint8Array(await crypto.subtle.digest('SHA-256',encoder.encode(value)))].map(x=>x.toString(16).padStart(2,'0')).join('');
const passwordHash = async value => {
  const key = await crypto.subtle.importKey('raw',encoder.encode(value),'PBKDF2',false,['deriveBits']);
  return new Uint8Array(await crypto.subtle.deriveBits({name:'PBKDF2',hash:'SHA-256',salt:encoder.encode('osaim-private-inbox-v1'),iterations:100000},key,256));
};
async function matchPassword(candidate, expected) {
  const [a,b] = await Promise.all([passwordHash(candidate),passwordHash(expected)]);
  let mismatch = 0; for(let i=0;i<a.length;i++) mismatch |= a[i]^b[i];
  return mismatch===0;
}
const headers = {
  'Cache-Control':'no-store', 'X-Content-Type-Options':'nosniff', 'Referrer-Policy':'no-referrer',
  'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
};
const reply = (status,value={},cookie) => new Response(JSON.stringify(value),{status,headers:{...headers,'Content-Type':'application/json',...(cookie?{'Set-Cookie':cookie}:{})}});
async function owner(request,db) {
  const session = request.headers.get('Cookie')?.split(';').map(x=>x.trim()).find(x=>x.startsWith('session='))?.slice(8);
  if(!session) return false;
  return !!await db.prepare('SELECT 1 FROM sessions WHERE token=? AND expires>?').bind(await digest(session),now()).first();
}
async function handle(request,env) {
  const url = new URL(request.url), path = url.pathname, db=env.DB;
  if(!path.startsWith('/api/')) {
    // Assets are public; no SMS is embedded or cached here.
    if(request.method!=='GET'&&request.method!=='HEAD') return reply(405);
    if(!['/','/app.js','/style.css','/logo.png','/manifest.webmanifest'].includes(path)) return reply(404);
    const asset=await env.ASSETS.fetch(request);
    const result=new Response(asset.body,asset);
    for(const [k,v] of Object.entries(headers))result.headers.set(k,v);
    return result;
  }
  if(request.method==='GET') {
    if(path!=='/api/inbox') return reply(404);
    if(!await owner(request,db)) return reply(401);
    await db.prepare('DELETE FROM messages WHERE created<?').bind(now()-7*86400).run();
    const [messages,devices] = await Promise.all([
      db.prepare('SELECT m.*,d.label FROM messages m JOIN devices d ON d.id=m.device ORDER BY m.created DESC,m.id DESC LIMIT 200').all(),
      db.prepare('SELECT id,label FROM devices').all()
    ]);
    return reply(200,{messages:messages.results,devices:devices.results});
  }
  if(request.method!=='POST') return reply(405);
  const length=Number(request.headers.get('Content-Length')||0);
  if(length>32768) return reply(413);
  let payload;
  try {
    // Bound the stream as well as Content-Length (chunked uploads may omit it).
    const reader=request.body?.getReader(); if(!reader)return reply(400);
    let size=0;const chunks=[];
    while(true){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>32768){await reader.cancel();return reply(413)}chunks.push(value)}
    const bytes=new Uint8Array(size);let offset=0;for(const chunk of chunks){bytes.set(chunk,offset);offset+=chunk.length}
    payload=JSON.parse(new TextDecoder().decode(bytes));
    if(!payload||typeof payload!=='object'||Array.isArray(payload))return reply(400);
  } catch { return reply(400); }
  if(path==='/api/messages') {
    const bearer=request.headers.get('Authorization')||'';
    if(!bearer.startsWith('Bearer '))return reply(401);
    const device=await db.prepare('SELECT id FROM devices WHERE token=?').bind(await digest(bearer.slice(7))).first();
    if(!device)return reply(401);
    const {event,sender,body,received}=payload;
    if(!(typeof event==='string'&&event.length>=1&&event.length<=100&&typeof sender==='string'&&sender.length<=200&&typeof body==='string'&&body.length>=1&&body.length<=10000&&Number.isInteger(received)&&received>0&&received<4102444800))return reply(400);
    await db.batch([
      db.prepare('INSERT OR IGNORE INTO messages(device,event,sender,body,received,created) VALUES(?,?,?,?,?,?)').bind(device.id,event,sender,body,received,now()),
      db.prepare('DELETE FROM messages WHERE created<?').bind(now()-7*86400)
    ]);
    return reply(200,{saved:true});
  }
  // No arbitrary CORS and no browser mutation without same-origin intent.
  if(request.headers.get('Origin')!==url.origin)return reply(403);
  if(path==='/api/login') {
    if(typeof env.SMS_ADMIN_PASSWORD!=='string'||env.SMS_ADMIN_PASSWORD.length<16)return reply(503,{error:'Private inbox password not configured.'});
    const ip=request.headers.get('CF-Connecting-IP')||'unknown', timestamp=now();
    const attempt=await db.prepare('SELECT count,reset FROM attempts WHERE ip=?').bind(ip).first();
    if(attempt&&attempt.reset>timestamp&&attempt.count>=10)return reply(429);
    const valid=typeof payload.password==='string'&&payload.password.length<=1024&&await matchPassword(payload.password,env.SMS_ADMIN_PASSWORD);
    if(!valid){
      const count=attempt&&attempt.reset>timestamp?attempt.count+1:1;
      const reset=attempt&&attempt.reset>timestamp?attempt.reset:timestamp+900;
      await db.prepare('INSERT OR REPLACE INTO attempts VALUES(?,?,?)').bind(ip,count,reset).run();
      return reply(401);
    }
    const session=token();
    await db.batch([
      db.prepare('DELETE FROM attempts WHERE ip=? OR reset<=?').bind(ip,timestamp),
      db.prepare('DELETE FROM sessions WHERE expires<=?').bind(timestamp),
      db.prepare('INSERT INTO sessions VALUES(?,?)').bind(await digest(session),timestamp+3600)
    ]);
    return reply(200,{},`session=${session}; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=3600`);
  }
  if(!await owner(request,db))return reply(401);
  if(path==='/api/logout'){
    await db.prepare('DELETE FROM sessions').run();
    return reply(200,{},'session=; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=0');
  }
  if(path==='/api/devices'){
    if(typeof payload.label!=='string'||payload.label.trim().length<1||payload.label.trim().length>80)return reply(400);
    const key=token(),id=token();
    await db.prepare('INSERT INTO devices VALUES(?,?,?)').bind(id,payload.label.trim(),await digest(key)).run();
    return reply(201,{token:key,id});
  }
  if(path==='/api/revoke'){
    if(typeof payload.id!=='string')return reply(400);
    await db.batch([db.prepare('DELETE FROM messages WHERE device=?').bind(payload.id),db.prepare('DELETE FROM devices WHERE id=?').bind(payload.id)]);
    return reply(200);
  }
  if(path==='/api/clear'){await db.prepare('DELETE FROM messages').run();return reply(200)}
  return reply(404);
}
export default {
  async fetch(request,env){try{return await handle(request,env)}catch{return reply(500,{error:'Inbox temporarily unavailable.'})}},
  async scheduled(event,env){const timestamp=now();await env.DB.batch([
    env.DB.prepare('DELETE FROM messages WHERE created<?').bind(timestamp-7*86400),
    env.DB.prepare('DELETE FROM sessions WHERE expires<=?').bind(timestamp),
    env.DB.prepare('DELETE FROM attempts WHERE reset<=?').bind(timestamp)
  ])}
};
