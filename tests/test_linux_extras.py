"""The 2026-11-25 Linux extras: fast cores, ..."""
import os


def _w(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


def test_fast_cores_intel_hybrid(tmp_path):
    from cornerplay import cores
    _w(f"{tmp_path}/cpu_core/cpus", "0-15\n")
    _w(f"{tmp_path}/cpu_atom/cpus", "16-23\n")
    f = cores.fast(str(tmp_path))
    assert f["kind"] == "intel-hybrid" and f["cpus"] == list(range(16))


def test_fast_cores_amd_x3d_picks_the_big_cache(tmp_path):
    from cornerplay import cores
    for cpu in range(32):
        group = "0-7,16-23" if cpu % 16 < 8 else "8-15,24-31"
        _w(f"{tmp_path}/system/cpu/cpu{cpu}/cache/index3/shared_cpu_list", group)
        _w(f"{tmp_path}/system/cpu/cpu{cpu}/cache/index3/size", "98304K" if group.startswith("0") else "32768K")
    f = cores.fast(str(tmp_path))
    assert f["kind"] == "amd-x3d" and cores.to_list(f["cpus"]) == "0-7,16-23"


def test_fast_cores_nothing_on_an_ordinary_cpu(tmp_path):
    from cornerplay import cores
    for cpu in range(16):
        _w(f"{tmp_path}/system/cpu/cpu{cpu}/cache/index3/shared_cpu_list", "0-15")
        _w(f"{tmp_path}/system/cpu/cpu{cpu}/cache/index3/size", "16384K")
    assert cores.fast(str(tmp_path)) == {}
    assert cores.parse_list("0-3,8,10-11") == [0, 1, 2, 3, 8, 10, 11] and cores.to_list([3, 0, 1, 2, 8]) == "0-3,8"


def _state(pid):
    with open(f"/proc/{pid}/stat") as f:
        return f.read().rsplit(")", 1)[1].split()[0]


def test_freeze_stops_the_game_tree_when_away_and_resumes_on_its_window(monkeypatch):
    import subprocess
    import time
    from cornerplay import freeze, hypr
    game = subprocess.Popen(["bash", "-c", "sleep 30 & wait"], start_new_session=True)
    try:
        time.sleep(0.3)
        kids = [p for p in freeze.tree(game.pid) if p != game.pid]
        assert kids, "the stand-in game has a child process"
        monkeypatch.setattr(freeze, "DELAY", 0.1)
        monkeypatch.setattr(hypr, "running", lambda: False)  # no real event socket in tests
        monkeypatch.setattr(hypr, "clients", lambda: [{"address": "0xgame", "pid": kids[0]},
                                                      {"address": "0xother", "pid": 1}])
        told = []
        fr = freeze.Freezer(on_frozen=told.append)
        fr.set_games({"gog:1": {"root": game.pid}})
        fr.focused("other")                      # another window: stops after DELAY
        time.sleep(0.4)
        assert told == ["gog:1"] and _state(game.pid) == "T" and _state(kids[0]) == "T"
        fr.focused("game")                       # back on the game's window: carries on
        time.sleep(0.1)
        assert _state(game.pid) != "T" and _state(kids[0]) != "T"
        fr.focused("")                           # an empty workspace counts as away
        time.sleep(0.4)
        assert _state(game.pid) == "T"
        fr.set_games({})                         # the game closed / switched off: never left stopped
        time.sleep(0.1)
        assert _state(game.pid) != "T"
    finally:
        os.killpg(game.pid, 9)
        game.wait()
