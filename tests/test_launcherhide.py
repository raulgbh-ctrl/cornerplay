"""Store apps kept out of sight while their games start, and Steam's own downloads listed."""
from cornerplay import hypr, launcherhide as lh


def _fake(monkeypatch, wins):
    moves, closed = [], []
    monkeypatch.setattr(hypr, "clients", lambda: wins)
    monkeypatch.setattr(hypr, "lua", lambda: False)
    monkeypatch.setattr(hypr, "workspace", lambda: "2")
    monkeypatch.setattr(hypr, "focus_window", lambda a: True)

    def move(a, ws, silent=True):
        moves.append((a, ws))
        next(w for w in wins if w["address"] == a)["workspace"] = {"name": ws}
        return True
    monkeypatch.setattr(hypr, "move_window", move)
    monkeypatch.setattr(hypr, "close_window", lambda a: closed.append(a) or True)
    return moves, closed


def test_steam_windows_hidden_but_never_its_games(monkeypatch):
    spec = lh.get("steam")
    wins = [{"address": "main", "class": "steam", "title": "Steam", "workspace": {"name": "1"}},
            {"address": "game", "class": "steam_app_620", "title": "Portal 2", "workspace": {"name": "1"}},
            {"address": "guard", "class": "steam", "title": "Steam Guard - Computer Authorization Required",
             "workspace": {"name": "1"}}]
    moves, closed = _fake(monkeypatch, wins)
    assert lh.park(spec) == 1 and moves == [("main", spec.place)]
    assert lh.asking(spec)["address"] == "guard"
    lh.put_away(spec)  # Steam opened only for the game: its hidden window closes (to the tray)
    assert closed == ["main"]


def test_windows_open_before_stay_where_they_are(monkeypatch):
    spec = lh.get("steam")
    wins = [{"address": "main", "class": "steam", "title": "Steam", "workspace": {"name": "1"}}]
    moves, closed = _fake(monkeypatch, wins)
    h = lh.Hider(spec)
    assert h.was_open and lh.park(spec, h.keep) == 0
    wins.append({"address": "dlg", "class": "Steam", "title": "Launching", "workspace": {"name": "1"}})
    assert lh.park(spec, h.keep) == 1
    h.finish()
    assert closed == [] and moves[-1] == ("dlg", "2")  # back on screen, quietly


def test_hider_hides_while_the_game_runs_and_brings_it_back_after(monkeypatch):
    import time
    spec = lh.get("prism")
    wins = []
    moves, _closed = _fake(monkeypatch, wins)
    h = lh.Hider(spec, poll=0.01).start()  # not open before: it appears once the game is started
    wins.append({"address": "p", "class": "org.prismlauncher.PrismLauncher", "title": "Prism Launcher",
                 "workspace": {"name": "1"}})
    for _ in range(200):
        if moves:
            break
        time.sleep(0.01)
    h.finish()
    assert moves[0] == ("p", spec.place) and moves[-1] == ("p", "2")


def test_steam_download_state():
    from cornerplay.stores.steam import download_state
    assert download_state({"StateFlags": "4"}) == {}
    assert download_state({"StateFlags": "1026", "BytesToDownload": "200", "BytesDownloaded": "50",
                           "buildid": "0"}) == {"kind": "install", "progress": 25.0}
    assert download_state({"StateFlags": "1030", "BytesToDownload": "100", "BytesDownloaded": "100",
                           "buildid": "123"})["kind"] == "update"
    assert download_state({"StateFlags": str(1026 | 512), "BytesToDownload": "1"}) == {}  # paused in Steam
    assert download_state({"StateFlags": "x"}) == {}


def test_windows_hides_by_program(monkeypatch):
    from cornerplay import winwindows
    monkeypatch.setattr(lh, "WINDOWS", True)
    state = {1: "desktop", 2: "desktop", 3: "desktop"}
    progs = {1: "steamwebhelper.exe", 2: "notepad.exe", 3: "steamwebhelper.exe"}
    titles = {1: "Steam", 2: "notes", 3: "Steam Guard"}
    monkeypatch.setattr(winwindows, "clients", lambda: [
        {"address": h, "class": progs[h], "title": titles[h], "workspace": {"name": state[h]}} for h in state])
    monkeypatch.setattr(winwindows, "hide", lambda h: state.__setitem__(h, winwindows.HIDDEN) or True)
    monkeypatch.setattr(winwindows, "show", lambda h, focus=True: state.__setitem__(h, "desktop") or True)
    closed = []
    monkeypatch.setattr(winwindows, "close", lambda h: closed.append(h) or True)
    spec = lh.get("steam")
    assert lh.get("xbox") is None  # the Xbox app is left alone on Windows
    assert lh.park(spec) == 1 and state == {1: "hidden", 2: "desktop", 3: "desktop"}
    assert lh.asking(spec)["address"] == 3
    assert lh.rule(spec, True) is False
    lh.put_away(spec)
    assert closed == [1]
