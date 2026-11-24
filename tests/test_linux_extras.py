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


def test_run_in_prefix_commands(tmp_path, monkeypatch):
    import types
    from cornerplay import app as A, runner
    from cornerplay.stores.base import Game
    trainer = tmp_path / "Trainer.exe"
    trainer.write_text("")
    started = []
    games = {"gog:1": Game(store="gog", id="1", title="Witcher", installed=True, install_path=str(tmp_path)),
             "battlenet:pro": Game(store="battlenet", id="pro", title="Overwatch", installed=True, install_path=str(tmp_path)),
             "steam:220": Game(store="steam", id="220", title="HL2", installed=True, install_path=str(tmp_path))}
    f = types.SimpleNamespace(demo=False, model=types.SimpleNamespace(find=games.get),
                              stores={"battlenet": types.SimpleNamespace(env=lambda: {"WINEPREFIX": "/bnet", "GAMEID": "umu-battlenet"})},
                              _options_for=lambda g: {}, toast=types.SimpleNamespace(emit=lambda m: None),
                              _detach=lambda argv, env, cwd, name: started.append((argv, env, cwd)) or True,
                              PREFIX_TOOLS=A.AioLaunch.PREFIX_TOOLS)
    f.prefixToolsFor = lambda k: True
    monkeypatch.setattr(runner, "compat", lambda: ("umu", "/usr/bin/umu-run"))
    monkeypatch.setattr(runner, "wine_env", lambda store, gid: {"WINEPREFIX": f"/pfx/{store}-{gid}"})
    monkeypatch.setattr(A, "_appid", lambda g: g.id)
    A.AioLaunch.runInPrefix(f, "gog:1", "file://" + str(trainer))
    A.AioLaunch.runInPrefix(f, "battlenet:pro", "regedit")
    A.AioLaunch.runInPrefix(f, "steam:220", "winecfg")
    A.AioLaunch.runInPrefix(f, "steam:220", str(trainer))
    assert started[0] == (["/usr/bin/umu-run", str(trainer)], {"WINEPREFIX": "/pfx/gog-1"}, str(tmp_path))
    assert started[1][0] == ["/usr/bin/umu-run", "regedit"] and started[1][1]["GAMEID"] == "umu-cornerplay-tools"
    assert started[2][0] == ["protontricks", "-c", "wine winecfg", "220"]
    assert started[3][0] == ["protontricks-launch", "--appid", "220", str(trainer)]


def test_screen_mode_switches_and_puts_back(tmp_path, monkeypatch):
    from cornerplay import hypr, screenmode, stream
    calls = []
    monkeypatch.setattr(screenmode, "STATE_DIR", tmp_path)
    monkeypatch.setattr(stream, "fit_display", lambda w, h, hz, state_dir=None: calls.append(("fit", w, h, hz)) or "eDP-1 at ...")
    monkeypatch.setattr(stream, "restore_display", lambda state_dir=None: calls.append(("restore",)) or True)
    monkeypatch.setattr(stream, "display_backend", lambda: "hyprland")
    vrr = {"misc:vrr": 0}
    monkeypatch.setattr(hypr, "option", lambda k: vrr[k])
    monkeypatch.setattr(hypr, "set_option", lambda k, v: vrr.__setitem__(k, v) or True)
    undo = screenmode.begin("2560x1600@120", vrr=True)
    assert calls == [("fit", 2560, 1600, 120.0)] and vrr["misc:vrr"] == 1
    screenmode.end(undo)
    assert calls[-1] == ("restore",) and vrr["misc:vrr"] == 0
    assert screenmode.begin("", vrr=False) == {} and screenmode.parse("junk") is None


LOG = """ProtonFixes[123] INFO: Running checks
1.0:0020:0024:trace:loaddll:build_module Loaded L"C:\\\\windows\\\\system32\\\\mscoree.dll" at 00006FFFFDE70000: builtin
1.1:0020:0024:trace:loaddll:build_module Loaded L"C:\\\\windows\\\\system32\\\\d3dx9_43.dll" at 00006FFFFDE70000: builtin
1.2:0098:00b0:err:hid:get_container_id_for_usb_udev_device Failed to get parent device.
2.0:0100:0104:err:module:import_dll Library MSVCP140.dll (which is needed by L"C:\\\\Games\\\\Witcher\\\\bin\\\\witcher3.exe") not found
2.0:0100:0104:err:module:import_dll Library VCRUNTIME140_1.dll (which is needed by L"C:\\\\Games\\\\Witcher\\\\bin\\\\witcher3.exe") not found
2.0:0100:0104:err:module:loader_init Importing dlls for L"C:\\\\Games\\\\Witcher\\\\bin\\\\witcher3.exe" failed, status c0000135
err:   DXVK: Failed to create shader module
wine: Unhandled page fault on read access to 0000000000000000 at address 00000001400A2B31 (thread 0104), starting debugger...
Unhandled exception: page fault on read access to 0x00000000 in 64-bit code (0x00000001400a2b31).
Backtrace:
=>0 0x00000001400a2b31 in witcher3 (+0xa2b31) (0x000000000021fd40)
  1 0x000000014003c10f in witcher3 (+0x3c10f)
"""


def test_log_reader_finds_what_matters():
    from cornerplay import logreader
    r = logreader.read(LOG)
    assert r["crash"]["where"] == "witcher3" and r["crash"]["offset"] == "a2b31" and "page fault" in r["crash"]["what"]
    assert [m["dll"] for m in r["missing"]] == ["MSVCP140.dll", "VCRUNTIME140_1.dll"]
    assert r["missing"][0]["fix"] == "vcrun" and r["missing"][0]["by"] == "witcher3.exe"
    assert not any(e.startswith("hid:") for e in r["errors"]) and r["errors"][0].startswith("module:")
    assert r["graphics"] == ["err:   DXVK: Failed to create shader module"]
    assert r["explain"]["fix"] == "vcrun"  # Visual C++, not .NET or DirectX from the "Loaded" notes


def test_explain_ignores_wine_notes_about_loaded_libraries():
    from cornerplay import problems
    notes = ('1.0:0020:0024:trace:loaddll:build_module Loaded L"C:\\\\windows\\\\system32\\\\mscoree.dll" at 0: builtin\n'
             '1.1:0020:0024:fixme:d3dx:something d3dx9_43.dll stub\n')
    assert problems.explain(notes) == {}
