"""Functional API checks; synthetic messages only, no real SMS or credentials."""
import http.client
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import unittest

class InboxTest(unittest.TestCase):
    def test_private_sms_workflow(self):
        with tempfile.TemporaryDirectory() as directory:
            with socket.socket() as s:
                s.bind(('127.0.0.1',0)); port=s.getsockname()[1]
            password=secrets.token_urlsafe(24)
            env={**os.environ,'SMS_ADMIN_PASSWORD':password,'SMS_PUBLIC_ORIGIN':'https://inbox.test','SMS_DATA_DIR':directory,'SMS_PORT':str(port)}
            proc=subprocess.Popen([sys.executable,str(Path(__file__).with_name('server.py'))],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
            try:
                for _ in range(50):
                    try:
                        with socket.create_connection(('127.0.0.1',port),timeout=.1): break
                    except OSError:
                        if proc.poll() is not None: self.fail('Server failed to start')
                        time.sleep(.05)
                def call(path,body=None,cookie='',token='',origin='https://inbox.test'):
                    conn=http.client.HTTPConnection('127.0.0.1',port,timeout=5)
                    headers={'Origin':origin,'Content-Type':'application/json'}
                    if cookie: headers['Cookie']=cookie
                    if token: headers['Authorization']='Bearer '+token
                    conn.request('POST' if body is not None else 'GET',path,json.dumps(body) if body is not None else None,headers)
                    result=conn.getresponse(); code=result.status; session=result.getheader('Set-Cookie'); data=result.read();conn.close()
                    return code,session,json.loads(data)
                self.assertEqual(call('/api/inbox')[0],401)
                self.assertEqual(call('/api/login',{'password':password},origin='https://attacker.test')[0],403)
                self.assertEqual(call('/api/login',{'password':'incorrect'})[0],401)
                code,cookie,_=call('/api/login',{'password':password});self.assertEqual(code,200)
                self.assertIn('HttpOnly',cookie);self.assertIn('Secure',cookie)
                cookie=cookie.split(';')[0]
                code,_,device=call('/api/devices',{'label':'My Android'},cookie);self.assertEqual(code,201)
                message={'event':'test-1','sender':'Test sender','body':'Synthetic OTP: 123456','received':int(time.time())}
                self.assertEqual(call('/api/messages',message,token='invalid')[0],401)
                self.assertEqual(call('/api/messages',message,token=device['token'])[0],200)
                self.assertEqual(call('/api/messages',message,token=device['token'])[0],200)
                _,_,inbox=call('/api/inbox',cookie=cookie)
                self.assertEqual(len(inbox['messages']),1)
                self.assertEqual(inbox['messages'][0]['body'],message['body'])
                self.assertEqual(inbox['messages'][0]['label'],'My Android')
                self.assertNotIn('token',inbox['devices'][0])
                self.assertEqual(call('/api/clear',{},cookie,origin='https://attacker.test')[0],403)
                self.assertEqual(call('/api/revoke',{'id':device['id']},cookie)[0],200)
                self.assertEqual(call('/api/messages',message,token=device['token'])[0],401)
                self.assertEqual(call('/api/inbox',cookie=cookie)[2]['messages'],[])
                self.assertEqual(call('/api/logout',{},cookie)[0],200)
                self.assertEqual(call('/api/inbox',cookie=cookie)[0],401)
            finally:
                proc.terminate();proc.wait(timeout=5);proc.stderr.close()

if __name__=='__main__': unittest.main()
