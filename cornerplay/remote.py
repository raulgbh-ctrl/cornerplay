"""Cornerplay from a phone: a small web server on your home network (off until Settings > TV
mode > Phone remote is on).

The phone opens http://<this PC>:47110/ (a QR code on the TV has the address and the code),
types the 6-digit code once (it is kept in a cookie), and gets:
  - a remote: d-pad, A / B / X / Y, Guide, quick access, LB / RB, and a box that types
    (searching from the sofa without the on-screen keyboard)
  - game night: the games up for tonight, one vote per phone
  - the web library (webui.py adds its pages): browse, queue installs, see downloads

Nothing is reachable without the code; a new code is made each time the server starts, and
after 10 wrong codes from one address it stops answering that address. Plain HTTP on the
local network only (the code travels in the clear, like a TV's own remote apps).

The server runs in its own thread; every action goes to the UI thread through `post`.
"""
import json
import secrets
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

PORT = 47110
KEYS = ("up", "down", "left", "right", "a", "b", "x", "y", "view", "guide", "qa", "lb", "rb", "lt", "rt")


def lan_ip() -> str:
    """This PC's address on the home network (the one a phone can reach)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))  # no packet is sent: this only picks the outgoing interface
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


class Server:
    """handlers: {"key": fn(name), "text": fn(str), "state": fn() -> dict,
    "night": fn(phone_id) -> dict, "vote": fn(phone_id, key) -> bool, "routes": {path: fn(method, query, body) -> (status, type, bytes)}}"""

    def __init__(self, handlers, port=PORT):
        self.handlers = handlers
        self.port = port
        self.code = f"{secrets.randbelow(10 ** 6):06d}"
        self._fails = {}
        self._httpd = None
        self._thread = None

    @property
    def url(self):
        return f"http://{lan_ip()}:{self.port}/"

    def start(self) -> str:
        """Start listening. "" or why it could not."""
        if self._httpd:
            return ""
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):  # quiet
                pass

            def _send(self, status, ctype, body, headers=()):
                self.send_response(status)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Referrer-Policy", "no-referrer")
                # Never inside another site's frame (a page could trick taps onto the remote), and the
                # pages talk only to this server; covers may come from the stores' image servers.
                self.send_header("X-Frame-Options", "DENY")
                self.send_header("Content-Security-Policy",
                                 "default-src 'self'; img-src 'self' https: data:; style-src 'self' 'unsafe-inline'; "
                                 "script-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; "
                                 "form-action 'self'; base-uri 'none'")
                for k, v in headers:
                    self.send_header(k, v)
                self.end_headers()
                if self.command != "HEAD":
                    self.wfile.write(body)

            def _json(self, obj, status=200, headers=()):
                self._send(status, "application/json", json.dumps(obj).encode(), headers)

            def _code_ok(self, query):
                ip = self.client_address[0]
                if server._fails.get(ip, 0) >= 10:
                    return False
                given = ""
                for part in (self.headers.get("Cookie") or "").split(";"):
                    k, _, v = part.strip().partition("=")
                    if k == "cp":
                        given = v
                given = (query.get("c") or [given])[0]
                if given and secrets.compare_digest(given, server.code):
                    return True
                if given:
                    server._fails[ip] = server._fails.get(ip, 0) + 1
                return False

            def _phone(self):
                """One vote per phone: its address and browser."""
                return self.client_address[0] + "|" + (self.headers.get("User-Agent") or "")[:80]

            def _body(self):
                n = min(int(self.headers.get("Content-Length") or 0), 64 * 1024)
                raw = self.rfile.read(n) if n else b""
                try:
                    return json.loads(raw or b"{}")
                except ValueError:
                    return {}

            def do_HEAD(self):
                self.do_GET()

            def do_GET(self):
                u = urlparse(self.path)
                q = parse_qs(u.query)
                if not self._code_ok(q):
                    return self._send(200, "text/html; charset=utf-8", LOGIN.encode())
                cookie = [("Set-Cookie", f"cp={server.code}; Path=/; SameSite=Strict; Max-Age=2592000")] if q.get("c") else []
                if u.path == "/":
                    return self._send(200, "text/html; charset=utf-8", PAGE.encode(), cookie)
                if u.path == "/state":
                    return self._json(server.handlers["state"]())
                if u.path == "/night":
                    return self._json(server.handlers["night"](self._phone()))
                route = server.handlers.get("routes", {}).get(u.path)
                if route:
                    status, ctype, body = route("GET", q, {})
                    return self._send(status, ctype, body, cookie)
                self._send(404, "text/plain", b"not found")

            def do_POST(self):
                u = urlparse(self.path)
                q = parse_qs(u.query)
                if not self._code_ok(q):
                    return self._json({"ok": False, "error": "code"}, 403)
                # Only from this page: a page elsewhere cannot make the phone's browser press keys.
                origin = self.headers.get("Origin")
                if origin and urlparse(origin).netloc != self.headers.get("Host"):
                    return self._json({"ok": False}, 403)
                body = self._body()
                if u.path == "/key" and body.get("k") in KEYS:
                    server.handlers["key"](body["k"])
                    return self._json({"ok": True})
                if u.path == "/text" and isinstance(body.get("t"), str):
                    server.handlers["text"](body["t"][:200])
                    return self._json({"ok": True})
                if u.path == "/vote" and isinstance(body.get("key"), str):
                    return self._json({"ok": bool(server.handlers["vote"](self._phone(), body["key"]))})
                route = server.handlers.get("routes", {}).get(u.path)
                if route:
                    status, ctype, out = route("POST", q, body)
                    return self._send(status, ctype, out)
                self._json({"ok": False}, 404)

        try:
            self._httpd = ThreadingHTTPServer(("0.0.0.0", self.port), Handler)
        except OSError as e:
            self._httpd = None
            return f"Port {self.port} is busy ({e.strerror})"
        self._httpd.daemon_threads = True
        self._thread = threading.Thread(target=self._httpd.serve_forever, name="cornerplay-remote", daemon=True)
        self._thread.start()
        return ""

    def stop(self):
        if self._httpd:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None


def qr_svg(text: str) -> str:
    """A QR code as SVG, through the qrencode tool when it is there ("" without it)."""
    import shutil
    import subprocess
    if not shutil.which("qrencode"):
        return ""
    try:
        r = subprocess.run(["qrencode", "-t", "SVG", "-m", "2", "-o", "-", text], capture_output=True, text=True, timeout=5)
        return r.stdout if r.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


LOGIN = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Cornerplay</title><style>
body{margin:0;font:18px system-ui,sans-serif;background:#16141a;color:#eee;display:grid;place-items:center;min-height:100vh}
form{display:grid;gap:14px;padding:24px;max-width:320px;text-align:center}
input{font-size:32px;letter-spacing:8px;text-align:center;padding:12px;border-radius:14px;border:1px solid #444;background:#222;color:#fff}
button{font-size:20px;padding:14px;border-radius:14px;border:0;background:#f0a868;color:#1b1b1f;font-weight:700}
</style></head><body><form method="get" action="/"><h2>Cornerplay</h2>
<div>Type the code shown on the TV (Guide menu &rsaquo; Phone remote).</div>
<input name="c" inputmode="numeric" autocomplete="one-time-code" maxlength="6" autofocus>
<button>Connect</button></form></body></html>"""

