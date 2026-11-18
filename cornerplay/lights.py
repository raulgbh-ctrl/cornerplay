"""Room lights in the game's colour: OpenRGB (keyboards, mice, fans, LED strips on this PC) or
Philips Hue lights, following the game in focus in TV mode and the game being played
(Settings > TV mode > Lights).

OpenRGB: its SDK server (OpenRGB's SDK Server tab, or `openrgb --server`) on 127.0.0.1:6742.
Each device is put in its custom ("direct") mode and every LED gets the colour.
Hue: the bridge's local API. Pairing presses the bridge's round button, then Pair: the
bridge gives Cornerplay a user name, kept in the settings. All lights (group 0) or one room.
Every call is short and runs off the UI thread; a missing server or bridge is quietly skipped.
"""
import socket
import struct

from .net import requests

OPENRGB = ("127.0.0.1", 6742)
MAGIC = b"ORGB"
REQUEST_CONTROLLER_COUNT = 0
REQUEST_CONTROLLER_DATA = 1
SET_CLIENT_NAME = 50
SET_CUSTOM_MODE = 1100
UPDATE_LEDS = 1050


def hex_rgb(colour: str):
    c = colour.lstrip("#")[-6:]
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


# --- OpenRGB SDK (protocol 0: every server version speaks it) -----------------------------
def _packet(dev, pid, body=b""):
    return MAGIC + struct.pack("<III", dev, pid, len(body)) + body


def _recv(sock, n):
    out = b""
    while len(out) < n:
        chunk = sock.recv(n - len(out))
        if not chunk:
            raise OSError("closed")
        out += chunk
    return out


def _reply(sock):
    head = _recv(sock, 16)
    if head[:4] != MAGIC:
        raise OSError("not OpenRGB")
    _dev, _pid, size = struct.unpack("<III", head[4:])
    return _recv(sock, size)


class _Reader:
    def __init__(self, data, at=0):
        self.d, self.i = data, at

    def u16(self):
        v = struct.unpack_from("<H", self.d, self.i)[0]
        self.i += 2
        return v

    def u32(self):
        v = struct.unpack_from("<I", self.d, self.i)[0]
        self.i += 4
        return v

    def text(self):
        n = self.u16()
        s = self.d[self.i:self.i + n].rstrip(b"\0").decode("utf-8", "replace")
        self.i += n
        return s


def led_count(data: bytes) -> int:
    """How many LEDs a controller has, from its CONTROLLER_DATA reply (protocol 0)."""
    r = _Reader(data)
    r.u32()          # data size
    r.u32()          # device type
    for _ in range(5):
        r.text()     # name, description, version, serial, location
    modes = r.u16()
    r.u32()          # active mode
    for _ in range(modes):
        r.text()
        r.u32(); r.u32(); r.u32(); r.u32(); r.u32(); r.u32(); r.u32(); r.u32(); r.u32()  # value .. color mode
        n = r.u16()          # the mode's colours (read first: `r.i += 4 * r.u16()` would lose the u16)
        r.i += 4 * n
    zones = r.u16()
    for _ in range(zones):
        r.text()
        r.u32(); r.u32(); r.u32(); r.u32()  # type, leds min, max, count
        if r.u16():                          # a matrix: height, width, then its map
            h, w = r.u32(), r.u32()
            r.i += 4 * h * w
    return r.u16()


def openrgb_set(rgb, addr=OPENRGB, timeout=1.5) -> int:
    """Every OpenRGB device to one colour. Returns how many devices took it."""
    red, green, blue = rgb
    colour = struct.pack("<BBBB", red, green, blue, 0)
    done = 0
    with socket.create_connection(addr, timeout=timeout) as s:
        s.sendall(_packet(0, SET_CLIENT_NAME, b"Cornerplay\0"))
        s.sendall(_packet(0, REQUEST_CONTROLLER_COUNT))
        count = struct.unpack("<I", _reply(s)[:4])[0]
        for dev in range(count):
            s.sendall(_packet(dev, REQUEST_CONTROLLER_DATA))
            leds = led_count(_reply(s))
            if not leds:
                continue
            s.sendall(_packet(dev, SET_CUSTOM_MODE))
            body = struct.pack("<H", leds) + colour * leds
            s.sendall(_packet(dev, UPDATE_LEDS, struct.pack("<I", len(body) + 4) + body))
            done += 1
    return done


# --- Philips Hue ---------------------------------------------------------------------------
def rgb_to_xy(rgb):
    """sRGB to the CIE xy Hue lights take (Philips' published conversion)."""
    def lin(c):
        c /= 255
        return ((c + 0.055) / 1.055) ** 2.4 if c > 0.04045 else c / 12.92
    r, g, b = (lin(c) for c in rgb)
    x = r * 0.664511 + g * 0.154324 + b * 0.162028
    y = r * 0.283881 + g * 0.668433 + b * 0.047685
    z = r * 0.000088 + g * 0.072310 + b * 0.986039
    total = x + y + z
    return (round(x / total, 4), round(y / total, 4)) if total else (0.3227, 0.329)


def hue_pair(bridge: str) -> str:
    """After the bridge's button was pressed: a user name for Cornerplay ("" if not pressed)."""
    r = requests.post(f"http://{bridge}/api", json={"devicetype": "cornerplay#pc"}, timeout=5)
    for item in r.json() or []:
        if "success" in item:
            return item["success"].get("username", "")
    return ""


def hue_set(bridge: str, user: str, rgb, group: str = "0"):
    bri = max(40, min(254, int(max(rgb) * 254 / 255)))
    requests.put(f"http://{bridge}/api/{user}/groups/{group or '0'}/action",
                 json={"on": True, "xy": list(rgb_to_xy(rgb)), "bri": bri, "transitiontime": 4}, timeout=3)


def apply(colour: str, settings_get) -> str:
    """Set the lights the settings name to `colour` ("#rrggbb"). "" or why not."""
    kind = settings_get("lights") or ""
    if not kind or not colour:
        return ""
    rgb = hex_rgb(colour)
    try:
        if kind == "openrgb":
            openrgb_set(rgb)
        elif kind == "hue" and settings_get("hue_bridge") and settings_get("hue_user"):
            hue_set(settings_get("hue_bridge"), settings_get("hue_user"), rgb, settings_get("hue_group") or "0")
    except (OSError, ValueError, requests.RequestException) as e:
        return str(e)
    return ""
