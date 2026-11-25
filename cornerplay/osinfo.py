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
