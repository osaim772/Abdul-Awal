"""Personal SMS inbox. Run behind an HTTPS reverse proxy on loopback."""
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import sqlite3
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).parent
DATA = Path(os.environ.get('SMS_DATA_DIR', str(ROOT / 'data')))
DATA.mkdir(mode=0o700, parents=True, exist_ok=True)
DB = DATA / 'inbox.sqlite'
PASSWORD = os.environ.get('SMS_ADMIN_PASSWORD', '')
ORIGIN = os.environ.get('SMS_PUBLIC_ORIGIN', os.environ.get('RENDER_EXTERNAL_URL', '')).rstrip('/')
if len(PASSWORD) < 16:
    raise SystemExit('Set SMS_ADMIN_PASSWORD to a unique password of at least 16 characters.')
if not ORIGIN.startswith('https://'):
    raise SystemExit('Set SMS_PUBLIC_ORIGIN to the HTTPS address of your inbox.')
PASSWORD_SALT = secrets.token_bytes(32)
PASSWORD_HASH = hashlib.pbkdf2_hmac('sha256', PASSWORD.encode(), PASSWORD_SALT, 200_000)
del PASSWORD

def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()

def connect():
    conn = sqlite3.connect(DB, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

with connect() as c:
    c.executescript('''
    CREATE TABLE IF NOT EXISTS devices(id TEXT PRIMARY KEY, label TEXT NOT NULL, token TEXT UNIQUE NOT NULL);
    CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY, device TEXT NOT NULL, event TEXT NOT NULL,
      sender TEXT NOT NULL, body TEXT NOT NULL, received INTEGER NOT NULL, created INTEGER NOT NULL,
      UNIQUE(device,event));
    CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, expires INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS attempts(ip TEXT PRIMARY KEY, count INTEGER NOT NULL, reset INTEGER NOT NULL);
    DELETE FROM sessions;
    ''')
os.chmod(DB, 0o600)

class Handler(BaseHTTPRequestHandler):
    # SMS, passwords and bearer tokens must never appear in request logs.
    def log_message(self, *args):
        pass

    def reply(self, status, value=None, cookie=None, html=False):
        content = value.encode() if html else json.dumps(value or {}).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'text/html; charset=utf-8' if html else 'application/json')
        self.send_header('Content-Length', str(len(content)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        if cookie:
            self.send_header('Set-Cookie', cookie)
        self.end_headers()
        self.wfile.write(content)

    def owner(self):
        from http.cookies import SimpleCookie
        cookies = SimpleCookie()
        try:
            cookies.load(self.headers.get('Cookie', ''))
            token = cookies['session'].value
        except (KeyError, Exception):
            return False
        with connect() as c:
            return c.execute('SELECT 1 FROM sessions WHERE token=? AND expires>?', (digest(token), int(time.time()))).fetchone() is not None

    def do_GET(self):
        path = self.path.split('?')[0]
        if path in ('/', '/app.js', '/style.css', '/manifest.webmanifest', '/logo.png'):
            filename = {'/': 'index.html'}.get(path, path[1:])
            content = (ROOT / 'web' / filename).read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', {'/': 'text/html; charset=utf-8', '/app.js': 'text/javascript', '/style.css': 'text/css', '/manifest.webmanifest': 'application/manifest+json', '/logo.png': 'image/png'}[path])
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return
        if path != '/api/inbox':
            return self.reply(404)
        if not self.owner():
            return self.reply(401)
        with connect() as c:
            c.execute('DELETE FROM messages WHERE created<?', (int(time.time()) - 7*86400,))
            messages = [dict(r) for r in c.execute('SELECT m.*, d.label FROM messages m JOIN devices d ON d.id=m.device ORDER BY m.created DESC,m.id DESC LIMIT 200')]
            devices = [dict(r) for r in c.execute('SELECT id,label FROM devices')]
        self.reply(200, {'messages': messages, 'devices': devices})

    def do_POST(self):
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 32768:
                return self.reply(413)
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                return self.reply(400)
        except (ValueError, UnicodeError):
            return self.reply(400)
        path = self.path
        if path == '/api/messages':
            bearer = self.headers.get('Authorization', '')
            if not bearer.startswith('Bearer '):
                return self.reply(401)
            with connect() as c:
                device = c.execute('SELECT id FROM devices WHERE token=?', (digest(bearer[7:]),)).fetchone()
                if not device:
                    return self.reply(401)
                event, sender, body, received = [payload.get(k) for k in ('event', 'sender', 'body', 'received')]
                if not (isinstance(event,str) and 1 <= len(event) <= 100 and isinstance(sender,str) and len(sender) <= 200 and isinstance(body,str) and 1 <= len(body) <= 10000 and isinstance(received,int) and 0 < received < 4102444800):
                    return self.reply(400)
                c.execute('INSERT OR IGNORE INTO messages(device,event,sender,body,received,created) VALUES(?,?,?,?,?,?)', (device['id'],event,sender,body,received,int(time.time())))
                c.execute('DELETE FROM messages WHERE created<?', (int(time.time())-7*86400,))
            return self.reply(200, {'saved': True})
        # All browser writes, including login, require an exact same-origin header.
        if self.headers.get('Origin') != ORIGIN:
            return self.reply(403)
        if path == '/api/login':
            now = int(time.time())
            ip = self.client_address[0]
            with connect() as c:
                attempt = c.execute('SELECT * FROM attempts WHERE ip=?', (ip,)).fetchone()
                if attempt and attempt['reset'] > now and attempt['count'] >= 10:
                    return self.reply(429)
                candidate = payload.get('password', '')
                valid = isinstance(candidate, str) and hmac.compare_digest(hashlib.pbkdf2_hmac('sha256',candidate.encode(),PASSWORD_SALT,200_000),PASSWORD_HASH)
                if not valid:
                    count = attempt['count']+1 if attempt and attempt['reset']>now else 1
                    reset = attempt['reset'] if attempt and attempt['reset']>now else now+900
                    c.execute('INSERT OR REPLACE INTO attempts VALUES(?,?,?)', (ip,count,reset))
                    return self.reply(401)
                c.execute('DELETE FROM attempts WHERE ip=?', (ip,))
                token = secrets.token_urlsafe(32)
                c.execute('DELETE FROM sessions WHERE expires<=?', (now,))
                c.execute('INSERT INTO sessions VALUES(?,?)', (digest(token),now+3600))
            return self.reply(200, cookie=f'session={token}; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=3600')
        if not self.owner():
            return self.reply(401)
        if path == '/api/logout':
            # Expire every session: this is a single-owner app.
            with connect() as c:
                c.execute('DELETE FROM sessions')
            return self.reply(200,cookie='session=; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=0')
        if path == '/api/devices':
            label = payload.get('label')
            if not isinstance(label,str) or not 1 <= len(label.strip()) <= 80:
                return self.reply(400)
            token, device = secrets.token_urlsafe(32), secrets.token_hex(12)
            with connect() as c:
                c.execute('INSERT INTO devices VALUES(?,?,?)',(device,label.strip(),digest(token)))
            return self.reply(201, {'token':token,'id':device})
        if path == '/api/revoke':
            with connect() as c:
                c.execute('DELETE FROM messages WHERE device=?',(payload.get('id'),))
                c.execute('DELETE FROM devices WHERE id=?',(payload.get('id'),))
            return self.reply(200)
        if path == '/api/clear':
            with connect() as c:
                c.execute('DELETE FROM messages')
            return self.reply(200)
        self.reply(404)

if __name__ == '__main__':
    print('Personal inbox started. HTTPS reverse proxy required.')
    ThreadingHTTPServer((os.environ.get('SMS_BIND_HOST','127.0.0.1'),int(os.environ.get('PORT',os.environ.get('SMS_PORT','8080')))),Handler).serve_forever()
