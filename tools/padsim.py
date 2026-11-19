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
from PySide6.QtGui import QGuiApplication  # noqa: E402

# (name the pad gives itself, vendor, product, the prompts Cornerplay should pick)
PADS = [
    ("Microsoft X-Box 360 pad", 0x045E, 0x028E, "xbox360", "xbox"),
    ("Microsoft X-Box One S pad", 0x045E, 0x02EA, "xbox", "xbox"),
    ("Xbox Wireless Controller", 0x045E, 0x0B13, "xbox", "xbox"),
    ("Sony Interactive Entertainment Wireless Controller", 0x054C, 0x0CE6, "ps5", "ps"),
    ("Sony Interactive Entertainment Wireless Controller", 0x054C, 0x09CC, "ps4", "ps"),
    ("Sony PLAYSTATION(R)3 Controller", 0x054C, 0x0268, "ps3", "ps"),
    ("Nintendo Switch Pro Controller", 0x057E, 0x2009, "switch", "switch"),
    ("Steam Deck", 0x28DE, 0x1205, "deck", "deck"),
    ("Valve Software Steam Controller", 0x28DE, 0x1102, "steam", "steam"),
    ("Google LLC Stadia Controller rev. A", 0x18D1, 0x9400, "stadia", "sym"),
    ("Amazon Game Controller", 0x1949, 0x0419, "luna", "sym"),
    ("NVIDIA Controller v01.04", 0x0955, 0x7214, "shield", "sym"),
    ("Generic USB Joystick", 0x0079, 0x0006, "generic", "xbox"),
    # Test your controller's drawings (pad.padShape) for pads named or made by someone it knows.
    ("8BitDo Pro 2", 0x2DC8, 0x6003, None, "sn30"),
    ("8BitDo SN30 Pro", 0x2DC8, 0x6001, None, "sn30"),
    ("8BitDo Zero 2 gamepad", 0x2DC8, 0x9018, None, "snes"),
    ("8BitDo Ultimate Wireless Controller", 0x2DC8, 0x3106, None, "xbox"),
    ("Xbox 360 Controller", 0x2DC8, 0x3105, None, "sn30"),   # an 8BitDo in XInput mode
    ("HORI Fighting Commander OCTA", 0x0F0D, 0x0123, None, "arcade"),
    ("Nintendo GameCube Controller", 0x0E6F, 0x0185, None, "gamecube"),
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
    for name, vendor, product, want, shape in PADS:
        dev = plug(name, vendor, product)
        wait(1.2)
        info = pad.pads[-1] if pad.pads else {}
        got, drawn = pad.style, pad.padShape
        ok = (want is None or got == want) and drawn == shape
        bad += not ok
        print(f"{'ok ' if ok else 'BAD'}  {vendor:04x}:{product:04x}  {name[:36]:36}  sdl: {info.get('name', '-')[:28]:28}  "
              f"prompts: {got:8} drawing: {drawn}" + ("" if ok else f" (wanted {want or got}, {shape})"))
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

    # Quick access over a game takes the pad away from the game (padgrab.py), and gives it back.
    import select
    from evdev import InputDevice, list_devices
    from PySide6.QtGui import QWindow
    dev = plug(*PADS[0][:3])
    wait(1.2)
    game = next(InputDevice(p) for p in list_devices() if InputDevice(p).name == PADS[0][0])
    heard = []
    pad.rawButton.connect(lambda b, d: heard.append(b) if d else None)

    def game_heard():
        n = 0
        while select.select([game], [], [], 0.05)[0]:
            n += sum(1 for ev in game.read() if ev.type in (e.EV_KEY, e.EV_ABS))
        return n
    game_heard()
    panel = QWindow()
    panel.show()
    pad.steer(panel)
    wait(0.3)
    for code in (e.BTN_SOUTH, e.BTN_EAST, e.BTN_TL):
        dev.write(e.EV_KEY, code, 1); dev.syn(); wait(0.1); dev.write(e.EV_KEY, code, 0); dev.syn(); wait(0.1)
    took = heard == [0, 1, 9] and game_heard() == 0
    pad.steer(None)
    wait(0.3)
    press(dev)
    wait(0.3)
    back = game_heard() > 0
    bad += not (took and back)
    print(f"{'ok ' if took and back else 'BAD'}  quick access over a game: Cornerplay heard {heard[:3]}, the game "
          f"{'heard nothing' if took else 'heard it too'}; afterwards the game {'hears it again' if back else 'still hears nothing'}")
    dev.close()
    wait(0.3)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
