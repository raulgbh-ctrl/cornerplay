"""Signing in to Xbox inside Cornerplay (Linux), with no Nexus Launcher window.

The Xbox backend (xodus-cli, see xodus.py) does the Microsoft sign-in itself and keeps the account
in the system keyring; all it needs is a web window to show Microsoft's pages in. With
`--external-webview-stdio login` it asks for one over its stdin/stdout, one JSON line per message
(Nexus Launcher's "external sign-in UI protocol", version 1, ported from its source):

    backend -> us   NEXUS_AUTH_V1 {"type": "ready", "version": 1}
    us -> backend   {"type": "hello", "version": 1}
    backend -> us   NEXUS_AUTH_V1 {"type": "open", "session": n, "url": ..., "headers": {...}}
                    NEXUS_AUTH_V1 {"type": "context", "session": n, "context": ...}
                    NEXUS_AUTH_V1 {"type": "close", "session": n}
    us -> backend   {"type": "ipc", "session": n, "payload": ...}   (the page's external.notify)
                    {"type": "closed", "session": n}                (the person closed the window)

The backend exits 0 once signed in. Only Microsoft's sign-in hosts are ever opened, with only the
headers Microsoft's sign-in host app sends (the same checks Nexus makes). Nothing here sees a
password or a token: they stay between the page and the backend.
"""
import json
import subprocess
import threading
from urllib.parse import urlsplit

PREFIX = "NEXUS_AUTH_V1 "
FRAME_LIMIT = 128 * 1024
HOSTS = ("login.live.com", "account.live.com", "login.microsoftonline.com", "login.microsoft.com",
         "account.microsoft.com", "sisu.xboxlive.com")
HEADERS = {"cxh-capabilities", "cxh-correlationid", "cxh-msabinaryversion", "cxh-identityclientbinaryversion",
           "cxh-osversioninfo", "cxh-platform", "cxh-protocol", "cxh-source", "hostapp"}
# Microsoft's sign-in pages behave as in Windows' own sign-in host with this browser name.
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64; MSAppHost/3.0) AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/70.0.3538.102 Safari/537.36 Edge/18.26100")
TIMEOUT = 600  # seconds for the whole sign-in


def trusted(url: str) -> bool:
    """A Microsoft sign-in page: https, no port, no user name, one of HOSTS."""
    try:
        u = urlsplit(url)
        return u.scheme == "https" and not u.username and not u.password and u.port is None and u.hostname in HOSTS
    except ValueError:
        return False


def context_script(context: str) -> str:
    """The JavaScript that hands the backend's context to the page (Windows' sign-in host does this)."""
    message = json.dumps({"type": "callback", "value": {
        "name": "CloudExperienceHost.getContext",
        "args": ["CloudExperienceHost", "TokenBroker", "TokenBroker",
                 '{"PrivatePropertyBag":1,"PasswordlessConnect":1,"PreferAssociate":1,"ChromelessUI":0}'],
        "context": context}})
    return f'globalThis["CloudExperienceHost.Bridge.dispatchMessage"]({json.dumps(message)})'


class ProtocolError(Exception):
    pass


def parse(line: str):
    """One backend line as a frame dict, None for a line that is not a frame (log output)."""
    if not line.startswith(PREFIX):
        return None
    if len(line.encode()) > FRAME_LIMIT:
        raise ProtocolError("Sign-in response exceeds the protocol limit")
    try:
        f = json.loads(line[len(PREFIX):])
    except ValueError:
        raise ProtocolError("Invalid sign-in protocol response") from None
    if not isinstance(f, dict):
        raise ProtocolError("Invalid sign-in protocol response")
    kind = f.get("type")
    if kind == "ready" and f.get("version") == 1:
        return {"type": "ready"}
    session = f.get("session")
    if not isinstance(session, int) or isinstance(session, bool) or session < 1:
        raise ProtocolError("Invalid sign-in session")
    if kind == "close":
        return {"type": "close", "session": session}
    if kind == "context" and isinstance(f.get("context"), str) and len(f["context"]) <= 4096:
        return {"type": "context", "session": session, "context": f["context"]}
    if (kind == "open" and isinstance(f.get("url"), str) and len(f["url"]) <= 32768 and trusted(f["url"])
            and isinstance(f.get("headers"), dict)):
        headers = {}
        if len(f["headers"]) > len(HEADERS):
            raise ProtocolError("Invalid sign-in request headers")
        for name, value in f["headers"].items():
            low = str(name).lower()
            if (low not in HEADERS or not isinstance(value, str) or len(value) > 4096 or low in headers
                    or any(not (0x20 <= ord(c) <= 0x7e) for c in value)):
                raise ProtocolError("Invalid sign-in request headers")
            headers[low] = value
        return {"type": "open", "session": session, "url": f["url"], "headers": headers}
    raise ProtocolError("Unsupported sign-in protocol response")


