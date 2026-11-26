"""Windows' top-level windows, for keeping store apps out of sight (launcherhide.py).

The same shape as hypr.clients(): [{"address", "class", "title", "workspace": {"name"}}], where
"class" is the program's file name in lower case (steam.exe, battle.net.exe) and a window
Cornerplay hid has the workspace name HIDDEN. Hiding is ShowWindow(SW_HIDE): no taskbar
button, no flash; showing brings it back (to the front when it needs you).
"""
import ctypes
import os
from ctypes import wintypes

HIDDEN = "hidden"
SW_HIDE, SW_SHOWNOACTIVATE, SW_SHOW = 0, 4, 5
WM_CLOSE = 0x0010
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

_hidden = set()  # windows Cornerplay hid in this process (others' hidden windows are not ours)


def available() -> bool:
    return os.name == "nt"


_u32 = None


def _user32():
    """user32 with its argument types set: window handles are 64-bit, and plain ints would be cut."""
    global _u32
    if _u32 is None:
        u = ctypes.windll.user32
        H = wintypes.HWND
        u.ShowWindow.argtypes = (H, ctypes.c_int)
        u.SetForegroundWindow.argtypes = (H,)
        u.PostMessageW.argtypes = (H, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
        u.IsWindowVisible.argtypes = (H,)
        u.GetWindowTextLengthW.argtypes = (H,)
        u.GetWindowTextW.argtypes = (H, wintypes.LPWSTR, ctypes.c_int)
        u.GetWindowThreadProcessId.argtypes = (H, ctypes.POINTER(wintypes.DWORD))
        _u32 = u
    return _u32


def _program(pid) -> str:
    k32 = ctypes.windll.kernel32
    h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(len(buf))
        if k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return os.path.basename(buf.value).lower()
        return ""
    finally:
        k32.CloseHandle(h)


def clients() -> list:
    """Top-level windows that are on screen, or that Cornerplay hid."""
    if not available():
        return []
    u = _user32()
    out, names = [], {}
    proto = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def each(hwnd, _):
        hwnd = int(hwnd or 0)
        mine = hwnd in _hidden
        if not (mine or u.IsWindowVisible(hwnd)):
            return True
        n = u.GetWindowTextLengthW(hwnd)
        title = ctypes.create_unicode_buffer(n + 1)
        u.GetWindowTextW(hwnd, title, n + 1)
        if not title.value and not mine:
            return True
        pid = wintypes.DWORD()
        u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value not in names:
            names[pid.value] = _program(pid.value)
        out.append({"address": hwnd, "class": names[pid.value], "title": title.value,
                    "workspace": {"name": HIDDEN if mine else "desktop"}})
        return True
    u.EnumWindows(proto(each), 0)
    return out


def hide(hwnd) -> bool:
    _hidden.add(hwnd)
    _user32().ShowWindow(hwnd, SW_HIDE)
    return True


def show(hwnd, focus=True) -> bool:
    _hidden.discard(hwnd)
    u = _user32()
    u.ShowWindow(hwnd, SW_SHOW if focus else SW_SHOWNOACTIVATE)
    if focus:
        u.SetForegroundWindow(hwnd)
    return True


def close(hwnd) -> bool:
    """As its close button would (Steam then sits in the tray)."""
    _hidden.discard(hwnd)
    return bool(_user32().PostMessageW(hwnd, WM_CLOSE, 0, 0))
