"""A game's own screen mode while it plays: 120 Hz for a shooter, a lower resolution for an old
game that looks blurry scaled, variable refresh rate on. Back to yours when the last game closes.

A game's Options > Screen while playing names a mode of the screen in front ("2560x1600@120");
Options > Variable refresh asks for VRR. Hyprland, Sway and KDE Plasma, through the same
switching the streaming code uses (stream.fit_display), with its own record of how the screen
was (a stream and a game never overwrite each other's "before").
"""
import json
import subprocess

from . import stream
from .config import CACHE_DIR

STATE_DIR = CACHE_DIR / "screenmode"


def modes() -> list:
    """[(w, h, hz)] the screen in front can show, biggest first ([] when this desktop cannot say)."""
    out = []
    try:
        backend = stream.display_backend()
        if backend == "hyprland":
            mons = json.loads(stream._run(["hyprctl", "monitors", "-j"], stream._hypr_env(), timeout=5))
            m = next((m for m in mons if m.get("focused")), mons[0] if mons else None)
            out = stream._hypr_mode_list(m or {})
        elif backend == "sway":
            outs = [o for o in json.loads(stream._run(["swaymsg", "-t", "get_outputs", "-r"], timeout=5)) if o.get("active")]
            o = next((o for o in outs if o.get("focused")), outs[0] if outs else {})
            out = [(m["width"], m["height"], m["refresh"] / 1000) for m in o.get("modes") or []]
        elif backend == "kde":
            outs = [o for o in json.loads(stream._run(["kscreen-doctor", "-j"], timeout=5)).get("outputs") or [] if o.get("enabled")]
            o = next((o for o in outs if o.get("priority") == 1), outs[0] if outs else {})
            out = [(m["size"]["width"], m["size"]["height"], float(m["refreshRate"])) for m in o.get("modes") or []]
    except (RuntimeError, OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired):
        return []
    seen, unique = set(), []
    for w, h, hz in sorted(out, key=lambda m: (-m[0] * m[1], -m[2])):
        k = (w, h, round(hz))
        if k not in seen:
            seen.add(k)
            unique.append((w, h, hz))
    return unique


def choices() -> list:
    """For a game's Options: [{"label", "value"}], "" = as it is."""
    return [{"label": f"{w}×{h} · {round(hz)} Hz", "value": f"{w}x{h}@{round(hz)}"} for w, h, hz in modes()]


def parse(value: str):
    """"2560x1600@120" -> (2560, 1600, 120.0), else None."""
    try:
        size, _, hz = (value or "").partition("@")
        w, h = (int(x) for x in size.lower().split("x"))
        return w, h, float(hz or 60)
    except ValueError:
        return None


def _vrr(on: bool):
    """Variable refresh on the screen in front; returns how to undo it ({} if nothing changed)."""
    backend = stream.display_backend()
    try:
        if backend == "hyprland":
            from . import hypr
            was = hypr.option("misc:vrr")
            if was is None or (was != 0) == on:
                return {}
            hypr.set_option("misc:vrr", 1 if on else 0)
            return {"vrr": ["hyprland", was]}
        if backend == "sway":
            outs = [o for o in json.loads(stream._run(["swaymsg", "-t", "get_outputs", "-r"], timeout=5)) if o.get("active")]
            o = next((o for o in outs if o.get("focused")), outs[0] if outs else None)
            if not o or (o.get("adaptive_sync_status") == "enabled") == on:
                return {}
            stream._run(["swaymsg", "output", o["name"], "adaptive_sync", "on" if on else "off"])
            return {"vrr": ["sway", o["name"], "off" if on else "on"]}
        if backend == "kde":
            outs = [o for o in json.loads(stream._run(["kscreen-doctor", "-j"], timeout=5)).get("outputs") or [] if o.get("enabled")]
            o = next((o for o in outs if o.get("priority") == 1), outs[0] if outs else None)
            if not o or "vrrPolicy" not in o:
                return {}
            was = {0: "never", 1: "always", 2: "automatic"}.get(o["vrrPolicy"], "automatic")
            stream._run(["kscreen-doctor", f"output.{o['name']}.vrrpolicy.{'always' if on else 'never'}"])
            return {"vrr": ["kde", o["name"], was]}
    except (RuntimeError, OSError, ValueError, KeyError, subprocess.TimeoutExpired):
        pass
    return {}


def begin(mode: str = "", vrr: bool = False) -> dict:
    """Switch to a game's mode and/or VRR; returns what end() needs."""
    undo = {}
    pick = parse(mode)
    if pick:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        try:
            if stream.fit_display(*pick, state_dir=STATE_DIR):
                undo["screen_mode"] = True
        except (RuntimeError, OSError, ValueError, KeyError, StopIteration, subprocess.TimeoutExpired):
            pass
    if vrr:
        undo.update(_vrr(True))
    return undo


def end(undo: dict):
    if (undo or {}).get("screen_mode"):
        try:
            stream.restore_display(state_dir=STATE_DIR)
        except (RuntimeError, OSError, subprocess.TimeoutExpired):
            pass
    v = (undo or {}).get("vrr")
    try:
        if v and v[0] == "hyprland":
            from . import hypr
            hypr.set_option("misc:vrr", v[1])
        elif v and v[0] == "sway":
            stream._run(["swaymsg", "output", v[1], "adaptive_sync", v[2]])
        elif v and v[0] == "kde":
            stream._run(["kscreen-doctor", f"output.{v[1]}.vrrpolicy.{v[2]}"])
    except (RuntimeError, OSError, subprocess.TimeoutExpired):
        pass