class Login:
    """One sign-in. The callbacks run on a reader thread: hand them to the UI thread.

    on_open(session, url, headers)  show this page (a new window for each session)
    on_context(session, context)    run context_script(context) in the page
    on_close(session)               the page is done with: hide it
    on_done(ok, message)            finished (ok), cancelled or failed (message says why)
    """

    def __init__(self, exe, on_open, on_context, on_close, on_done, player=False):
        self.exe, self.player = exe, player
        self.on_open, self.on_context, self.on_close, self.on_done = on_open, on_context, on_close, on_done
        self.proc = None
        self.ready = False
        self.active = None
        self.latest = 0
        self.cancelled = False
        self.failure = ""
        self._lock = threading.Lock()

    # --- to the backend --------------------------------------------------------------------------
    def _write(self, event: dict):
        with self._lock:
            p = self.proc
            if not p or p.poll() is not None or not p.stdin:
                return
            try:
                p.stdin.write(json.dumps(event) + "\n")
                p.stdin.flush()
            except (OSError, ValueError):
                pass

    def notify(self, session: int, payload: str):
        """What the page passed to external.notify (or its ServerData), for the backend."""
        if session == self.active and isinstance(payload, str) and len(payload.encode()) <= FRAME_LIMIT // 2:
            self._write({"type": "ipc", "session": session, "payload": payload})

    def cancel(self, session: int = 0):
        """The person closed the sign-in window."""
        if session and session != self.active:
            return
        self.cancelled = True
        if self.active:
            self._write({"type": "closed", "session": self.active})
        self._terminate()

    def fail(self, message: str):
        if not self.failure:
            self.failure = message
        self._terminate()

    def _terminate(self):
        p = self.proc
        if p and p.poll() is None:
            p.terminate()
            threading.Timer(1.5, lambda: p.poll() is None and p.kill()).start()

    # --- from the backend ------------------------------------------------------------------------
    def start(self):
        env = {**__import__("os").environ, "XODUS_LOG": "off", "RUST_LOG": "off"}
        args = [self.exe, "--external-webview-stdio", "login"] + (["--player"] if self.player else [])
        self.proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     text=True, encoding="utf-8", errors="replace", env=env, bufsize=1)
        threading.Thread(target=self._read, daemon=True).start()
        threading.Thread(target=self._stderr, daemon=True).start()
        threading.Timer(TIMEOUT, lambda: self.proc.poll() is None and self.fail("Sign-in timed out")).start()

    def _stderr(self):
        self.err = []
        for line in self.proc.stderr:
            if len(self.err) < 200:
                self.err.append(line.rstrip())

    def _read(self):
        total = 0
        try:
            for raw in self.proc.stdout:
                total += len(raw)
                if total > 2 * 1024 * 1024:
                    self.fail("Sign-in backend exceeded the output limit")
                    break
                if self.failure or self.cancelled:
                    continue
                self._frame(parse(raw.rstrip("\r\n")))
        except ProtocolError as e:
            self.fail(str(e))
        code = self.proc.wait()
        if self.active:
            self.on_close(self.active)
            self.active = None
        if self.cancelled:
            self.on_done(False, "Sign-in cancelled")
        elif self.failure:
            self.on_done(False, self.failure)
        elif code == 0 and self.ready and self.latest:
            self.on_done(True, "")
        else:
            why = next((l for l in reversed(getattr(self, "err", [])) if l.strip()), "")
            self.on_done(False, f"Sign-in did not finish{': ' + why[:200] if why else ''}")

    def _frame(self, f):
        if not f:
            return
        if f["type"] == "ready":
            if self.ready:
                raise ProtocolError("Duplicate sign-in handshake")
            self.ready = True
            self._write({"type": "hello", "version": 1})
            return
        if not self.ready:
            raise ProtocolError("Missing sign-in protocol handshake")
        if f["type"] == "open":
            if f["session"] <= self.latest or self.latest >= 32:
                raise ProtocolError("Invalid sign-in session order")
            self.active = self.latest = f["session"]
            self.on_open(f["session"], f["url"], f["headers"])
        elif f["session"] != self.active:
            raise ProtocolError("Unexpected sign-in session")
        elif f["type"] == "context":
            self.on_context(f["session"], f["context"])
        else:
            self.active = None
            self.on_close(f["session"])
