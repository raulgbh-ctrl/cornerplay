"""Battle.net: product.db states, the registered uninstaller, following the game's own process."""
import struct
import subprocess
import time
import types

from cornerplay.stores import battlenet as B


def _v(n):
    out = b""
    while True:
        b, n = n & 0x7F, n >> 7
        out += bytes([b | (0x80 if n else 0)])
        if not n:
            return out


def _f(num, val):
    if isinstance(val, bool) or isinstance(val, int):
        return _v(num << 3) + _v(int(val))
    if isinstance(val, float):
        return _v(num << 3 | 1) + struct.pack("<d", val)
    val = val.encode() if isinstance(val, str) else val
    return _v(num << 3 | 2) + _v(len(val)) + val


def _product(uid, code, path, installed, playable, done, progress, version="1.0"):
    base = _f(1, installed) + _f(2, playable) + _f(3, done) + _f(7, version)
    state = _f(1, base) + _f(4, _f(2, progress))
    return _f(1, _f(1, uid) + _f(2, code) + _f(3, _f(1, path)) + _f(4, state))


def test_product_states(tmp_path):
    db = tmp_path / "product.db"
    db.write_bytes(_product("pro", "Pro", "C:/Program Files (x86)/Overwatch", True, True, True, 1.0, "2.15")
                   + _product("fenris", "Fen", "C:/Program Files (x86)/Diablo IV", False, False, False, 0.42)
                   + _product("wow", "WoW", "C:/Program Files (x86)/World of Warcraft", True, True, False, 0.5))
    got = {p["uid"]: p for p in B.products(str(db))}
    assert got["pro"]["playable"] and got["pro"]["busy"] is None and got["pro"]["version"] == "2.15"
    assert not got["fenris"]["playable"] and got["fenris"]["busy"] == {"kind": "install", "progress": 42.0}
    assert got["wow"]["playable"] and got["wow"]["busy"] == {"kind": "update", "progress": 50.0}
    assert B.read_product_db(str(db))[0] == ("pro", "Pro", "C:/Program Files (x86)/Overwatch")


def test_uid_for_game_page_and_moved_titles(tmp_path, monkeypatch):
    assert B.UID_BY_LAUNCH["fen"] == "fenris" and B.UID_BY_LAUNCH["wtcg"] == "hs_beta"
    monkeypatch.setattr(B, "OWNED_FILE", tmp_path / "owned.json")
    games = B.save_owned({"games": [{"titleId": 1146311730, "localizedGameName": "Destiny 2"},
                                    {"titleId": 4613486, "localizedGameName": "Diablo IV"}]})
    assert [g["title"] for g in games] == ["Diablo IV"]


def test_uninstaller_from_registry(tmp_path):
    (tmp_path / "system.reg").write_text(
        '[Software\\\\Wow6432Node\\\\Microsoft\\\\Windows\\\\CurrentVersion\\\\Uninstall\\\\Overwatch] 1\n'
        '"UninstallString"="\\"C:\\\\ProgramData\\\\Battle.net\\\\Agent\\\\Blizzard Uninstaller.exe\\" '
        '--lang=enUS --uid=pro --displayname=\\"Overwatch\\""\n')
    assert B.uninstall_argv(str(tmp_path), "pro") == [
        "C:\\ProgramData\\Battle.net\\Agent\\Blizzard Uninstaller.exe", "--lang=enUS", "--uid=pro", "--displayname=Overwatch"]
    assert B.uninstall_argv(str(tmp_path), "wow") == []


def test_watch_follows_the_game_not_the_launcher(monkeypatch):
    """Battle.net's starter exits at once; the game (argv0 in its folder) runs on, then closes."""
    starter = subprocess.Popen(["true"])
    game = subprocess.Popen(["bash", "-c", 'exec -a "C:\\Games\\Overwatch\\Overwatch.exe" sleep 3'])
    store = types.SimpleNamespace(product_db=lambda: "/nonexistent", linux_path=lambda p: p, prefix=lambda: "/nonexistent")
    g = types.SimpleNamespace(id="pro", extra={"uid": "pro"}, install_path="C:/Games/Overwatch")
    seen = []
    t0 = time.time()
    started, ended = B.watch(store, g, starter, seen.append, poll=0.2, grace=0.5)
    game.wait()
    assert started and ended >= started and seen and seen[0] == [game.pid]
    assert 2 <= time.time() - t0 < 10


def test_watch_gives_up_when_battlenet_closes_without_the_game(monkeypatch):
    starter = subprocess.Popen(["true"])
    store = types.SimpleNamespace(product_db=lambda: "/nonexistent", linux_path=lambda p: p, prefix=lambda: "/nonexistent")
    g = types.SimpleNamespace(id="pro", extra={}, install_path="/nonexistent/Overwatch")
    clock = [0.0]
    monkeypatch.setattr(B, "launcher_running", lambda s: False)  # not this PC's real Battle.net
    monkeypatch.setattr(time, "time", lambda: clock[0])
    monkeypatch.setattr(time, "sleep", lambda s: clock.__setitem__(0, clock[0] + s))
    assert B.watch(store, g, starter, lambda p: None, poll=5) == (0.0, 0.0)
    assert clock[0] < 60


def test_hide_parks_quiet_windows_and_shows_the_one_asking(monkeypatch):
    from cornerplay import bnethide, hypr
    wins = [{"address": "a", "class": bnethide.CLASS, "title": "Battle.net", "workspace": {"name": "1"}},
            {"address": "b", "class": bnethide.CLASS, "title": "Battle.net Login", "workspace": {"name": bnethide.PLACE}},
            {"address": "c", "class": "kitty", "title": "shell", "workspace": {"name": "1"}}]
    moves = []
    monkeypatch.setattr(hypr, "clients", lambda: wins)
    monkeypatch.setattr(hypr, "move_window", lambda a, ws, silent=True: moves.append((a, ws)) or True)
    monkeypatch.setattr(hypr, "focus_window", lambda a: True)
    monkeypatch.setattr(hypr, "workspace", lambda: "3")
    assert bnethide.park() == 1 and moves == [("a", bnethide.PLACE)]
    assert bnethide.asking()["address"] == "b"
    moves.clear()
    bnethide.show(bnethide.asking())
    assert moves == [("b", "3")]


def test_launch_without_battlenet_for_wow(tmp_path, monkeypatch):
    from cornerplay.stores.base import Game
    exe = tmp_path / "_retail_" / "Wow.exe"
    exe.parent.mkdir()
    exe.write_text("")
    g = Game(store="battlenet", id="wow", title="World of Warcraft", installed=True, install_path=str(tmp_path),
             extra={"uid": "wow", "launch": "WoW"})
    s = B.BattleNet()
    monkeypatch.setattr(s, "launcher_exe", lambda: "/x/Battle.net.exe")
    monkeypatch.setattr(B.game_options, "get", lambda k: {"bnet_direct": True})
    assert s.launch(g).argv[-1] == str(exe)
    monkeypatch.setattr(B.game_options, "get", lambda k: {})
    monkeypatch.setattr(B, "keep_signed_in", lambda p: None)
    assert s.launch(g).argv[-1] == "--exec=launch WoW"
