"""While a game plays, on Linux: lower latency on Hyprland, and lower audio latency (PipeWire).

Low latency (Settings > Games, "Low-latency mode"): a full-screen game may tear instead of
waiting for the compositor (less input lag), and variable refresh rate is on for full-screen
windows. On Ryoku its own Game Mode does exactly this, and Cornerplay's "Do not disturb" turns
that on, so nothing is set twice. Everything goes back when the last game closes.

Low audio latency (a game's Options, for rhythm and fighting games): PipeWire's buffer is made
small (128 samples, about 3 ms) while the game plays, then left to PipeWire again.
"""
import subprocess

from . import host, hypr

RULE = "cornerplay-low-latency"
QUANTUM = 128


def low_latency_begin(ryoku_game_mode: bool) -> dict:
    if ryoku_game_mode or not hypr.running():
        return {}
    before = {"general:allow_tearing": hypr.option("general:allow_tearing"), "misc:vrr": hypr.option("misc:vrr")}
    if None in before.values():
        return {}
    changed = {}
    if before["general:allow_tearing"] is not True and hypr.set_option("general:allow_tearing", True):
        changed["general:allow_tearing"] = before["general:allow_tearing"]
    if before["misc:vrr"] == 0 and hypr.set_option("misc:vrr", 2):  # 2: full-screen windows only
        changed["misc:vrr"] = 0
    rule = hypr.window_rule(RULE, {"fullscreen": True}, immediate=True)
    return {"lowlat": changed, "lowlat_rule": rule} if (changed or rule) else {}


def low_latency_end(undo: dict):
    changed = (undo or {}).get("lowlat") or {}
    for path, value in changed.items():
        hypr.set_option(path, value)
    if (undo or {}).get("lowlat_rule"):
        if hypr.lua():
            hypr.window_rule(RULE, {"fullscreen": True}, immediate=False)  # same name: replaces it
        else:
            hypr.reload()  # classic keyword rules cannot be taken back one by one


def _pw(*args):
    if not host.which("pw-metadata"):
        return None
    try:
        r = subprocess.run(host.argv(["pw-metadata", "-n", "settings", *args]), capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout if r.returncode == 0 else None


def audio_begin() -> dict:
    return {"quantum": True} if _pw("0", "clock.force-quantum", str(QUANTUM)) is not None else {}


def audio_end(undo: dict):
    if (undo or {}).get("quantum"):
        _pw("0", "clock.force-quantum", "0")  # 0: PipeWire chooses again


def hdr_begin() -> dict:
    """HDR on the screen in front while the game plays (Hyprland), when that screen can show it."""
    if not hypr.running():
        return {}
    m = next((x for x in hypr.monitors() if x.get("focused")), None)
    if not m or (m.get("colorManagementPreset") or "") == "hdr" or not hypr.edid_hdr(m["name"]):
        return {}
    bits = 10 if "2101010" in (m.get("currentFormat") or "") else 8
    if not hypr.set_color(m, "hdr", 10):
        return {}
    return {"hdr": {"name": m["name"], "preset": m.get("colorManagementPreset") or "srgb", "bits": bits}}


def hdr_end(undo: dict):
    was = (undo or {}).get("hdr")
    if not was:
        return
    m = next((x for x in hypr.monitors() if x.get("name") == was["name"]), None)
    if m:
        hypr.set_color(m, was["preset"], was["bits"])
