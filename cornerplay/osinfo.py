"""Which operating system Cornerplay runs on, and the few things that differ because of it.

Cornerplay started on Linux, where Windows games run through Proton. On Windows they run
natively: no Proton, no Wine prefixes, no umu-launcher, and the Linux-only extras (gamescope,
MangoHud, the compositor tricks, btrfs snapshots...) are simply not offered.
"""
import os
import sys

WINDOWS = sys.platform == "win32"
LINUX = sys.platform.startswith("linux")

# Executables carry .exe on Windows: "legendary" is legendary.exe there.
EXE = ".exe" if WINDOWS else ""


def exe(name: str) -> str:
    """A program's file name on this system ("legendary" -> "legendary.exe" on Windows)."""
    return name + EXE if EXE and not name.lower().endswith(EXE) else name


def home_dirs():
    """(config, data, cache) base folders: XDG on Linux, AppData on Windows."""
    from pathlib import Path
    home = Path.home()
    if WINDOWS:
        roaming = Path(os.environ.get("APPDATA") or home / "AppData" / "Roaming")
        local = Path(os.environ.get("LOCALAPPDATA") or home / "AppData" / "Local")
        return roaming, local, local
    return (Path(os.environ.get("XDG_CONFIG_HOME") or home / ".config"),
            Path(os.environ.get("XDG_DATA_HOME") or home / ".local/share"),
            Path(os.environ.get("XDG_CACHE_HOME") or home / ".cache"))


def run_dir():
    """A private folder for sockets and other short-lived files of this session."""
    import tempfile
    if WINDOWS:
        return tempfile.gettempdir()
    return os.environ.get("XDG_RUNTIME_DIR") or os.path.join(tempfile.gettempdir(), f"cornerplay-{os.getuid()}")


def machine() -> str:
    """The CPU architecture: "x86_64", "aarch64"... (os.uname is not on Windows)."""
    import platform
    m = (platform.machine() or "").lower()
    return {"amd64": "x86_64", "x64": "x86_64", "arm64": "aarch64"}.get(m, m)


