from cornerplay import app as appmod



def test_dupes_tag_needs_two_stores():
    p = appmod.LibraryProxy.__new__(appmod.LibraryProxy)
    a = type("G", (), {"store": "steam"})()
    b = type("G", (), {"store": "gog"})()
    c = type("G", (), {"store": "steam"})()
    assert p._has_tag(None, [a, b], "dupes") is True
    assert p._has_tag(None, [a, c], "dupes") is False


def test_because_row_is_empty_without_a_game():
    assert appmod._BECAUSE["test"]([]) is False


def test_fps_cap_wins_over_the_profile(monkeypatch):
    from cornerplay import runner
    monkeypatch.setattr(runner, "_overrides", {"perf": "balanced", "fps_cap": 40, "perf_log": False, "show_fps": False})
    env = runner.perf_env("epic", "x")
    assert env["DXVK_FRAME_RATE"] == "40" and "fps_limit=40" in env["MANGOHUD_CONFIG"]
    assert env.get("WINE_FULLSCREEN_FSR") == "1"  # Balanced's upscaling stays


def test_month_progress_counts_this_month_only():
    from datetime import datetime
    from cornerplay import statsdata
    now = datetime(2026, 11, 18, 12).timestamp()
    nov = datetime(2026, 11, 5).timestamp()
    oct_ = datetime(2026, 10, 5).timestamp()
    log = [["a", nov, nov + 7200], ["b", oct_, oct_ + 3600], ["b", nov, nov + 1800], ["c", nov, nov + 60]]
    p = statsdata.month_progress(log, lambda k: k.upper(), {"a": nov, "b": oct_}, now)
    assert p["hours"] == 2.5 and p["new"] == 2 and p["finish"] == 1 and p["daysLeft"] == 12


def test_goals_merge_newer_wins():
    from cornerplay import personal
    a = {"games": {}, "goals": {"finish": 3, "t": 5}}
    b = {"games": {}, "goals": {"finish": 1, "hours": 20, "t": 9}}
    assert personal._merge(a, b)["goals"]["hours"] == 20


def test_family_limits(monkeypatch):
    import time
    from cornerplay import family
    store = {}
    monkeypatch.setattr(family.settings, "get", lambda k, d=None: store.get(k, d))
    monkeypatch.setattr(family.settings, "set", lambda k, v: store.__setitem__(k, v))
    family.set_rules("Kid", 60, "21:00", "")
    assert family.limited("Kid") and not family.limited("Me")
    noon = time.mktime((2026, 11, 18, 12, 0, 0, 0, 0, -1))
    played = [["a", noon - 3000, noon - 1200]]  # 30 min this morning
    assert family.blocked("Kid", played, noon) == ""
    assert round(family.minutes_left("Kid", played, noon)) == 30
    assert family.blocked("Kid", played, noon, running_since=[noon - 1800]) == "limit"
    late = time.mktime((2026, 11, 18, 21, 30, 0, 0, 0, -1))
    assert family.blocked("Kid", [], late) == "bedtime"
    family.set_pin("1234")
    assert family.pin_ok("1234") and not family.pin_ok("0000")


def test_lutris_games_from_its_database(tmp_path, monkeypatch):
    import sqlite3
    from cornerplay import importer
    db = tmp_path / "pga.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE games (id INTEGER, name TEXT, runner TEXT, installed INTEGER)")
    con.executemany("INSERT INTO games VALUES (?,?,?,?)", [(3, "Diablo II", "wine", 1), (4, "Portal", "steam", 1), (5, "Old", "wine", 0)])
    con.commit()
    con.close()
    monkeypatch.setattr(importer, "LUTRIS_DBS", (str(db),))
    games = importer.lutris_games()
    assert [g["title"] for g in games] == ["Diablo II"]
    assert importer.lutris_command(games[0])[1] == "lutris:rungameid/3"
