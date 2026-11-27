"""Store sign-ins kept fresh (keepalive.py) and Play on TV (stream.ensure_game)."""
import json
import subprocess

from cornerplay import keepalive, stream


class FakeStore:
    def __init__(self, signed=True, problem=""):
        self.signed, self._problem = signed, problem

    def logged_in(self):
        return self.signed

    def problem(self):
        return self._problem

    def tool(self):
        return "tool"


def _run(out, code=0):
    return lambda argv, timeout=0, env=None: subprocess.CompletedProcess(argv, code, out, "")


def test_epic_ok_and_expired(monkeypatch):
    from cornerplay.stores import base
    monkeypatch.setattr(base, "run", _run('[Core] INFO: ...\n{"account": "Me", "games_available": 3}'))
    assert keepalive.refresh("epic", FakeStore()) == keepalive.OK
    monkeypatch.setattr(base, "run", _run('{"account": "<not logged in>"}'))
    assert keepalive.refresh("epic", FakeStore()) == keepalive.EXPIRED
    monkeypatch.setattr(base, "run", _run("network unreachable", 1))
    assert keepalive.refresh("epic", FakeStore()) == keepalive.OFFLINE
    assert keepalive.refresh("epic", FakeStore(signed=False)) == keepalive.SKIPPED
    assert keepalive.refresh("epic", FakeStore(problem="legendary not found")) == keepalive.SKIPPED


def test_amazon_and_gog(monkeypatch):
    from cornerplay.runner import StoreError
    from cornerplay.stores import base
    monkeypatch.setattr(base, "run", _run('{"Username": "x", "LoggedIn": true}'))
    assert keepalive.refresh("amazon", FakeStore()) == keepalive.OK
    monkeypatch.setattr(base, "run", _run('{"LoggedIn": false}'))
    assert keepalive.refresh("amazon", FakeStore()) == keepalive.EXPIRED
    gog = FakeStore()
    gog._token = lambda: "tok"
    assert keepalive.refresh("gog", gog) == keepalive.OK

    def gone():
        raise StoreError("GOG session expired, sign in again")
    gog._token = gone
    assert keepalive.refresh("gog", gog) == keepalive.EXPIRED
    assert keepalive.refresh("battlenet", FakeStore()) == keepalive.SKIPPED


def test_expired_told_once_until_it_works_again():
    seen = keepalive.Seen()
    assert seen.news({"epic": "expired", "gog": "ok"}) == ["epic"]
    assert seen.news({"epic": "expired"}) == []
    assert seen.news({"epic": "ok"}) == [] and seen.news({"epic": "expired"}) == ["epic"]


def test_ensure_game_keeps_the_rest_of_sunshines_list(monkeypatch):
    files = {"apps.json": json.dumps({"apps": [{"name": "Desktop", "cmd": ""}]})}
    monkeypatch.setattr(stream, "WINDOWS", False)
    monkeypatch.setattr(stream, "_read", lambda name="apps.json": files.get(name))
    monkeypatch.setattr(stream, "_write", lambda text, name="apps.json": files.__setitem__(name, text))
    monkeypatch.setattr(stream, "sunshine_kind", lambda: "native")
    monkeypatch.setattr(stream, "sunshine_running", lambda: False)
    monkeypatch.setattr(stream, "_launcher", lambda kind="": ["/usr/bin/cornerplay"])
    game = {"key": "gog:1", "title": "Witcher 3"}
    assert stream.ensure_game(game) == "file"
    assert stream.ensure_game(game) == "file"  # twice: still one entry
    apps = json.loads(files["apps.json"])["apps"]
    assert [a["name"] for a in apps] == ["Desktop", "Witcher 3"]
    assert apps[1]["cmd"] == "/usr/bin/cornerplay --play gog:1" and apps[1]["prep-cmd"]


def test_ensure_game_through_the_api(monkeypatch):
    calls = []

    def api(method, path, body=None, login=None, **kw):
        calls.append((method, path, body))
        return {"apps": [{"name": "Other", "cmd": "x"}]} if method == "GET" else {}
    monkeypatch.setattr(stream, "api", api)
    monkeypatch.setattr(stream, "sunshine_kind", lambda: "windows")
    monkeypatch.setattr(stream, "WINDOWS", True)
    monkeypatch.setattr(stream, "_launcher", lambda kind="": [r"C:\Program Files\Cornerplay\Cornerplay.exe"])
    assert stream.ensure_game({"key": "steam:620", "title": "Portal 2"}, {"username": "u", "password": "p"}) == "api"
    post = calls[-1]
    assert post[:2] == ("POST", "/api/apps") and post[2]["index"] == -1
    assert post[2]["cmd"] == '"C:\\Program Files\\Cornerplay\\Cornerplay.exe" --play steam:620'
    assert "prep-cmd" not in post[2]  # Windows leaves its display alone
