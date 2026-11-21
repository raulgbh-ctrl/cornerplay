"""TV mode on the TV: which screen it opens on, and (on Hyprland) that screen at its best.

Settings > TV mode > Screen: "auto" (the default) opens TV mode on a TV or monitor plugged in next
to the PC's own panel, "" stays on the screen the window is on, or a screen's name (HDMI-A-1).
The window itself is moved by the interface (Qt knows the screens on every desktop); this module
only picks the screen, and on Hyprland sets it to its highest resolution, then refresh rate,
for TV mode and back to what it was after (hyprctl keyword monitor: nothing is saved to the
config).
"""
import json
import os
import subprocess

from . import host

INTERNAL = ("eDP", "LVDS", "DSI")  # a laptop's or handheld's own panel


def pick(names: list, current: str, want: str) -> str:
    """The screen TV mode should use ("" = stay where the window is). names: the connected
    screens; current: the window's screen now."""
    if not want:
        return ""
    if want != "auto":
        return want if want in names else ""
    external = [n for n in names if not n.startswith(INTERNAL)]
    if not external or (len(names) == 1):
        return ""
    return current if current in external else external[0]


def _hyprctl(*args):
    if not os.environ.get("HYPRLAND_INSTANCE_SIGNATURE") or not host.which("hyprctl"):
        return None
    try:
        r = subprocess.run(host.argv(["hyprctl", *args]), capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout if r.returncode == 0 else None


def _monitor(name):
    try:
        return next((m for m in json.loads(_hyprctl("monitors", "-j") or "[]") if m.get("name") == name), None)
    except ValueError:
        return None


def _rule(m, mode):
    rule = f"{m['name']},{mode},{m['x']}x{m['y']},{m['scale']:g}"
    return rule + (f",transform,{m['transform']}" if m.get("transform") else "")


def best(name: str) -> dict:
    """Hyprland: the screen at its best mode for TV mode; returns what to put back ({} if nothing)."""
    m = _monitor(name) if name else None
    if not m:
        return {}

    def key(mode):  # "3840x2160@60.00Hz" -> (pixels, Hz)
        try:
            size, _, hz = mode.rstrip("Hz").partition("@")
            w, h = (int(x) for x in size.split("x"))
            return (w * h, float(hz or 0))
        except ValueError:
            return (0, 0.0)
    modes = [x for x in m.get("availableModes") or [] if key(x)[0]]
    if not modes:
        return {}
    top = max(modes, key=key)
    now = f"{m['width']}x{m['height']}@{float(m['refreshRate']):.2f}Hz"
    if key(top) <= key(now):
        return {}
    if _hyprctl("keyword", "monitor", _rule(m, top.replace("Hz", ""))) is None:
        return {}
    return {"name": name, "rule": _rule(m, now.replace("Hz", ""))}


def restore(undo: dict):
    if undo and undo.get("rule"):
        _hyprctl("keyword", "monitor", undo["rule"])
