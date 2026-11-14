"""The PC's own controls for TV mode's quick access and settings, like SteamOS's Game Mode:
volume and the sound output, screen brightness, Wi-Fi, Bluetooth, the power profile, and
gamescope's live display settings (frame limit, refresh rate, scaling, sharpness, tearing, HDR).

Everything goes through the desktop's usual tools (wpctl / pactl, brightnessctl, nmcli,
bluetoothctl, powerprofilesctl, xprop), on the host when Cornerplay is a Flatpak. A tool that is
missing just leaves its part out of the state: the menus show only what this PC can do.
All calls block; Cornerplay runs them on one worker thread, in order.
"""
import json
import os
import re
import subprocess

from . import host

SINK = "@DEFAULT_AUDIO_SINK@"
SOURCE = "@DEFAULT_AUDIO_SOURCE@"

# gamescope's enums (src/main.hpp): the upscale filter and how the picture is fitted.
FILTERS = ["linear", "nearest", "fsr", "nis", "pixel"]
SCALERS = ["auto", "integer", "fit", "fill", "stretch"]
# What Cornerplay remembers and sets again when a gamescope session starts: setting -> atom.
GS_SETTINGS = {
    "gs_fps_limit": "GAMESCOPE_FPS_LIMIT",
    "gs_filter": "GAMESCOPE_NEW_SCALING_FILTER",
    "gs_scaler": "GAMESCOPE_NEW_SCALING_SCALER",
    "gs_sharpness": "GAMESCOPE_FSR_SHARPNESS",
    "gs_tearing": "GAMESCOPE_ALLOW_TEARING",
    "gs_hdr": "GAMESCOPE_DISPLAY_HDR_ENABLED",
}