def open_path(path: str) -> None:
    """Open a file, folder or link with the desktop's default program."""
    import subprocess
    if WINDOWS:
        os.startfile(path)  # noqa: S606 (the user asked to open it)
    else:
        subprocess.Popen(["xdg-open", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)


def detached() -> dict:
    """subprocess.Popen keywords for a program that outlives Cornerplay and is not tied to its
    console: a new session on Linux, a new process group without a console window on Windows."""
    import subprocess
    if WINDOWS:
        return {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW}
    return {"start_new_session": True}


def no_window() -> dict:
    """subprocess keywords so a command-line tool run in the background does not flash a
    console window on Windows (nothing on Linux)."""
    import subprocess
    return {"creationflags": subprocess.CREATE_NO_WINDOW} if WINDOWS else {}


def pid_alive(pid) -> bool:
    """Is process `pid` still running? Never use os.kill(pid, 0) for this on Windows: there it
    does not ask, it ends the process (TerminateProcess with exit code 0)."""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if not WINDOWS:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.OpenProcess.restype = wintypes.HANDLE
    k32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    k32.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
    k32.CloseHandle.argtypes = (wintypes.HANDLE,)
    handle = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return ctypes.get_last_error() == 5  # ERROR_ACCESS_DENIED: it exists, it is just not ours
    try:
        code = wintypes.DWORD()
        return bool(k32.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259  # STILL_ACTIVE
    finally:
        k32.CloseHandle(handle)


def terminate(pid, force: bool = False) -> bool:
    """End process `pid` and its children: SIGTERM/SIGKILL to its group on Linux, taskkill /T on
    Windows (/F when forced). True when it was asked."""
    import subprocess
    if WINDOWS:
        r = subprocess.run(["taskkill", "/PID", str(int(pid)), "/T", *(["/F"] if force else [])],
                           capture_output=True, **no_window())
        return r.returncode == 0
    import signal
    try:
        os.killpg(int(pid), signal.SIGKILL if force else signal.SIGTERM)
        return True
    except OSError:
        return False


def reg_value(path: str, name: str = "", default=None):
    """A value from the Windows registry: path like r"HKCU\\Software\\Valve\\Steam". Tries the
    64-bit and the 32-bit view (launchers often register under WOW6432Node). default elsewhere."""
    if not WINDOWS:
        return default
    import winreg
    hive_name, _, sub = path.partition("\\")
    hive = {"HKCU": winreg.HKEY_CURRENT_USER, "HKLM": winreg.HKEY_LOCAL_MACHINE}.get(hive_name.upper())
    if hive is None:
        return default
    for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
        try:
            with winreg.OpenKey(hive, sub, 0, winreg.KEY_READ | view) as k:
                return winreg.QueryValueEx(k, name)[0]
        except OSError:
            continue
    return default


def reg_subkeys(path: str) -> list:
    """The names of a registry key's subkeys ([] when it is missing, or not on Windows)."""
    if not WINDOWS:
        return []
    import winreg
    hive_name, _, sub = path.partition("\\")
    hive = {"HKCU": winreg.HKEY_CURRENT_USER, "HKLM": winreg.HKEY_LOCAL_MACHINE}.get(hive_name.upper())
    out = []
    for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
        try:
            with winreg.OpenKey(hive, sub, 0, winreg.KEY_READ | view) as k:
                i = 0
                while True:
                    try:
                        name = winreg.EnumKey(k, i)
                    except OSError:
                        break
                    if name not in out:
                        out.append(name)
                    i += 1
        except OSError:
            continue
    return out


def steam_windows():
    """(Steam folder, steam.exe) on Windows from the registry, else the usual place; (None, None)."""
    from pathlib import Path
    if not WINDOWS:
        return None, None
    root = reg_value(r"HKCU\Software\Valve\Steam", "SteamPath") or reg_value(r"HKLM\SOFTWARE\Valve\Steam", "InstallPath")
    exe_path = reg_value(r"HKCU\Software\Valve\Steam", "SteamExe")
    if not root:
        guess = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Steam"
        root = str(guess) if guess.is_dir() else None
    if root and not exe_path:
        exe_path = os.path.join(root, "steam.exe")
    root = os.path.normpath(root) if root else None
    exe_path = os.path.normpath(exe_path) if exe_path and os.path.isfile(exe_path) else None
    return root, exe_path


def process_programs() -> list:
    """[(pid, program path)] for every process this user can see: /proc on Linux, the Windows
    API on Windows (QueryFullProcessImageName; processes it may not open are left out)."""
    me = os.getpid()
    out = []
    if not WINDOWS:
        for d in os.listdir("/proc"):
            if not d.isdigit() or int(d) == me:
                continue
            try:
                with open(f"/proc/{d}/cmdline", "rb") as f:
                    prog = f.read().split(b"\0")[0].decode("utf-8", "replace")
            except OSError:
                continue
            if prog:
                out.append((int(d), prog))
        return out
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    k32.OpenProcess.restype = wintypes.HANDLE
    k32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    k32.QueryFullProcessImageNameW.argtypes = (wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                               ctypes.POINTER(wintypes.DWORD))
    k32.CloseHandle.argtypes = (wintypes.HANDLE,)
    n = 4096
    while True:
        pids = (wintypes.DWORD * n)()
        got = wintypes.DWORD()
        if not psapi.EnumProcesses(pids, ctypes.sizeof(pids), ctypes.byref(got)):
            return out
        if got.value < ctypes.sizeof(pids):
            break
        n *= 2
    buf = ctypes.create_unicode_buffer(32768)
    for pid in pids[:got.value // ctypes.sizeof(wintypes.DWORD)]:
        if pid in (0, me):
            continue
        h = k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            continue
        try:
            size = wintypes.DWORD(len(buf))
            if k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                out.append((int(pid), buf.value))
        finally:
            k32.CloseHandle(h)
    return out


FROZEN = bool(getattr(sys, "frozen", False))  # the packaged Windows build (PyInstaller)


def python_argv(module: str = "", *args, code: str = "") -> list:
    """A command line that runs one of Cornerplay's modules (`python -m cornerplay.session ...`)
    or a line of Python, in a process of its own. The packaged Windows build has no python.exe:
    Cornerplay.exe itself takes --run-module / --run-code then (see run_frozen_helper)."""
    if FROZEN:
        return [sys.executable, "--run-code", code] if code else [sys.executable, "--run-module", module, *args]
    return [sys.executable, "-c", code] if code else [sys.executable, "-m", module, *args]


def run_frozen_helper(argv=None) -> bool:
    """In the packaged build: run what python_argv asked for, the way `python -m` would. False
    when argv is an ordinary start of the app."""
    import runpy
    hide_console_windows()
    argv = list(sys.argv if argv is None else argv)
    if len(argv) >= 3 and argv[1] == "--run-module" and argv[2].split(".")[0] == "cornerplay":
        sys.argv = [argv[2], *argv[3:]]
        runpy.run_module(argv[2], run_name="__main__", alter_sys=True)
        return True
    if len(argv) >= 3 and argv[1] == "--run-code":
        sys.argv = ["-c", *argv[3:]]
        exec(compile(argv[2], "<cornerplay>", "exec"), {"__name__": "__main__"})  # noqa: S102 (our own line, from python_argv)
        return True
    return False


def hide_console_windows() -> None:
    """Windows: every command-line tool Cornerplay runs (legendary, nile, gogdl, taskkill...)
    would flash a black console window. Start them without one unless the caller chose its own
    creation flags. Games are windowed programs: CREATE_NO_WINDOW does not touch them."""
    if not WINDOWS:
        return
    import subprocess
    if getattr(subprocess.Popen, "_cornerplay_quiet", False):
        return
    original = subprocess.Popen.__init__

    def __init__(self, *args, **kwargs):
        if not kwargs.get("creationflags"):
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        original(self, *args, **kwargs)

    subprocess.Popen.__init__ = __init__
    subprocess.Popen._cornerplay_quiet = True
