"""Simulated controllers: checks that Cornerplay shows each kind of pad's own button prompts.

    python3 tools/padsim.py            (needs python-evdev and write access to /dev/uinput)

For every family in qml/glyphs.js it plugs in a virtual controller with that pad's real USB
vendor and product ids, lets Cornerplay's gamepad code (SDL) find it, and checks pad.style.
Then it plugs two in at once and presses a button on each: the prompts must follow the pad
that was used last. Prints one line per pad and exits non-zero if any is wrong.
"""
import os
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evdev import AbsInfo, UInput, ecodes as e  # noqa: E402
from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtGui import QGuiApplication  # noqa: E402

# (name the pad gives itself, vendor, product, the prompts Cornerplay should pick)
PADS = [
    ("Microsoft X-Box 360 pad", 0x045E, 0x028E, "xbox360"),
    ("Microsoft X-Box One S pad", 0x045E, 0x02EA, "xbox"),
    ("Xbox Wireless Controller", 0x045E, 0x0B13, "xbox"),
    ("Sony Interactive Entertainment Wireless Controller", 0x054C, 0x0CE6, "ps5"),
    ("Sony Interactive Entertainment Wireless Controller", 0x054C, 0x09CC, "ps4"),
    ("Sony PLAYSTATION(R)3 Controller", 0x054C, 0x0268, "ps3"),
    ("Nintendo Switch Pro Controller", 0x057E, 0x2009, "switch"),
    ("Steam Deck", 0x28DE, 0x1205, "deck"),
    ("Valve Software Steam Controller", 0x28DE, 0x1102, "steam"),
    ("Google LLC Stadia Controller rev. A", 0x18D1, 0x9400, "stadia"),
    ("Amazon Game Controller", 0x1949, 0x0419, "luna"),
    ("NVIDIA Controller v01.04", 0x0955, 0x7214, "shield"),
    ("Generic USB Joystick", 0x0079, 0x0006, "generic"),
]

AXIS = AbsInfo(0, -32768, 32767, 16, 128, 0)
TRIG = AbsInfo(0, 0, 255, 0, 0, 0)
HAT = AbsInfo(0, -1, 1, 0, 0, 0)
CAPS = {e.EV_KEY: [e.BTN_SOUTH, e.BTN_EAST, e.BTN_NORTH, e.BTN_WEST, e.BTN_TL, e.BTN_TR, e.BTN_SELECT,
                   e.BTN_START, e.BTN_MODE, e.BTN_THUMBL, e.BTN_THUMBR],
        e.EV_ABS: [(e.ABS_X, AXIS), (e.ABS_Y, AXIS), (e.ABS_RX, AXIS), (e.ABS_RY, AXIS),
                   (e.ABS_Z, TRIG), (e.ABS_RZ, TRIG), (e.ABS_HAT0X, HAT), (e.ABS_HAT0Y, HAT)]}


def plug(name, vendor, product):
    return UInput(CAPS, name=name, vendor=vendor, product=product, version=0x111, bustype=e.BUS_USB)


def press(dev):
    dev.write(e.EV_KEY, e.BTN_SOUTH, 1); dev.syn(); time.sleep(0.05)
    dev.write(e.EV_KEY, e.BTN_SOUTH, 0); dev.syn()


def main():
    app = QGuiApplication(sys.argv)
    from cornerplay.gamepad import Gamepad
    from cornerplay.config import settings
    settings.data["pad_glyphs"] = ""  # in memory only: the detected prompts, not a chosen set
    pad = Gamepad(app)

    def wait(seconds):  # let SDL see the device come or go
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            app.processEvents()
            time.sleep(0.01)

    wait(1.0)
    if not pad.available:
        print("SDL2 is not available"); return 2
    bad = 0
    for name, vendor, product, want in PADS:
        dev = plug(name, vendor, product)
        wait(1.2)
        info = pad.pads[-1] if pad.pads else {}
        got = pad.style
        ok = got == want
        bad += not ok
        print(f"{'ok ' if ok else 'BAD'}  {vendor:04x}:{product:04x}  {name[:44]:44}  sdl: {info.get('name', '-')[:28]:28}  "
              f"prompts: {got}" + ("" if ok else f" (wanted {want})"))
        dev.close()
        wait(0.8)

    # Two pads at once: the prompts follow the one pressed last.
    one, two = plug(*PADS[3][:3]), plug(*PADS[6][:3])
    wait(1.2)
    seen = []
    for dev, want in ((one, "ps5"), (two, "switch"), (one, "ps5")):
        press(dev)
        wait(0.4)
        seen.append(pad.style)
        bad += pad.style != want
    print(f"{'ok ' if seen == ['ps5', 'switch', 'ps5'] else 'BAD'}  two pads, pressed DualSense, Switch, DualSense: {' -> '.join(seen)}")
    one.close(); two.close()
    wait(0.5)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
