"""A virtual keyboard and mouse (Linux uinput), for playing keyboard-only games with a controller
(padkeys.py). No extra Python packages: the device is made with a few ioctls.

/dev/uinput must be writable by you. Steam's udev rules (the steam-devices package, or Steam
itself) already allow it on most gaming PCs; otherwise a rule such as
  KERNEL=="uinput", SUBSYSTEM=="misc", TAG+="uaccess", OPTIONS+="static_node=uinput"
in /etc/udev/rules.d/60-uinput.rules does.
"""
import fcntl
import os
import struct
import time

EV_SYN, EV_KEY, EV_REL = 0, 1, 2
REL_X, REL_Y, REL_HWHEEL, REL_WHEEL = 0, 1, 6, 8
BTN_LEFT, BTN_RIGHT, BTN_MIDDLE = 0x110, 0x111, 0x112

UI_SET_EVBIT, UI_SET_KEYBIT, UI_SET_RELBIT = 0x40045564, 0x40045565, 0x40045566
UI_DEV_CREATE, UI_DEV_DESTROY = 0x5501, 0x5502

# The keys a layout can send, by the name shown in Cornerplay (Linux key codes).
KEYS = {
    "Esc": 1, "1": 2, "2": 3, "3": 4, "4": 5, "5": 6, "6": 7, "7": 8, "8": 9, "9": 10, "0": 11,
    "-": 12, "=": 13, "Backspace": 14, "Tab": 15, "Q": 16, "W": 17, "E": 18, "R": 19, "T": 20, "Y": 21,
    "U": 22, "I": 23, "O": 24, "P": 25, "[": 26, "]": 27, "Enter": 28, "Ctrl": 29, "A": 30, "S": 31,
    "D": 32, "F": 33, "G": 34, "H": 35, "J": 36, "K": 37, "L": 38, ";": 39, "'": 40, "`": 41, "Shift": 42,
    "\\": 43, "Z": 44, "X": 45, "C": 46, "V": 47, "B": 48, "N": 49, "M": 50, ",": 51, ".": 52, "/": 53,
    "Alt": 56, "Space": 57, "Caps Lock": 58, "F1": 59, "F2": 60, "F3": 61, "F4": 62, "F5": 63, "F6": 64,
    "F7": 65, "F8": 66, "F9": 67, "F10": 68, "F11": 87, "F12": 88, "Home": 102, "Up": 103, "Page Up": 104,
    "Left": 105, "Right": 106, "End": 107, "Down": 108, "Page Down": 109, "Insert": 110, "Delete": 111,
}
MOUSE = {"Left click": BTN_LEFT, "Right click": BTN_RIGHT, "Middle click": BTN_MIDDLE}
_EVENT = struct.Struct("llHHi")


class Device:
    """One virtual keyboard + mouse. Raises OSError when /dev/uinput cannot be used."""

    def __init__(self, name="Cornerplay controller as keyboard and mouse"):
        self.fd = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
        try:
            for ev in (EV_KEY, EV_REL):
                fcntl.ioctl(self.fd, UI_SET_EVBIT, ev)
            for code in list(KEYS.values()) + list(MOUSE.values()):
                fcntl.ioctl(self.fd, UI_SET_KEYBIT, code)
            for rel in (REL_X, REL_Y, REL_WHEEL, REL_HWHEEL):
                fcntl.ioctl(self.fd, UI_SET_RELBIT, rel)
            # struct uinput_user_dev: name[80], input_id (bustype, vendor, product, version),
            # ff_effects_max, then absmax/absmin/absfuzz/absflat[64] (unused here).
            dev = struct.pack("80sHHHHi", name.encode()[:79], 0x03, 0x1209, 0xC0E1, 1, 0) + bytes(4 * 64 * 4)
            os.write(self.fd, dev)
            fcntl.ioctl(self.fd, UI_DEV_CREATE)
        except OSError:
            os.close(self.fd)
            raise
        self.down = set()

    def _emit(self, kind, code, value):
        now = time.time()
        os.write(self.fd, _EVENT.pack(int(now), int((now % 1) * 1e6), kind, code, value))

    def _sync(self):
        self._emit(EV_SYN, 0, 0)

    def key(self, code, down):
        if down == (code in self.down):
            return
        (self.down.add if down else self.down.discard)(code)
        self._emit(EV_KEY, code, 1 if down else 0)
        self._sync()

    def move(self, dx, dy):
        if dx:
            self._emit(EV_REL, REL_X, int(dx))
        if dy:
            self._emit(EV_REL, REL_Y, int(dy))
        if dx or dy:
            self._sync()

    def wheel(self, steps, horizontal=False):
        self._emit(EV_REL, REL_HWHEEL if horizontal else REL_WHEEL, int(steps))
        self._sync()

    def release_all(self):
        for code in list(self.down):
            self.key(code, False)

    def close(self):
        try:
            self.release_all()
            fcntl.ioctl(self.fd, UI_DEV_DESTROY)
        except OSError:
            pass
        os.close(self.fd)


def available() -> bool:
    return os.access("/dev/uinput", os.W_OK)
