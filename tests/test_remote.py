import json
import urllib.request
from urllib.error import HTTPError

from cornerplay import remote


def _srv():
    got = {"keys": [], "text": [], "votes": {}}
    s = remote.Server({"key": got["keys"].append, "text": got["text"].append, "state": lambda: {"playing": "X"},
                       "night": lambda phone: {"open": True, "games": [], "mine": got["votes"].get(phone, "")},
                       "vote": lambda phone, key: got["votes"].__setitem__(phone, key) or True}, port=0)
    assert s.start() == ""
    return s, got, f"http://127.0.0.1:{s._httpd.server_address[1]}"


def _post(url, body, headers=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", **(headers or {})})
    return json.loads(urllib.request.urlopen(req, timeout=5).read())


def test_needs_the_code_then_presses_keys():
    s, got, base = _srv()
    try:
        page = urllib.request.urlopen(base + "/", timeout=5).read().decode()
        assert "Type the code" in page  # the login page, not the remote
        try:
            _post(base + "/key", {"k": "a"})
            assert False, "a key without the code went through"
        except HTTPError as e:
            assert e.code == 403
        assert _post(base + f"/key?c={s.code}", {"k": "a"})["ok"]
        assert _post(base + f"/text?c={s.code}", {"t": "hol"})["ok"]
        assert got["keys"] == ["a"] and got["text"] == ["hol"]
        cookie = {"Cookie": f"cp={s.code}"}
        assert _post(base + "/vote", {"key": "steam:1"}, cookie)["ok"]
        # A page on another site cannot drive it through the phone's browser.
        try:
            _post(base + "/key", {"k": "b"}, dict(cookie, Origin="http://evil.example"))
            assert False
        except HTTPError as e:
            assert e.code == 403
        assert got["keys"] == ["a"]
    finally:
        s.stop()


def test_locks_out_after_ten_wrong_codes():
    s, got, base = _srv()
    try:
        for _ in range(10):
            urllib.request.urlopen(base + "/?c=000000x", timeout=5).read()
        try:
            _post(base + f"/key?c={s.code}", {"k": "a"})
            assert False
        except HTTPError as e:
            assert e.code == 403
    finally:
        s.stop()


def test_keys_from_the_phone_reach_the_window():
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QGuiApplication, QWindow
    from cornerplay.app import AioLaunch as App
    qapp = QGuiApplication.instance() or QGuiApplication([])
    got = []

    class W(QWindow):
        def keyPressEvent(self, e):
            got.append((e.key(), e.text(), bool(e.modifiers() & Qt.ShiftModifier)))
    w = W()
    w.show()
    w.requestActivate()
    fake = type("F", (), {"PAD_KEYS": App.PAD_KEYS, "_post_key": App._post_key})()
    App._inject_key(fake, "a")
    App._inject_key(fake, "rt")
    App._inject_text(fake, "hi\b")
    qapp.processEvents()
    assert got == [(Qt.Key_Return, "", False), (Qt.Key_Right, "", True), (Qt.Key_H, "h", False),
                   (Qt.Key_I, "i", False), (Qt.Key_Backspace, "", False)]


def test_web_library_lists_and_acts():
    from cornerplay import webui
    did = []
    r = webui.routes(lambda: {"games": [{"key": "gog:1", "title": "A"}], "downloads": []},
                     lambda what, key: did.append((what, key)) or "")
    status, ctype, body = r["/web/api/games"]("GET", {}, {})
    assert status == 200 and json.loads(body)["games"][0]["key"] == "gog:1"
    assert r["/web/api/act"]("POST", {}, {"action": "install", "key": "gog:1"})[0] == 200
    assert r["/web/api/act"]("POST", {}, {"action": "uninstall", "key": "gog:1"})[0] == 400  # not offered on the web
    assert r["/web/api/act"]("GET", {}, {})[0] == 405
    assert did == [("install", "gog:1")]
