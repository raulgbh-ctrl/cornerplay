"""Xbox sign-in inside Cornerplay (xboxauth.py): the backend's sign-in protocol, with a fake backend."""
import json
import sys
import threading

import pytest

from cornerplay import xboxauth as A

FAKE = r'''#!{py}
import json, sys
mode = "{mode}"
print("some log line", flush=True)
print("NEXUS_AUTH_V1 " + json.dumps({{"type": "ready", "version": 1}}), flush=True)
hello = json.loads(sys.stdin.readline())
assert hello == {{"type": "hello", "version": 1}}, hello
url = "https://evil.example/login" if mode == "evil" else "https://login.live.com/oauth20_authorize.srf?x=1"
print("NEXUS_AUTH_V1 " + json.dumps({{"type": "open", "session": 1, "url": url,
      "headers": {{"cxh-platform": "Desktop", "Hostapp": "x"}}}}), flush=True)
print("NEXUS_AUTH_V1 " + json.dumps({{"type": "context", "session": 1, "context": "ctx"}}), flush=True)
msg = json.loads(sys.stdin.readline())
if msg.get("type") == "closed":
    sys.exit(1)
assert msg == {{"type": "ipc", "session": 1, "payload": "token-ish"}}, msg
print("NEXUS_AUTH_V1 " + json.dumps({{"type": "close", "session": 1}}), flush=True)
sys.exit(0)
'''


def run(tmp_path, mode, page):
    exe = tmp_path / "xodus-cli"
    exe.write_text(FAKE.format(py=sys.executable, mode=mode))
    exe.chmod(0o755)
    seen, done = [], threading.Event()
    result = {}

    def on_open(session, url, headers):
        seen.append(("open", session, url, headers))

    def on_context(session, ctx):
        seen.append(("context", session, ctx))
        page(login, session)

    def on_done(ok, message):
        result.update(ok=ok, message=message)
        done.set()
    login = A.Login(str(exe), on_open, on_context, lambda s: seen.append(("close", s)), on_done)
    login.start()
    assert done.wait(20)
    return seen, result


def test_signs_in(tmp_path):
    seen, result = run(tmp_path, "ok", lambda login, s: login.notify(s, "token-ish"))
    assert result == {"ok": True, "message": ""}
    assert seen[0] == ("open", 1, "https://login.live.com/oauth20_authorize.srf?x=1",
                       {"cxh-platform": "Desktop", "hostapp": "x"})
    assert seen[1] == ("context", 1, "ctx") and seen[-1] == ("close", 1)


def test_closing_the_window_cancels(tmp_path):
    seen, result = run(tmp_path, "ok", lambda login, s: login.cancel(s))
    assert result["ok"] is False and "cancelled" in result["message"]


def test_only_microsoft_pages_open(tmp_path):
    seen, result = run(tmp_path, "evil", lambda login, s: None)
    assert not result["ok"] and not [x for x in seen if x[0] == "open"]


def test_frames_are_checked():
    assert A.parse("plain log") is None
    assert A.parse('NEXUS_AUTH_V1 {"type":"ready","version":1}') == {"type": "ready"}
    for bad in ('{"type":"open","session":1,"url":"http://login.live.com/","headers":{}}',
                '{"type":"open","session":1,"url":"https://login.live.com:444/","headers":{}}',
                '{"type":"open","session":1,"url":"https://login.live.com/","headers":{"cookie":"x"}}',
                '{"type":"open","session":0,"url":"https://login.live.com/","headers":{}}',
                '{"type":"context","session":1,"context":' + json.dumps("x" * 5000) + '}',
                'not json'):
        with pytest.raises(A.ProtocolError):
            A.parse("NEXUS_AUTH_V1 " + bad)
    assert A.trusted("https://sisu.xboxlive.com/connect") and not A.trusted("https://login.live.com.evil.io/")
    assert "CloudExperienceHost.Bridge.dispatchMessage" in A.context_script("c")
