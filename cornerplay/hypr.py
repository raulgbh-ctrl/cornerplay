"""Talking to Hyprland at runtime, in either of its configuration languages.

Classic Hyprland takes `hyprctl keyword section:key value` and `hyprctl dispatch workspace 3`.
Hyprland built with Lua configuration (Ryoku's) answers "unknown request" to keyword and reads
dispatch arguments as Lua; there `hyprctl eval 'hl.config({...})'`, `hl.monitor({...})`,
`hl.window_rule({...})` and `hyprctl dispatch 'hl.dsp.focus({ workspace = "3" })'` do the same.
Nothing here is saved to the user's config: a reload puts everything back.
"""
import json
import os
import subprocess

from . import host

_lua = None


def running() -> bool:
    return bool(os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")) and bool(host.which("hyprctl"))


def ctl(*args, timeout=5):
    """hyprctl's answer, or None when it failed or Hyprland is not running."""
    if not running():
        return None
    try:
        r = subprocess.run(host.argv(["hyprctl", *args]), capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    out = (r.stdout or "").strip()
    if r.returncode != 0 or out.startswith(("unknown request", "error")):
        return None
    return r.stdout


def lua() -> bool:
    """Hyprland with Lua configuration (asked once)."""
    global _lua
    if _lua is None:
        _lua = running() and ctl("eval", "return 1") is not None
    return bool(_lua)


def _lua_value(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, dict):
        return "{ " + ", ".join(f"{k} = {_lua_value(x)}" for k, x in v.items()) + " }"
    return json.dumps(str(v))  # a quoted Lua string (JSON's escaping is valid Lua)


def option(path: str):
    """An option's current value ("misc:vrr" -> 0), or None."""
    out = ctl("getoption", path, "-j")
    try:
        d = json.loads(out or "")
    except ValueError:
        return None
    for k in ("bool", "int", "float", "str", "custom"):
        if k in d:
            return d[k]
    return None


def set_option(path: str, value) -> bool:
    """"misc:vrr", 2 -> set for now (not saved)."""
    if lua():
        section, _, key = path.partition(":")
        return ctl("eval", f"hl.config({{ {section} = {{ {key} = {_lua_value(value)} }} }})") is not None
    if isinstance(value, bool):
        value = "true" if value else "false"
    return ctl("keyword", path, str(value)) is not None


def window_rule(name: str, match: dict, **props) -> bool:
    """A window rule for now. Lua: replaced by a later rule of the same name."""
    if lua():
        rule = dict({"name": name, "match": match}, **props)
        return ctl("eval", f"hl.window_rule({_lua_value(rule)})") is not None
    effects = ", ".join(k if v is True else f"{k} {v}" for k, v in props.items() if v is not False)
    matches = ", ".join(f"{k}:{int(v) if isinstance(v, bool) else v}" for k, v in match.items())
    return bool(effects) and ctl("keyword", "windowrulev2", f"{effects}, {matches}") is not None


def monitor(name, mode, x, y, scale, transform=0) -> bool:
    if lua():
        m = {"output": name, "mode": mode, "position": f"{x}x{y}", "scale": scale}
        if transform:
            m["transform"] = transform
        return ctl("eval", f"hl.monitor({_lua_value(m)})") is not None
    rule = f"{name},{mode},{x}x{y},{scale:g}" + (f",transform,{transform}" if transform else "")
    return ctl("keyword", "monitor", rule) is not None


def monitors() -> list:
    try:
        return json.loads(ctl("monitors", "-j") or "[]")
    except ValueError:
        return []


def workspace() -> str:
    """The active workspace's name ("1", "special:x")."""
    try:
        return str(json.loads(ctl("activeworkspace", "-j") or "{}").get("name") or "")
    except ValueError:
        return ""


def focus_workspace(ws: str) -> bool:
    """Go to a workspace by name, or "empty" (the first empty one)."""
    if lua():
        return ctl("dispatch", f"hl.dsp.focus({{ workspace = {json.dumps(ws)} }})") is not None
    return ctl("dispatch", "workspace", ws) is not None


def clients() -> list:
    """Every window: [{"address", "class", "title", "workspace": {"name"}, ...}]."""
    try:
        return json.loads(ctl("clients", "-j") or "[]")
    except ValueError:
        return []


def move_window(address: str, workspace: str, silent: bool = True) -> bool:
    """Send one window (by address) to a workspace ("special:x", "3"); silent: stay where you are."""
    ws = workspace + (" silent" if silent and lua() else "")
    if lua():
        return ctl("dispatch", f"hl.dsp.window.move({{ workspace = {json.dumps(ws)}, window = {json.dumps('address:' + address)} }})") is not None
    return ctl("dispatch", "movetoworkspacesilent" if silent else "movetoworkspace", f"{workspace},address:{address}") is not None


def focus_window(address: str) -> bool:
    if lua():
        return ctl("dispatch", f"hl.dsp.focus({{ window = {json.dumps('address:' + address)} }})") is not None
    return ctl("dispatch", "focuswindow", f"address:{address}") is not None


def reload() -> bool:
    return ctl("reload") is not None


def edid_hdr(output: str) -> bool:
    """The screen says it can show HDR: its EDID has CTA-861's HDR static metadata block."""
    import glob
    for path in glob.glob(f"/sys/class/drm/card*-{output}/edid"):
        try:
            edid = open(path, "rb").read()
        except OSError:
            continue
        for start in range(128, len(edid) - 127, 128):  # extension blocks
            block = edid[start:start + 128]
            if block[0] != 0x02:  # CTA-861
                continue
            end = block[2] if 4 <= block[2] <= 127 else 4
            i = 4
            while i < end:
                tag, length = block[i] >> 5, block[i] & 0x1F
                if tag == 7 and length >= 1 and block[i + 1] == 0x06:  # extended tag 6: HDR static metadata
                    return True
                i += 1 + length
    return False


def set_color(m: dict, preset: str, bitdepth: int) -> bool:
    """A screen's colour mode ("hdr" / "srgb") and bit depth, keeping its mode and place."""
    mode = f"{m['width']}x{m['height']}@{float(m['refreshRate']):.2f}"
    if lua():
        rule = {"output": m["name"], "mode": mode, "position": f"{m['x']}x{m['y']}", "scale": m["scale"],
                "cm": preset, "bitdepth": bitdepth}
        if m.get("transform"):
            rule["transform"] = m["transform"]
        return ctl("eval", f"hl.monitor({_lua_value(rule)})") is not None
    rule = f"{m['name']},{mode},{m['x']}x{m['y']},{m['scale']:g},bitdepth,{bitdepth},cm,{preset}"
    if m.get("transform"):
        rule += f",transform,{m['transform']}"
    return ctl("keyword", "monitor", rule) is not None
