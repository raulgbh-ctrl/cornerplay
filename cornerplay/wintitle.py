"""Windows: the title bar (the strip with the window's name and its minimise, maximise and close
buttons) takes Cornerplay's own colours, so it matches the app in dark, light or any theme.

Windows 11 lets an app set the caption, text and border colours itself (DwmSetWindowAttribute);
Windows 10 only offers dark or light, so there the bar at least follows the theme's darkness.
Nothing happens on Linux, where the desktop draws the window frames.
"""
from . import osinfo

# DwmSetWindowAttribute attributes (dwmapi.h)
_DARK_MODE_OLD = 19   # Windows 10 1809-1909
_DARK_MODE = 20       # Windows 10 2004 and later
_BORDER_COLOR = 34    # Windows 11
_CAPTION_COLOR = 35   # Windows 11
_TEXT_COLOR = 36      # Windows 11


def _colorref(hex_colour: str):
    """'#rrggbb' (or '#aarrggbb') -> COLORREF 0x00bbggrr, None when it is not a colour."""
    h = str(hex_colour or "").lstrip("#")
    if len(h) == 8:
        h = h[2:]
    if len(h) != 6:
        return None
    try:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except ValueError:
        return None
    return r | (g << 8) | (b << 16)


def _set(dwm, hwnd, attr, value) -> bool:
    import ctypes
    v = ctypes.c_int(value)
    return dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(v), ctypes.sizeof(v)) == 0


def paint(window, theme: dict) -> None:
    """Colour one window's title bar from the theme (a no-op off Windows or for frameless windows)."""
    if not osinfo.WINDOWS or window is None or not theme:
        return
    try:
        from PySide6.QtCore import Qt
        if window.flags() & Qt.WindowType.FramelessWindowHint:
            return
        hwnd = int(window.winId())
    except (AttributeError, TypeError, ValueError, RuntimeError):
        return
    if not hwnd:
        return
    try:
        import ctypes
        from ctypes import wintypes
        dwm = ctypes.WinDLL("dwmapi")
        dwm.DwmSetWindowAttribute.argtypes = (wintypes.HWND, wintypes.DWORD, wintypes.LPCVOID, wintypes.DWORD)
        dwm.DwmSetWindowAttribute.restype = ctypes.c_long
    except (OSError, AttributeError):
        return
    dark = bool(theme.get("dark", True))
    if not _set(dwm, hwnd, _DARK_MODE, int(dark)):
        _set(dwm, hwnd, _DARK_MODE_OLD, int(dark))
    caption = _colorref(theme.get("surfaceContainerLow") or theme.get("background"))
    text = _colorref(theme.get("onSurface"))
    border = _colorref(theme.get("surfaceContainer") or theme.get("background"))
    # Refused quietly on Windows 10, which keeps the dark/light bar set above.
    if caption is not None:
        _set(dwm, hwnd, _CAPTION_COLOR, caption)
    if text is not None:
        _set(dwm, hwnd, _TEXT_COLOR, text)
    if border is not None:
        _set(dwm, hwnd, _BORDER_COLOR, border)


def follow(qt_app, cornerplay) -> None:
    """Keep every Cornerplay window's title bar in the app's colours: now, whenever the theme
    changes (light/dark, a new palette, evening warmth), and when a new window opens."""
    if not osinfo.WINDOWS:
        return
    def paint_all(*_):
        theme = dict(cornerplay.theme or {})
        for w in qt_app.topLevelWindows():
            if w.isVisible():
                paint(w, theme)

    cornerplay.themeChanged.connect(paint_all)
    # A window that opens (the sign-in window, a dialog) takes focus: paint it then. Cheaper than
    # watching every event, and painting twice does no harm.
    qt_app.focusWindowChanged.connect(paint_all)
    paint_all()
