"""Cornerplay on Windows: games run natively, helpers start through Cornerplay.exe, and nothing
at the core calls what Windows does not have. The behaviour tests pretend to be on Windows
(osinfo.WINDOWS); the guard tests read the source so a Linux-only call cannot slip back in."""
import ast
import os
import sys
from pathlib import Path

import pytest

from cornerplay import osinfo, runner
from cornerplay.config import settings
from cornerplay.stores.base import Game

SRC = Path(__file__).resolve().parent.parent / "cornerplay"


@pytest.fixture
def windows(monkeypatch):
    """Pretend to be on Windows for the modules that decide by osinfo.WINDOWS."""
    from cornerplay.stores import gog
    for mod in (osinfo, runner, gog):
        monkeypatch.setattr(mod, "WINDOWS", True)


# --- running games -------------------------------------------------------------------------
def test_games_run_natively(windows):
    assert runner.compat() == ("native", "")
    assert runner.wrapper_argv() == []
    assert runner.extras() == []
    assert runner.wrapper_flags() == []


def test_windows_env_is_only_what_the_user_set(windows):
    settings.data["env"] = "A=1"
    settings.data["shader_cache"] = True
    try:
        with runner.using({"env": "B=2", "perf": "battery"}):
            env = runner.wine_env("epic", "x")
        assert env == {"A": "1", "B": "2"}  # no WINEPREFIX, DXVK or MangoHud variables
    finally:
        settings.data["env"] = ""


def test_epic_and_amazon_launch_without_wine_flags(windows, monkeypatch):
    from cornerplay.stores import amazon, epic
    seen = {}

    def fake_run(argv, timeout=120, env=None):
        seen["argv"] = argv

        class R:
            returncode = 0
            stdout = '{"game_directory": "C:/Games/X", "game_executable": "x.exe", "launch_command": []}'
            stderr = ""
        return R()

    monkeypatch.setattr(epic, "run", fake_run)
    monkeypatch.setattr(epic.Epic, "tool", lambda self: "legendary.exe")
    cmd = epic.Epic().launch(Game(store="epic", id="abc", title="X", installed=True))
    assert "--no-wine" not in seen["argv"] and "--wrapper" not in seen["argv"]
    assert cmd.argv == [os.path.join("C:/Games/X", "x.exe")]
    monkeypatch.setattr(amazon.Amazon, "tool", lambda self: "nile.exe")
    a = amazon.Amazon().launch(Game(store="amazon", id="a1", title="Y", installed=True))
    assert a.argv == ["nile.exe", "launch", "a1"]


def test_gog_always_installs_the_windows_build(windows):
    from cornerplay.stores.gog import Gog
    g = Game(store="gog", id="1", title="X", extra={"linux": True})
    assert Gog().platform_for(g) == "windows"


# --- helper processes ----------------------------------------------------------------------
def test_python_argv_plain_and_frozen(monkeypatch):
    assert osinfo.python_argv("cornerplay.session", "job.json") == [sys.executable, "-m", "cornerplay.session", "job.json"]
    assert osinfo.python_argv(code="print(1)") == [sys.executable, "-c", "print(1)"]
    monkeypatch.setattr(osinfo, "FROZEN", True)
    assert osinfo.python_argv("cornerplay.session", "job.json") == [sys.executable, "--run-module", "cornerplay.session", "job.json"]
    assert osinfo.python_argv(code="print(1)") == [sys.executable, "--run-code", "print(1)"]


def test_frozen_helper_runs_only_cornerplay_modules(monkeypatch):
    ran = []
    monkeypatch.setattr("runpy.run_module", lambda name, **k: ran.append(name))
    assert osinfo.run_frozen_helper(["Cornerplay.exe", "--run-module", "cornerplay.session", "x"]) is True
    assert ran == ["cornerplay.session"]
    assert osinfo.run_frozen_helper(["Cornerplay.exe", "--run-module", "os", "x"]) is False
    assert osinfo.run_frozen_helper(["Cornerplay.exe", "--tv"]) is False


def test_exe_names():
    assert osinfo.exe("legendary") == "legendary" + osinfo.EXE
    assert osinfo.exe("nile.exe").lower().count(".exe") == 1
    assert osinfo.machine()


def test_pid_alive():
    assert osinfo.pid_alive(os.getpid())
    assert not osinfo.pid_alive(0)
    assert not osinfo.pid_alive("nope")


