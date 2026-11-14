"""Controller as keyboard and mouse, for games that only take a keyboard and mouse: ready-made
layouts like Steam Input's templates, and your own. While a game with a layout (a game's
Options, or TV mode's game menu) is in front, Cornerplay's gamepad turns buttons into keys and
clicks and the sticks into WASD, arrows, the mouse or the wheel, through a virtual keyboard and
mouse (kbdmouse.py). Guide still opens the menus (Guide + A quick access, Guide + Y the panel).

A layout: {"buttons": {button: action}, "left": stick, "right": stick, "lt": action, "rt": action}
  button  SDL's names: a b x y back start ls rs lb rb up down left right
  action  a key name from kbdmouse.KEYS, "Left click", "Right click", "Middle click",
          "Wheel up", "Wheel down", or "" (nothing)
  stick   "wasd", "arrows", "mouse", "scroll" or "" (nothing)
"""
import math

from . import kbdmouse

BUTTON_NAMES = {0: "a", 1: "b", 2: "x", 3: "y", 4: "back", 6: "start", 7: "ls", 8: "rs", 9: "lb", 10: "rb",
                11: "up", 12: "down", 13: "left", 14: "right", 15: "share",
                16: "paddle1", 17: "paddle2", 18: "paddle3", 19: "paddle4"}
ORDER = ["a", "b", "x", "y", "lb", "rb", "lt", "rt", "back", "start", "ls", "rs", "up", "down", "left", "right"]
ACTIONS = [""] + list(kbdmouse.MOUSE) + ["Wheel up", "Wheel down"] + list(kbdmouse.KEYS)
STICKS = ["", "wasd", "arrows", "mouse", "scroll"]

TEMPLATES = {
    "wasd": {"name": "Action and shooters (WASD)",
             "left": "wasd", "right": "mouse", "lt": "Right click", "rt": "Left click",
             "buttons": {"a": "Space", "b": "Ctrl", "x": "R", "y": "F", "lb": "Q", "rb": "E", "back": "Tab", "start": "Esc",
                         "ls": "Shift", "rs": "V", "up": "1", "right": "2", "down": "3", "left": "4"}},
    "strategy": {"name": "Strategy and management",
                 "left": "mouse", "right": "arrows", "lt": "Wheel down", "rt": "Wheel up",
                 "buttons": {"a": "Left click", "b": "Right click", "x": "Ctrl", "y": "Shift", "lb": "Q", "rb": "E", "back": "Tab",
                             "start": "Esc", "ls": "Middle click", "rs": "Space", "up": "1", "right": "2", "down": "3", "left": "4"}},
    "pointclick": {"name": "Point and click",
                   "left": "mouse", "right": "scroll", "lt": "", "rt": "",
                   "buttons": {"a": "Left click", "b": "Right click", "x": "Space", "y": "Tab", "lb": "", "rb": "", "back": "I",
                               "start": "Esc", "ls": "", "rs": "", "up": "Up", "down": "Down", "left": "Left", "right": "Right"}},
}


def template(name, custom=None):
    """The layout for a game: a template, or "custom" (the user's own, from settings)."""
    if name == "custom" and isinstance(custom, dict):
        base = {"left": "", "right": "", "lt": "", "rt": "", "buttons": {}}
        base.update({k: v for k, v in custom.items() if k in base})
        return base
    return TEMPLATES.get(name)


class Mapper:  # noqa: D101
    """Turns SDL controller events into keyboard and mouse events on a kbdmouse.Device."""
    DEAD = 0.18
    SPEED = 18.0   # mouse pixels per tick (16 ms) at full tilt
    TRIGGER = 0.5

    def __init__(self, layout, device=None):
        self.layout = layout
        self.dev = device or kbdmouse.Device()
        self.axes = [0.0] * 6
        self.held = {}        # stick direction or trigger -> key code held for it
        self._frac = [0.0, 0.0]
        self._wheel = 0.0

    def close(self):
        self.dev.close()

    def _do(self, action, down):
        if not action:
            return
        if action in kbdmouse.MOUSE:
            self.dev.key(kbdmouse.MOUSE[action], down)
        elif action in ("Wheel up", "Wheel down"):
            if down:
                self.dev.wheel(1 if action == "Wheel up" else -1)
        elif action in kbdmouse.KEYS:
            self.dev.key(kbdmouse.KEYS[action], down)

    def button(self, sdl_button, down):
        name = BUTTON_NAMES.get(sdl_button)
        if name:
            self._do(self.layout.get("buttons", {}).get(name, ""), down)

    def axis(self, axis, value):
        if 0 <= axis < 6:
            self.axes[axis] = max(-1.0, min(1.0, value / 32767))

    def _keys_for(self, mode, x, y, tag):
        names = {"wasd": ("A", "D", "W", "S"), "arrows": ("Left", "Right", "Up", "Down")}[mode]
        want = {names[0]: x < -0.45, names[1]: x > 0.45, names[2]: y < -0.45, names[3]: y > 0.45}
        for n, on in want.items():
            k = (tag, n)
            if on != bool(self.held.get(k)):
                self.held[k] = on
                self.dev.key(kbdmouse.KEYS[n], on)

    def tick(self):
        """Every poll (16 ms) while mapping: triggers as buttons, and sticks held toward a
        direction keep the keys down or the mouse and wheel moving."""
        for axis, name in ((4, "lt"), (5, "rt")):
            on = self.axes[axis] > self.TRIGGER
            if on != bool(self.held.get(name)):
                self.held[name] = on
                self._do(self.layout.get(name, ""), on)
        for stick, (ax, ay) in (("left", (0, 1)), ("right", (2, 3))):
            mode = self.layout.get(stick, "")
            x, y = self.axes[ax], self.axes[ay]
            if mode in ("wasd", "arrows"):
                self._keys_for(mode, x, y, stick)
            elif mode == "mouse":
                mag = math.hypot(x, y)
                if mag > self.DEAD:
                    scale = ((mag - self.DEAD) / (1 - self.DEAD)) ** 1.6 * self.SPEED / mag
                    self._frac[0] += x * scale
                    self._frac[1] += y * scale
                    dx, dy = int(self._frac[0]), int(self._frac[1])
                    self._frac[0] -= dx
                    self._frac[1] -= dy
                    self.dev.move(dx, dy)
            elif mode == "scroll":
                if abs(y) > self.DEAD:
                    self._wheel += -y * 0.25
                    steps = int(self._wheel)
                    if steps:
                        self._wheel -= steps
                        self.dev.wheel(steps)