def _run(cmd, timeout=6) -> str | None:
    """stdout of a host command, or None when it is missing, fails or hangs."""
    if not host.which(cmd[0]):
        return None
    try:
        r = subprocess.run(host.argv(cmd), capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout if r.returncode == 0 else None


def _ok(cmd, timeout=6) -> bool:
    return _run(cmd, timeout) is not None


# ---------------------------------------------------------------- sound
def audio() -> dict:
    out = _run(["wpctl", "get-volume", SINK])
    if out is None:
        return {}
    m = re.search(r"([\d.]+)", out)
    state = {"volume": round(float(m.group(1)) * 100) if m else 0, "muted": "MUTED" in out}
    mic = _run(["wpctl", "get-volume", SOURCE])
    if mic is not None:
        state["micMuted"] = "MUTED" in mic
    sinks = _run(["pactl", "-f", "json", "list", "sinks"])
    default = (_run(["pactl", "get-default-sink"]) or "").strip()
    if sinks:
        try:
            state["outputs"] = [{"id": s["name"], "name": s.get("description") or s["name"]}
                                for s in json.loads(sinks) if s.get("name")]
        except (ValueError, KeyError, TypeError):
            state["outputs"] = []
        state["output"] = default
    return state


def set_volume(pct: int) -> bool:
    pct = max(0, min(100, int(pct)))
    ok = _ok(["wpctl", "set-volume", "-l", "1.0", SINK, f"{pct / 100:.2f}"])
    if ok and pct > 0:
        _ok(["wpctl", "set-mute", SINK, "0"])  # turning it up unmutes, like a TV
    return ok


def set_muted(muted: bool) -> bool:
    return _ok(["wpctl", "set-mute", SINK, "1" if muted else "0"])


def set_mic_muted(muted: bool) -> bool:
    return _ok(["wpctl", "set-mute", SOURCE, "1" if muted else "0"])


def set_output(sink: str) -> bool:
    return _ok(["pactl", "set-default-sink", sink])


# ---------------------------------------------------------------- screen brightness
def brightness() -> int | None:
    """The built-in screen's backlight in percent; None on a desktop or a TV."""
    out = _run(["brightnessctl", "-m", "-c", "backlight", "info"])
    if not out:
        return None
    parts = out.strip().splitlines()[0].split(",")
    try:
        return int(parts[3].rstrip("%"))
    except (IndexError, ValueError):
        return None


def set_brightness(pct: int) -> bool:
    return _ok(["brightnessctl", "-q", "-c", "backlight", "set", f"{max(5, min(100, int(pct)))}%"])


# ---------------------------------------------------------------- Wi-Fi and network
def _split(line: str) -> list:
    """nmcli -t fields: ':' separates, '\\:' is a colon inside one."""
    return [p.replace("\\:", ":") for p in re.split(r"(?<!\\):", line)]


def network(scan: bool = False) -> dict:
    radio = _run(["nmcli", "-t", "-f", "WIFI", "general"])
    if radio is None:
        return {}
    state = {"wifi": radio.strip() == "enabled", "networks": [], "wired": False, "ssid": ""}
    for line in (_run(["nmcli", "-t", "-f", "TYPE,STATE,CONNECTION", "device"]) or "").splitlines():
        f = _split(line)
        if len(f) >= 3 and f[0] == "ethernet" and f[1] == "connected":
            state["wired"] = True
    if not state["wifi"]:
        return state
    saved = set()
    for line in (_run(["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show"]) or "").splitlines():
        f = _split(line)
        if len(f) >= 2 and f[1] == "802-11-wireless":
            saved.add(f[0])
    out = _run(["nmcli", "-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY", "device", "wifi", "list",
                "--rescan", "yes" if scan else "no"], timeout=20 if scan else 6) or ""
    seen = {}
    for line in out.splitlines():
        f = _split(line)
        if len(f) < 4 or not f[1]:
            continue
        net = {"ssid": f[1], "signal": int(f[2] or 0), "secure": f[3] not in ("", "--"),
               "active": f[0] == "*", "saved": f[1] in saved}
        old = seen.get(net["ssid"])
        if not old or net["active"] or (net["signal"] > old["signal"] and not old["active"]):
            seen[net["ssid"]] = net
    nets = sorted(seen.values(), key=lambda n: (not n["active"], not n["saved"], -n["signal"]))
    state["networks"] = nets[:12]
    state["ssid"] = next((n["ssid"] for n in nets if n["active"]), "")
    return state


def set_wifi(on: bool) -> bool:
    return _ok(["nmcli", "radio", "wifi", "on" if on else "off"])


def connect_wifi(ssid: str, password: str = "", saved: bool = False) -> str:
    """"" when connected, else nmcli's reason in a few words."""
    cmd = (["nmcli", "connection", "up", "id", ssid] if saved and not password
           else ["nmcli", "device", "wifi", "connect", ssid] + (["password", password] if password else []))
    if not host.which("nmcli"):
        return "nmcli is not installed"
    try:
        r = subprocess.run(host.argv(cmd), capture_output=True, text=True, timeout=45)
    except (OSError, subprocess.TimeoutExpired):
        return "it took too long"
    if r.returncode == 0:
        return ""
    msg = (r.stderr or r.stdout).strip().splitlines()
    text = msg[-1] if msg else "it did not connect"
    if "Secrets were required" in text or "802-11-wireless-security.psk" in text or "password" in text.lower():
        return "wrong password"
    return re.sub(r"^Error:\s*", "", text)[:90]


def disconnect_wifi(ssid: str) -> bool:
    return _ok(["nmcli", "connection", "down", "id", ssid], timeout=15)


def forget_wifi(ssid: str) -> bool:
    return _ok(["nmcli", "connection", "delete", "id", ssid], timeout=15)


# ---------------------------------------------------------------- Bluetooth
def _devices(which: str = "") -> list:
    out = _run(["bluetoothctl", "devices"] + ([which] if which else [])) or ""
    found = []
    for line in out.splitlines():
        m = re.match(r"Device\s+([0-9A-F:]{17})\s+(.*)", line.strip())
        if m:
            found.append({"mac": m.group(1), "name": m.group(2).strip()})
    return found


def bluetooth() -> dict:
    out = _run(["bluetoothctl", "show"], timeout=4)
    if out is None or "Controller" not in out:
        return {}
    state = {"on": bool(re.search(r"Powered:\s*yes", out)), "devices": []}
    if not state["on"]:
        return state
    connected = {d["mac"] for d in _devices("Connected")}
    for d in _devices("Paired"):
        d["connected"] = d["mac"] in connected
        d["paired"] = True
        state["devices"].append(d)
    state["devices"].sort(key=lambda d: (not d["connected"], d["name"].lower()))
    return state


def set_bluetooth(on: bool) -> bool:
    if on and host.which("rfkill"):
        _run(["rfkill", "unblock", "bluetooth"])
    return _ok(["bluetoothctl", "power", "on" if on else "off"])


def bt_connect(mac: str, connect: bool = True) -> bool:
    out = _run(["bluetoothctl", "connect" if connect else "disconnect", mac], timeout=20) or ""
    return "successful" in out.lower() or (not connect and out != "")


def bt_scan(seconds: int = 10) -> list:
    """Devices nearby that are not paired yet (a controller in pairing mode, headphones)."""
    paired = {d["mac"] for d in _devices("Paired")}
    _run(["bluetoothctl", "--timeout", str(seconds), "scan", "on"], timeout=seconds + 5)
    near = []
    for d in _devices():
        # Unnamed devices show their address with dashes as the name: nothing to recognise them by.
        if d["mac"] not in paired and not re.fullmatch(r"[0-9A-F]{2}(-[0-9A-F]{2}){5}", d["name"]):
            d.update(connected=False, paired=False)
            near.append(d)
    return near


def bt_pair(mac: str) -> bool:
    _run(["bluetoothctl", "--timeout", "20", "pair", mac], timeout=25)
    _run(["bluetoothctl", "trust", mac])
    return bt_connect(mac, True)


def bt_forget(mac: str) -> bool:
    return _ok(["bluetoothctl", "remove", mac])


# ---------------------------------------------------------------- power
def power_profiles() -> dict:
    cur = _run(["powerprofilesctl", "get"])
    if cur is None:
        return {}
    names = re.findall(r"^\*?\s*([\w-]+):\s*$", _run(["powerprofilesctl", "list"]) or "", re.M)
    return {"profile": cur.strip(), "profiles": names or ["power-saver", "balanced", "performance"]}


def set_power_profile(name: str) -> bool:
    return _ok(["powerprofilesctl", "set", name])


# ---------------------------------------------------------------- gamescope
def in_gamescope() -> bool:
    return (os.environ.get("XDG_CURRENT_DESKTOP", "").lower() == "gamescope"
            or bool(os.environ.get("GAMESCOPE_WAYLAND_DISPLAY")))


def _xprop_read(atoms) -> dict:
    out = _run(["xprop", "-root", *atoms], timeout=3) or ""
    vals = {}
    for line in out.splitlines():
        m = re.match(r"(\w+)\((\w+)\) = (.*)", line)
        if not m:
            continue
        raw = m.group(3).strip()
        if m.group(2) == "STRING" or raw.startswith('"'):
            vals[m.group(1)] = raw.strip('"')
        else:
            nums = [int(x) for x in re.findall(r"-?\d+", raw)]
            vals[m.group(1)] = nums[0] if len(nums) == 1 else nums
    return vals


def gs_set(atom: str, value) -> bool:
    """Set (or with None, clear) one of gamescope's root-window properties. It takes effect at once."""
    if value is None:
        return _ok(["xprop", "-root", "-remove", atom], timeout=3)
    return _ok(["xprop", "-root", "-f", atom, "32c", "-set", atom, str(int(value))], timeout=3)


def gamescope() -> dict:
    """gamescope's live settings, when Cornerplay runs inside it (the Cornerplay (TV) session)."""
    if not in_gamescope() or not host.which("xprop") or not os.environ.get("DISPLAY"):
        return {}
    v = _xprop_read(list(GS_SETTINGS.values()) + [
        "GAMESCOPE_DISPLAY_REFRESH_RATE_FEEDBACK", "GAMESCOPE_DISPLAY_SUPPORTS_HDR",
        "GAMESCOPE_DISPLAY_IS_EXTERNAL", "GAMESCOPE_DISPLAY_MODE_LIST_EXTERNAL",
        "GAMESCOPE_DYNAMIC_REFRESH", "GAMESCOPE_DYNAMIC_REFRESH_EXTERNAL"])
    refresh = v.get("GAMESCOPE_DISPLAY_REFRESH_RATE_FEEDBACK") or 60
    external = bool(v.get("GAMESCOPE_DISPLAY_IS_EXTERNAL"))
    rates = sorted({int(r) for r in re.findall(r"@(\d+)", str(v.get("GAMESCOPE_DISPLAY_MODE_LIST_EXTERNAL", "")))})
    if not external and not rates:
        rates = []  # a built-in panel: gamescope only knows its rates when started with them
    refresh_atom = "GAMESCOPE_DYNAMIC_REFRESH_EXTERNAL" if external else "GAMESCOPE_DYNAMIC_REFRESH"
    return {
        "active": True,
        "refresh": int(refresh) if isinstance(refresh, int) else 60,
        "refreshTarget": v.get(refresh_atom) or 0,
        "refreshAtom": refresh_atom,
        "rates": rates,
        "fpsLimit": v.get("GAMESCOPE_FPS_LIMIT") or 0,
        "filter": FILTERS[v.get("GAMESCOPE_NEW_SCALING_FILTER") or 0] if (v.get("GAMESCOPE_NEW_SCALING_FILTER") or 0) < len(FILTERS) else "linear",
        "scaler": SCALERS[v.get("GAMESCOPE_NEW_SCALING_SCALER") or 0] if (v.get("GAMESCOPE_NEW_SCALING_SCALER") or 0) < len(SCALERS) else "auto",
        # FSR / NIS sharpness: gamescope counts 0 (sharpest) to 20; shown here as 0..20, higher sharper.
        "sharpness": 20 - int(v.get("GAMESCOPE_FSR_SHARPNESS", 2) if isinstance(v.get("GAMESCOPE_FSR_SHARPNESS", 2), int) else 2),
        "tearing": bool(v.get("GAMESCOPE_ALLOW_TEARING")),
        "hdrSupported": bool(v.get("GAMESCOPE_DISPLAY_SUPPORTS_HDR")),
        "hdr": bool(v.get("GAMESCOPE_DISPLAY_HDR_ENABLED")),
    }


def gs_value(setting: str, value):
    """A Cornerplay setting's value as the atom wants it (None clears the atom: gamescope's default)."""
    if setting == "gs_filter":
        return FILTERS.index(value) if value in FILTERS and value != "linear" else None
    if setting == "gs_scaler":
        return SCALERS.index(value) if value in SCALERS and value != "auto" else None
    if setting == "gs_sharpness":
        return None if value in (None, "") else 20 - max(0, min(20, int(value)))
    if setting in ("gs_tearing", "gs_hdr"):
        return 1 if value else None
    return int(value) if value else None  # frame limit / refresh: 0 = off


def gs_apply(setting: str, value, atom: str = "") -> bool:
    atom = atom or GS_SETTINGS.get(setting, "")
    return bool(atom) and gs_set(atom, gs_value(setting, value))


def gs_restore(saved: dict):
    """A new gamescope session: put back what was chosen last time."""
    if not gamescope():
        return
    for setting, atom in GS_SETTINGS.items():
        val = saved.get(setting)
        if val not in (None, "", 0, False):
            gs_set(atom, gs_value(setting, val))


def state(scan: bool = False) -> dict:
    """Everything at once, for the menus. Keys are left out for what this PC cannot do."""
    return {
        "audio": audio(),
        "brightness": brightness(),
        "network": network(scan),
        "bluetooth": bluetooth(),
        "power": power_profiles(),
        "gamescope": gamescope(),
    }
