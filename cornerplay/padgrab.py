"""Taking a controller away from the game for a moment, the way Steam Input does: while quick
access is open over a game, or a keyboard layout (padkeys.py) is steering it, the pad's evdev
device is grabbed (EVIOCGRAB), so the game stops seeing its buttons. Cornerplay then reads the
grabbed device itself and turns what it reads into SDL's buttons and axes, through the pad's
own SDL mapping string, so every button still means the same thing.

Pads SDL reads through hidraw (PlayStation, Switch, Steam: HIDAPI) keep coming to Cornerplay
that way; their evdev device is grabbed too (games reading evdev stop seeing it) and only
drained. A game that reads the same hidraw device itself still sees those pads.
"""
import fcntl
import glob
import os
import re
import struct

EVIOCGRAB = 0x40044590
EV_KEY, EV_ABS = 1, 3
BTN_MISC, BTN_JOYSTICK, KEY_MAX = 0x100, 0x120, 0x2FF
ABS_HAT0X, ABS_HAT3Y, ABS_MAX = 0x10, 0x17, 0x3F
_EVENT = struct.Struct("llHHi")
# SDL_GameControllerButton / SDL_GameControllerAxis numbers, by the mapping's names.
BUTTONS = {"a": 0, "b": 1, "x": 2, "y": 3, "back": 4, "guide": 5, "start": 6, "leftstick": 7, "rightstick": 8,
           "leftshoulder": 9, "rightshoulder": 10, "dpup": 11, "dpdown": 12, "dpleft": 13, "dpright": 14,
           "misc1": 15, "paddle1": 16, "paddle2": 17, "paddle3": 18, "paddle4": 19, "touchpad": 20}
AXES = {"leftx": 0, "lefty": 1, "rightx": 2, "righty": 3, "lefttrigger": 4, "righttrigger": 5}


def _ioc_read(nr, size):
    return 0x80000000 | (size << 16) | (ord("E") << 8) | nr


def _bits(fd, ev, count):
    buf = bytearray((count + 7) // 8)
    fcntl.ioctl(fd, _ioc_read(0x20 + ev, len(buf)), buf)
    return [i for i in range(count) if buf[i // 8] >> (i % 8) & 1]


def evdev_for(path):
    """The evdev node for SDL's device path: itself, or a hidraw device's sibling."""
    if re.match(r"/dev/input/event\d+$", path or ""):
        return path, True
    m = re.match(r"/dev/(hidraw\d+)$", path or "")
    if m:
        for node in glob.glob(f"/sys/class/hidraw/{m.group(1)}/device/input/input*/event*"):
            return "/dev/input/" + os.path.basename(node), False
    return None, False


class Grab:
    """One grabbed pad. read() returns SDL-style events: ("button", n, down) or ("axis", n, value)."""

    def __init__(self, path, mapping, translate=True):
        self.fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
        try:
            fcntl.ioctl(self.fd, EVIOCGRAB, 1)
        except OSError:
            os.close(self.fd)
            raise
        self.translate = translate
        self.hats = [0] * 8
        self.ranges = {}
        self.button_of, self.axis_of, self.hat_of = {}, {}, {}
        if translate:
            self._learn(mapping)

    def _learn(self, mapping):
        """SDL numbers evdev buttons from BTN_JOYSTICK upward, then BTN_MISC, and the axes in
        code order without the hats: the mapping string's b<n> / a<n> / h<n>.<bit> follow that."""
        keys = _bits(self.fd, EV_KEY, KEY_MAX + 1)
        order = [k for k in keys if k >= BTN_JOYSTICK] + [k for k in keys if BTN_MISC <= k < BTN_JOYSTICK]
        absc = _bits(self.fd, EV_ABS, ABS_MAX + 1)
        axes = [a for a in absc if not ABS_HAT0X <= a <= ABS_HAT3Y]
        for a in absc:
            info = bytearray(24)
            try:
                fcntl.ioctl(self.fd, _ioc_read(0x40 + a, 24), info)
                _v, lo, hi = struct.unpack_from("iii", info)
                self.ranges[a] = (lo, hi)
            except OSError:
                self.ranges[a] = (-32768, 32767)
        for part in mapping.split(",")[2:]:
            name, _, src = part.partition(":")
            src = src.lstrip("+-~")
            if name in BUTTONS:
                if src.startswith("b") and src[1:].isdigit() and int(src[1:]) < len(order):
                    self.button_of[order[int(src[1:])]] = BUTTONS[name]
                elif src.startswith("h") and "." in src:
                    hat, bit = src[1:].split(".")
                    self.hat_of[(int(hat), int(bit))] = BUTTONS[name]
                elif src.startswith("a") and src[1:].isdigit() and int(src[1:]) < len(axes):
                    self.axis_of[axes[int(src[1:])]] = ("button", BUTTONS[name])
            elif name in AXES and src.startswith("a") and src[1:].isdigit() and int(src[1:]) < len(axes):
                self.axis_of[axes[int(src[1:])]] = ("axis", AXES[name])

    def _scale(self, code, value, trigger):
        lo, hi = self.ranges.get(code, (-32768, 32767))
        if hi <= lo:
            return 0
        f = (value - lo) / (hi - lo)
        return int(f * 32767) if trigger else int(f * 65535 - 32768)

    def read(self):
        out = []
        while True:
            try:
                data = os.read(self.fd, _EVENT.size * 64)
            except BlockingIOError:
                break
            except OSError:
                break
            if not data:
                break
            if not self.translate:
                continue  # SDL reads this pad through hidraw: only keep the game away from it
            for i in range(0, len(data) - _EVENT.size + 1, _EVENT.size):
                _s, _u, kind, code, value = _EVENT.unpack_from(data, i)
                if kind == EV_KEY and code in self.button_of:
                    out.append(("button", self.button_of[code], bool(value)))
                elif kind == EV_ABS and ABS_HAT0X <= code <= ABS_HAT3Y:
                    hat, ycoord = (code - ABS_HAT0X) // 2, (code - ABS_HAT0X) % 2
                    old = self.hats[hat]
                    bits = old & (0b1010 if ycoord else 0b0101)  # keep the other direction's bits
                    if ycoord:
                        bits |= 1 if value < 0 else 4 if value > 0 else 0   # up 1, down 4
                    else:
                        bits |= 8 if value < 0 else 2 if value > 0 else 0   # left 8, right 2
                    self.hats[hat] = bits
                    for bit in (1, 2, 4, 8):
                        if (old ^ bits) & bit and (hat, bit) in self.hat_of:
                            out.append(("button", self.hat_of[(hat, bit)], bool(bits & bit)))
                elif kind == EV_ABS and code in self.axis_of:
                    what, n = self.axis_of[code]
                    if what == "axis":
                        out.append(("axis", n, self._scale(code, value, n in (4, 5))))
                    else:
                        out.append(("button", n, self._scale(code, value, True) > 16000))
        return out

    def close(self):
        try:
            fcntl.ioctl(self.fd, EVIOCGRAB, 0)
        except OSError:
            pass
        os.close(self.fd)