PAGE = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>Cornerplay remote</title><style>
:root{--bg:#16141a;--fg:#f2eee8;--muted:#a59f99;--card:#24212a;--accent:#f0a868;--on:#1b1b1f}
@media (prefers-color-scheme: light){:root{--bg:#f6f2ec;--fg:#1d1b20;--muted:#625d58;--card:#fff;--on:#1b1b1f}}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
body{margin:0;font:16px system-ui,sans-serif;background:var(--bg);color:var(--fg);padding:16px;max-width:520px;margin:auto}
h1{font-size:20px;margin:4px 0 2px}#now{color:var(--muted);min-height:20px;margin-bottom:12px}
nav{display:flex;gap:8px;margin-bottom:14px}nav button{flex:1;padding:10px;border-radius:12px;border:0;background:var(--card);color:var(--fg);font-weight:600}
nav button.on{background:var(--accent);color:var(--on)}
.pad{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;max-width:300px;margin:8px auto 18px}
button.k{aspect-ratio:1;border-radius:20px;border:0;background:var(--card);color:var(--fg);font-size:26px;font-weight:700;touch-action:manipulation}
button.k:active{transform:scale(.94);background:var(--accent);color:var(--on)}
.row{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:10px}.row button.k{aspect-ratio:auto;padding:16px 0;font-size:17px}
.a{color:#7bd88f!important}.b{color:#ff8a80!important}.x{color:#82b1ff!important}.y{color:#ffd54f!important}
input{width:100%;font-size:18px;padding:14px;border-radius:14px;border:1px solid #555;background:var(--card);color:var(--fg)}
.g{display:flex;align-items:center;gap:12px;background:var(--card);border-radius:14px;padding:10px;margin-bottom:10px}
.g img{width:48px;height:70px;object-fit:cover;border-radius:8px;background:#333}.g b{flex:1}.g button{padding:10px 14px;border-radius:12px;border:0;background:var(--accent);color:var(--on);font-weight:700}
.g .n{min-width:36px;text-align:center;font-size:20px;font-weight:800}
section{display:none}section.on{display:block}
</style></head><body>
<h1>Cornerplay</h1><div id="now"></div>
<nav><button data-t="remote" class="on">Remote</button><button data-t="night">Game night</button><button data-t="lib" onclick="location.href='/web'">Library</button></nav>
<section id="remote" class="on">
<div class="row"><button class="k" data-k="lb">LB</button><button class="k" data-k="view">View</button><button class="k" data-k="guide">Guide</button><button class="k" data-k="rb">RB</button></div>
<div class="pad"><span></span><button class="k" data-k="up">&#9650;</button><span></span>
<button class="k" data-k="left">&#9664;</button><button class="k a" data-k="a">A</button><button class="k" data-k="right">&#9654;</button>
<span></span><button class="k" data-k="down">&#9660;</button><span></span></div>
<div class="row"><button class="k x" data-k="x">X</button><button class="k y" data-k="y">Y</button><button class="k b" data-k="b">B</button><button class="k" data-k="qa">&#8943;</button></div>
<input id="type" placeholder="Type to search…" autocomplete="off" autocapitalize="off">
</section>
<section id="night"><div id="nightlist"></div></section>
<script>
const post=(p,b)=>fetch(p,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)});
document.querySelectorAll('button.k').forEach(b=>b.addEventListener('click',()=>{post('/key',{k:b.dataset.k});navigator.vibrate&&navigator.vibrate(12)}));
let last='';const t=document.getElementById('type');
t.addEventListener('input',()=>{const v=t.value;if(v.startsWith(last)){const add=v.slice(last.length);if(add)post('/text',{t:add})}else{post('/text',{t:'\\b'.repeat(Math.max(0,last.length-v.length))})}last=v});
t.addEventListener('keydown',e=>{if(e.key==='Enter'){post('/key',{k:'a'});t.blur()}});
document.querySelectorAll('nav button[data-t]').forEach(b=>b.addEventListener('click',()=>{if(b.dataset.t==='lib')return;
document.querySelectorAll('nav button,section').forEach(x=>x.classList.remove('on'));b.classList.add('on');document.getElementById(b.dataset.t).classList.add('on');night()}));
async function state(){try{const s=await (await fetch('/state')).json();document.getElementById('now').textContent=s.playing?('Playing '+s.playing):(s.focus?('On '+s.focus):'')}catch(e){}}
function esc(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
async function night(){try{const n=await (await fetch('/night')).json();const el=document.getElementById('nightlist');
if(!n.open){el.innerHTML='<p>No game night right now. Start one on the TV: Guide menu &rsaquo; Game night.</p>';return}
el.innerHTML=n.games.map(g=>'<div class="g"><img src="'+esc(g.cover||'')+'" alt=""><b>'+esc(g.title)+'</b><span class="n">'+g.votes+'</span><button data-v="'+esc(g.key)+'">'+(n.mine===g.key?'Voted':'Vote')+'</button></div>').join('');
el.querySelectorAll('button[data-v]').forEach(b=>b.addEventListener('click',async()=>{await post('/vote',{key:b.dataset.v});night()}))}catch(e){}}
state();setInterval(state,4000);setInterval(()=>{if(document.getElementById('night').classList.contains('on'))night()},2500);
</script></body></html>"""

