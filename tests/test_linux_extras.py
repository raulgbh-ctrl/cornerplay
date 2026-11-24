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


def _until(check, timeout=5.0):
    """Wait for check() to hold (a busy test machine is slower than a fixed sleep)."""
    import time
    end = time.time() + timeout
    while time.time() < end:
        if check():
            return True
        time.sleep(0.05)
    return check()


def test_freeze_stops_the_game_tree_when_away_and_resumes_on_its_window(monkeypatch):
    import subprocess
    from cornerplay import freeze, hypr
    game = subprocess.Popen(["bash", "-c", "sleep 30 & wait"], start_new_session=True)
    try:
        assert _until(lambda: len(freeze.tree(game.pid)) > 1), "the stand-in game has a child process"
        kids = [p for p in freeze.tree(game.pid) if p != game.pid]
        monkeypatch.setattr(freeze, "DELAY", 0.1)
        monkeypatch.setattr(hypr, "running", lambda: False)  # no real event socket in tests
        monkeypatch.setattr(hypr, "clients", lambda: [{"address": "0xgame", "pid": kids[0]},
                                                      {"address": "0xother", "pid": 1}])
        told = []
        fr = freeze.Freezer(on_frozen=told.append)
        fr.set_games({"gog:1": {"root": game.pid}})
        fr.focused("other")                      # another window: stops after DELAY
        assert _until(lambda: _state(game.pid) == "T" and _state(kids[0]) == "T") and told == ["gog:1"]
        fr.focused("game")                       # back on the game's window: carries on
        assert _until(lambda: _state(game.pid) != "T" and _state(kids[0]) != "T")
        fr.focused("")                           # an empty workspace counts as away
        assert _until(lambda: _state(game.pid) == "T")
        fr.set_games({})                         # the game closed / switched off: never left stopped
        assert _until(lambda: _state(game.pid) != "T")
    finally:
        os.killpg(game.pid, 9)
        game.wait()


def test_lan_copy_end_to_end(tmp_path):
    import io
    import pytest
    from cornerplay import lancopy
    src = tmp_path / "share" / "Hollow Knight"
    (src / "data" / "deep").mkdir(parents=True)
    (src / "game.exe").write_bytes(os.urandom(3 * 1024 * 1024 + 7))
    (src / "data" / "deep" / "level.pak").write_bytes(b"level" * 1000)
    (src / "data" / "empty.txt").write_bytes(b"")
    os.symlink("game.exe", src / "link.exe")
    (tmp_path / "share" / "secret.txt").write_text("not yours")
    games = [{"key": "gog:42", "store": "gog", "id": "42", "title": "Hollow Knight", "path": str(src), "size": 3 * 2**20}]
    srv = lancopy.Server("other-pc", "ABCD-EFGH-23", lambda: games, port=0)
    srv.port = 0
    srv.start()
    port = srv.http.server_address[1]
    try:
        peer = {"host": "127.0.0.1", "port": port, "code": "abcdefgh23"}
        listed = lancopy.games_on(peer)
        assert [g["key"] for g in listed] == ["gog:42"] and listed[0]["folder"] == "Hollow Knight"
        with pytest.raises(PermissionError):
            lancopy.games_on(dict(peer, code="WRONG"))
        # ../ out of the game's folder is refused
        assert lancopy.inside(str(src), "../secret.txt") == ""
        dest = tmp_path / "copy" / "Hollow Knight"
        # a copy cut off halfway: the next run carries on from the partial file
        dest.mkdir(parents=True)
        (dest / "game.exe.cornerplay-part").write_bytes((src / "game.exe").read_bytes()[:1_000_000])
        out = io.StringIO()
        assert lancopy.fetch("127.0.0.1", port, "ABCDEFGH23", "gog:42", str(dest), out=out) == 0
        assert (dest / "game.exe").read_bytes() == (src / "game.exe").read_bytes()
        assert (dest / "data" / "deep" / "level.pak").read_bytes() == b"level" * 1000
        assert (dest / "data" / "empty.txt").exists() and os.readlink(dest / "link.exe") == "game.exe"
        assert not list(dest.rglob("*.cornerplay-part")) and "Progress: 100.0%" in out.getvalue()
    finally:
        srv.stop()


def test_drive_verdicts(monkeypatch):
    from cornerplay import drives
    cases = [({"fstype": "ntfs3", "options": ["rw"]}, {}, False, "windows"),
             ({"fstype": "exfat", "options": ["rw"]}, {"removable": True, "transport": "usb"}, False, "windows"),
             ({"fstype": "ext4", "options": ["rw", "noexec"]}, {}, False, "noexec"),
             ({"fstype": "ext4", "options": ["rw"]}, {"rotational": True}, True, "hdd"),
             ({"fstype": "ext4", "options": ["rw"], "source": "/dev/mmcblk0p1"}, {"transport": "mmc"}, True, "sd"),
             ({"fstype": "btrfs", "options": ["rw"]}, {"rotational": False}, True, "good")]
    for m, d, ok, key in cases:
        monkeypatch.setattr(drives, "mount", lambda p, m=m: dict({"target": "/games", "source": "/dev/sda1"}, **m))
        monkeypatch.setattr(drives, "disk", lambda s, d=d: d)
        j = drives.judge("/games")
        assert j["ok"] is ok and j["detail"] == drives.DETAILS[key], (m, d)
    assert drives.verdict(25) == drives.DETAILS["slow"] and drives.verdict(150) == drives.DETAILS["fast"]


def test_drive_speed_measures_and_cleans_up(tmp_path):
    from cornerplay import drives
    r = drives.speed(str(tmp_path), mb=4)
    assert r["read"] > 0 and r["write"] > 0 and not list(tmp_path.iterdir())