def test_process_programs_lists_children():
    import subprocess
    p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(5)"])
    try:
        assert any(pid == p.pid for pid, _prog in osinfo.process_programs())
    finally:
        p.kill()
        p.wait()


def test_battlenet_paths_on_windows(windows, monkeypatch):
    from cornerplay.stores import battlenet
    monkeypatch.setattr(battlenet, "WINDOWS", True)
    monkeypatch.setenv("SystemDrive", "C:")
    b = battlenet.BattleNet()
    assert b.drive_c() == "C:\\"
    assert b.product_db().replace("\\", "/").endswith("ProgramData/Battle.net/Agent/product.db")
    assert b.linux_path("C:/Games/Overwatch") == os.path.normpath("C:/Games/Overwatch")


# --- guards: nothing at the core that Windows lacks -------------------------------------------
UNIX_ONLY_MODULES = {"fcntl", "pwd", "grp", "termios", "resource", "pty", "tty"}


def _sources():
    for p in sorted(SRC.rglob("*.py")):
        yield p, p.read_text(encoding="utf-8")


def test_no_unguarded_unix_only_imports():
    """A top-level `import fcntl` stops the module (and the app) from loading on Windows: it must
    sit in try/except ImportError, or inside the function that needs it."""
    bad = []
    for path, text in _sources():
        tree = ast.parse(text)
        for node in tree.body:  # module level only; a try: block around it is fine
            names = []
            if isinstance(node, ast.Import):
                names = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module.split(".")[0]]
            if set(names) & UNIX_ONLY_MODULES:
                bad.append(f"{path.relative_to(SRC)}:{node.lineno}")
    assert not bad, "unguarded Unix-only import: " + ", ".join(bad)


def test_no_os_kill_zero_probe():
    """os.kill(pid, 0) checks a process on Linux but ENDS it on Windows: use osinfo.pid_alive."""
    bad = []
    for path, text in _sources():
        if path.name == "osinfo.py":
            continue
        for node in ast.walk(ast.parse(text)):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "kill"
                    and isinstance(node.func.value, ast.Name) and node.func.value.id == "os" and len(node.args) == 2
                    and isinstance(node.args[1], ast.Constant) and node.args[1].value == 0):
                bad.append(f"{path.relative_to(SRC)}:{node.lineno}")
    assert not bad, "os.kill(pid, 0): " + ", ".join(bad)


def test_no_os_uname():
    """os.uname() does not exist on Windows: osinfo.machine() says the same."""
    bad = [f"{p.relative_to(SRC)}" for p, text in _sources() if "os.uname()" in text]
    assert not bad, "os.uname(): " + ", ".join(bad)


def test_no_sys_executable_dash_m():
    """The packaged Windows build has no python.exe: start helpers with osinfo.python_argv."""
    bad = []
    for path, text in _sources():
        if path.name == "pkgs.py":  # pip hints for install.sh's venv (Linux)
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if "sys.executable" in line and ('"-m"' in line or '"-c"' in line) and "python_argv" not in line:
                if path.name != "osinfo.py":
                    bad.append(f"{path.relative_to(SRC)}:{i}")
    assert not bad, "sys.executable -m/-c: " + ", ".join(bad)


def test_no_linux_only_os_calls_outside_osinfo():
    """os.sysconf, os.posix_fadvise and SIGSTOP/SIGCONT do not exist on Windows. osinfo wraps
    them (total_ram_gb, suspend); the Linux-only features that still use them directly (freeze,
    clips, fast cores) are hidden on Windows, so they are listed here on purpose."""
    allowed = {"osinfo.py", "freeze.py", "clips.py", "cores.py"}
    bad = []
    for path, text in _sources():
        if path.name in allowed:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if "os.sysconf(" in line or "signal.SIGSTOP" in line or "signal.SIGCONT" in line or (
                    "os.posix_fadvise(" in line and "hasattr" not in text.splitlines()[i - 2]):
                bad.append(f"{path.relative_to(SRC)}:{i}")
    assert not bad, "Linux-only os call: " + ", ".join(bad)


def test_process_tree_and_suspend():
    import subprocess
    import time
    p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        assert p.pid in osinfo.process_tree(os.getpid())
        osinfo.suspend([p.pid], True)
        time.sleep(0.1)
        assert p.poll() is None
        osinfo.suspend([p.pid], False)
    finally:
        p.kill()
        p.wait()
    assert 0.5 < osinfo.total_ram_gb() < 100000
