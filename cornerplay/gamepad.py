"""Controller input through SDL2, turned into key presses for the focused Cornerplay window.

Laid out like SteamOS Game Mode: D-pad / left stick = arrows, A = Return (select),
B = Escape (back), Start / Menu = F2 (the game's options), X = F2 as well, Y = F3 (installed
only), View / Select = F4 (search), LB / RB = PageUp / PageDown (previous / next store),
LT / RT = Shift+Left / Right (jump). Guide (the Xbox, PS or Home button) = F10 (the main
menu, opened when it is let go), Guide + A or Share = F9 (quick access, Steam's "..." menu).
Nothing is sent while Cornerplay is not the focused window, so the pad never steers the
library while a game is running. The one exception is Guide + Y: it opens the in-game panel
(the overlay signal) over whatever has the focus.
"""
import ctypes
import ctypes.util
import time

from PySide6.QtCore import QEvent, QObject, Qt, QTimer, Property, Signal, Slot
from PySide6.QtGui import QGuiApplication, QKeyEvent

INIT_GAMECONTROLLER = 0x00002000
DEVICE_ADDED, DEVICE_REMOVED = 0x653, 0x654
AXIS_MOTION, BUTTON_DOWN, BUTTON_UP = 0x650, 0x651, 0x652

BUTTONS = {
    0: Qt.Key_Return, 1: Qt.Key_Escape, 2: Qt.Key_F2, 3: Qt.Key_F3, 4: Qt.Key_F4,  # 4: View / Select: search
    6: Qt.Key_F2, 9: Qt.Key_PageUp, 10: Qt.Key_PageDown,                          # 6: Start / Menu: options
    11: Qt.Key_Up, 12: Qt.Key_Down, 13: Qt.Key_Left, 14: Qt.Key_Right,
    15: Qt.Key_F9,                                                                # 15: Share / Capture: quick access
}
GUIDE, BUTTON_A, BUTTON_Y = 5, 0, 3
MAIN_MENU, QUICK_ACCESS = Qt.Key_F10, Qt.Key_F9
REPEATING = {Qt.Key_Up, Qt.Key_Down, Qt.Key_Left, Qt.Key_Right}
# SDL_GameControllerType -> which button prompts to show (qml/glyphs.js draws them).
STYLES = {1: "xbox360", 2: "xbox", 3: "ps3", 4: "ps4", 5: "switch", 7: "ps5", 8: "luna", 9: "stadia",
          10: "shield", 11: "switch", 12: "switch", 13: "switch"}
GLYPHS = {"xbox", "xbox360", "ps5", "ps4", "ps3", "switch", "deck", "steam", "stadia", "luna", "shield", "generic"}
OLD_GLYPHS = {"playstation": "ps5", "nintendo": "switch"}
VALVE = 0x28DE
STEAM_CONTROLLERS = {0x1102, 0x1142}   # wired and wireless
DECK_PRODUCT = 0x1205
STEAM_VIRTUAL = 0x11FF                # Steam Input's virtual pad (Game Mode presents every pad this way)
# SDL_JoystickPowerLevel -> a battery percentage to show (wired and unknown: None).
POWER = {0: 5, 1: 20, 2: 60, 3: 100, 5: 100}
STICK_ON, STICK_OFF = 18000, 12000
ACTIVE_MS, IDLE_MS = 16, 1000  # 60 checks a second while in use, one a second otherwise
BACKGROUND_MS = 100           # a pad is plugged in but a game has the focus: Guide + Y stays quick
FIRST_REPEAT = 0.38
# Holding a direction speeds up: (held for at least, seconds between moves).
REPEAT_STEPS = ((0.0, 0.11), (1.0, 0.06), (2.0, 0.035))
# The triggers (axes 4 and 5: LT / RT, L2 / R2) page through a row: Shift+Left / Shift+Right.
TRIGGERS = {4: Qt.Key_Left, 5: Qt.Key_Right}
TRIGGER_ON, TRIGGER_OFF = 16000, 8000
PAGE = Qt.ShiftModifier


def _repeat_gap(held_for):
    gap = REPEAT_STEPS[0][1]
    for after, step in REPEAT_STEPS:
        if held_for >= after:
            gap = step
    return gap


START_DELAY_MS = 300  # SDL_Init scans every input device (~150 ms); do it after the window is up


class Gamepad(QObject):
    connectedChanged = Signal()
    availableChanged = Signal()
    _sdlFetched = Signal()  # from the download thread; queued to the main thread
    styleChanged = Signal()
    overlay = Signal()   # Guide + Y: open or close the in-game panel
    activity = Signal()  # any button or stick, while Cornerplay has the focus
    # The controller tester (TV mode's Settings): every button and stick as it is, and while
    # capture is on, nothing is turned into keys (so B can be tested without leaving).
    rawButton = Signal(int, bool)
    rawAxis = Signal(int, int)
    captureChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._sdl = None
        self._pads = {}    # instance id -> controller handle
        self._held = {}    # Qt key -> time of next repeat
        self._stick = {}   # (pad, axis) -> key currently held by that stick axis
        self._guide = None  # None, "held" (Guide down) or "chord" (Guide + A used: no menu on release)
        self._swallow = set()  # buttons whose release must not send anything (the A of Guide + A)
        self._event = ctypes.create_string_buffer(128)
        self._timer = None
        self._style = "xbox"
        self._pad_style = "xbox"  # what the controller is; _style may be the user's choice instead
        self._info = {}            # instance id -> {"name", "style", "mapping"}
        self._capture = False
        self._buttons = dict(BUTTONS)
        self._deck = self._is_deck()
        self.reload()
        from . import padlayout
        padlayout.current_mappings = lambda: [i["mapping"] for i in list(self._info.values())]
        self._sdlFetched.connect(self._start)
        QTimer.singleShot(START_DELAY_MS, self._start)

    def _start(self):
        try:
            self._load()
        except (OSError, AttributeError):
            self._sdl = None
            self._fetch_sdl()
            return
        self.availableChanged.emit()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._timer.start(IDLE_MS)
        QGuiApplication.instance().focusWindowChanged.connect(lambda _w: self._pace())
        self._poll()  # pick up controllers that were plugged in before we started

    def _pace(self):
        """Fast polling only while a controller is plugged in and this app has focus."""
        interval = IDLE_MS if not self._pads else ACTIVE_MS if QGuiApplication.focusWindow() is not None else BACKGROUND_MS
        if self._timer.interval() != interval:
            self._timer.setInterval(interval)

    _fetching = False

    def _fetch_sdl(self):
        """No SDL2 anywhere: get the private copy in the background (sdl.py), then start."""
        from . import sdl as sdl_lib
        if Gamepad._fetching or not sdl_lib.can_fetch() or sdl_lib.PRIVATE.is_file():
            return
        Gamepad._fetching = True
        import threading

        def work():
            try:
                sdl_lib.fetch()
            except Exception:
                return
            finally:
                Gamepad._fetching = False
            self._sdlFetched.emit()  # Qt queues it to the main thread, where _start runs
        threading.Thread(target=work, daemon=True, name="fetch-sdl").start()

    def _load(self):
        from . import sdl as sdl_lib
        sdl = None
        for path in sdl_lib.candidates():
            try:
                sdl = ctypes.CDLL(path)
                break
            except OSError:
                continue
        if sdl is None:
            raise OSError("SDL2 not found")
        sdl.SDL_SetHint.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
        sdl.SDL_Init.argtypes = [ctypes.c_uint32]
        sdl.SDL_PollEvent.argtypes = [ctypes.c_void_p]
        sdl.SDL_GameControllerOpen.argtypes = [ctypes.c_int]
        sdl.SDL_GameControllerOpen.restype = ctypes.c_void_p
        sdl.SDL_GameControllerGetJoystick.argtypes = [ctypes.c_void_p]
        sdl.SDL_GameControllerGetJoystick.restype = ctypes.c_void_p
        sdl.SDL_JoystickInstanceID.argtypes = [ctypes.c_void_p]
        sdl.SDL_JoystickInstanceID.restype = ctypes.c_int32
        sdl.SDL_GameControllerClose.argtypes = [ctypes.c_void_p]
        for fn in ("SDL_GameControllerGetVendor", "SDL_GameControllerGetProduct"):  # SDL 2.0.6+
            try:
                getattr(sdl, fn).argtypes = [ctypes.c_void_p]
                getattr(sdl, fn).restype = ctypes.c_uint16
            except AttributeError:
                pass
        sdl.SDL_GameControllerName.argtypes = [ctypes.c_void_p]
        sdl.SDL_GameControllerName.restype = ctypes.c_char_p
        sdl.SDL_GameControllerMapping.argtypes = [ctypes.c_void_p]
        sdl.SDL_GameControllerMapping.restype = ctypes.c_void_p  # freed with SDL_free
        sdl.SDL_free.argtypes = [ctypes.c_void_p]
        sdl.SDL_JoystickCurrentPowerLevel.argtypes = [ctypes.c_void_p]
        sdl.SDL_JoystickCurrentPowerLevel.restype = ctypes.c_int
        try:  # SDL 2.0.12 and newer
            sdl.SDL_GameControllerGetType.argtypes = [ctypes.c_void_p]
            sdl.SDL_GameControllerGetType.restype = ctypes.c_int
            self._get_type = sdl.SDL_GameControllerGetType
        except AttributeError:
            self._get_type = None
        try:  # SDL 2.0.9 and newer
            sdl.SDL_GameControllerRumble.argtypes = [ctypes.c_void_p, ctypes.c_uint16, ctypes.c_uint16, ctypes.c_uint32]
            sdl.SDL_GameControllerRumble.restype = ctypes.c_int
            self._rumble = sdl.SDL_GameControllerRumble
        except AttributeError:
            self._rumble = None
        sdl.SDL_SetHint(b"SDL_NO_SIGNAL_HANDLERS", b"1")
        sdl.SDL_SetHint(b"SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS", b"1")
        if sdl.SDL_Init(INIT_GAMECONTROLLER) != 0:
            raise OSError("SDL_Init failed")
        self._sdl = sdl

    @staticmethod
    def _is_deck():
        """Steam Deck hardware. In Desktop Mode Steam turns its controller into a keyboard
        (A = Enter, B = Esc, Y = Space, D-pad = arrows), so SDL never sees a pad there."""
        try:
            vendor = open("/sys/class/dmi/id/board_vendor").read().strip()
            product = open("/sys/class/dmi/id/product_name").read().strip()
        except OSError:
            return False
        return vendor == "Valve" and product in ("Jupiter", "Galileo")

    available = Property(bool, lambda s: s._sdl is not None, notify=availableChanged)
    deck = Property(bool, lambda s: s._deck, constant=True)
    connected = Property(bool, lambda s: bool(s._pads), notify=connectedChanged)
    style = Property(str, lambda s: s._style, notify=styleChanged)  # a key of qml/glyphs.js

    @Slot()
    def reload(self):
        """Settings > Controllers changed: the button prompts and which button chooses."""
        from .config import settings
        glyphs = settings.get("pad_glyphs") or ""
        glyphs = OLD_GLYPHS.get(glyphs, glyphs)
        # No pad seen yet on a Steam Deck: its own controls (Steam turns them into keys on the desktop).
        own = self._pad_style if self._pads or not self._deck else "deck"
        style = glyphs if glyphs in GLYPHS else own
        if style != self._style:
            self._style = style
            self.styleChanged.emit()
        self._buttons = dict(BUTTONS)
        if settings.get("pad_swap_confirm"):
            self._buttons[0], self._buttons[1] = Qt.Key_Escape, Qt.Key_Return

    def _pads_info(self):
        out = []
        for iid, handle in list(self._pads.items()):
            info = self._info.get(iid, {})
            level = -1
            try:
                level = self._sdl.SDL_JoystickCurrentPowerLevel(self._sdl.SDL_GameControllerGetJoystick(handle))
            except (OSError, AttributeError):
                pass
            out.append({"id": iid, "name": info.get("name") or "Controller", "style": info.get("style", "xbox"),
                        "battery": POWER.get(level, -1), "wired": level == 4})
        return out

    pads = Property("QVariantList", _pads_info, notify=connectedChanged)

    def _set_capture(self, on):
        if bool(on) != self._capture:
            self._capture = bool(on)
            self._held.clear()
            self.captureChanged.emit()

    capture = Property(bool, lambda s: s._capture, _set_capture, notify=captureChanged)

    @Slot(int)
    def buzz(self, strength):
        """Settings > Controllers > Test rumble: a firm half-second buzz."""
        self.rumble(strength / 100, strength / 100, 500)

    def _used(self, iid):
        """A button on this pad: the prompts follow the controller in your hands, like Steam's."""
        info = self._info.get(iid)
        if info and info["style"] != self._pad_style:
            self._pad_style = info["style"]
            self.reload()

    def _style_of(self, handle, name):
        """Which prompts this controller has: Valve's own pads by their ids, the rest by SDL's type."""
        sdl = self._sdl
        try:
            vendor, product = sdl.SDL_GameControllerGetVendor(handle), sdl.SDL_GameControllerGetProduct(handle)
        except AttributeError:
            vendor = product = 0
        if vendor == VALVE:
            if product == DECK_PRODUCT or (product == STEAM_VIRTUAL and self._deck):
                return "deck"
            if product in STEAM_CONTROLLERS:
                return "steam"
        kind = self._get_type(handle) if self._get_type else 0
        if kind in STYLES:
            return STYLES[kind]
        low = name.lower()
        if "steam deck" in low:
            return "deck"
        if "8bitdo" in low or "xinput" in low or "x-box" in low or "xbox" in low:
            return "xbox"
        return "generic" if kind in (0, 6) and name else "xbox"

    def _remember(self, iid, handle):
        sdl = self._sdl
        name = sdl.SDL_GameControllerName(handle) or b""
        ptr = sdl.SDL_GameControllerMapping(handle)
        mapping = ""
        if ptr:
            mapping = ctypes.string_at(ptr).decode("utf-8", "replace")
            sdl.SDL_free(ptr)
        style = self._style_of(handle, name.decode("utf-8", "replace"))
        self._info[iid] = {"name": name.decode("utf-8", "replace"), "style": style, "mapping": mapping}

    # --- SDL events ------------------------------------------------------
    def _poll(self):
        sdl, ev = self._sdl, self._event
        while sdl.SDL_PollEvent(ev):
            kind = ctypes.c_uint32.from_buffer(ev, 0).value
            which = ctypes.c_int32.from_buffer(ev, 8).value
            if kind == DEVICE_ADDED:
                handle = sdl.SDL_GameControllerOpen(which)
                if handle:
                    iid = sdl.SDL_JoystickInstanceID(sdl.SDL_GameControllerGetJoystick(handle))
                    self._pads[iid] = handle
                    self._remember(iid, handle)
                    self._pad_style = self._info[iid]["style"]  # the pad plugged in last decides the glyphs
                    self.reload()
                    self.connectedChanged.emit()
                    self._pace()
            elif kind == DEVICE_REMOVED:
                handle = self._pads.pop(which, None)
                self._info.pop(which, None)
                if self._info:  # the prompts follow the pad that is still there
                    self._pad_style = list(self._info.values())[-1]["style"]
                self.reload()
                if handle:
                    sdl.SDL_GameControllerClose(handle)
                    self.connectedChanged.emit()
                    self._pace()
                self._held.clear()
                self._stick.clear()
                self._guide = None
                self._swallow.clear()
            elif kind in (BUTTON_DOWN, BUTTON_UP):
                if kind == BUTTON_DOWN:
                    self._used(which)
                self.rawButton.emit(ev.raw[12], kind == BUTTON_DOWN)
                if self._capture:
                    self.activity.emit()
                    continue
                self._button(ev.raw[12], kind == BUTTON_DOWN)
            elif kind == AXIS_MOTION:
                axis = ev.raw[12]
                value = ctypes.c_int16.from_buffer(ev, 16).value
                self.rawAxis.emit(axis, value)
                if self._capture:
                    continue
                if axis in (0, 1):
                    self._axis(which, axis, value)
                elif axis in TRIGGERS:
                    self._trigger(which, axis, value)
        now = time.monotonic()
        for held, (due, since) in list(self._held.items()):
            if now >= due:
                self._held[held] = (now + _repeat_gap(now - since), since)
                self._send(*held, repeat=True)

    _rumble = None

    def rumble(self, low: float, high: float, ms: int):
        """A short buzz on every connected pad (strengths 0..1). Pads without motors ignore it."""
        if not self._rumble or not getattr(self, "_pads", None):
            return
        lo, hi = int(max(0.0, min(1.0, low)) * 0xFFFF), int(max(0.0, min(1.0, high)) * 0xFFFF)
        for handle in list(self._pads.values()):
            try:
                self._rumble(handle, lo, hi, int(ms))
            except (OSError, ctypes.ArgumentError):
                pass

    def _button(self, button, down):
        # Guide opens the main menu when let go, unless it was held for Guide + A (quick access),
        # the way Steam treats its own button.
        if button == GUIDE:
            if down:
                self._guide = "held"
            else:
                if self._guide == "held":
                    self._send(MAIN_MENU)
                self._guide = None
            return
        if button == BUTTON_Y and down and self._guide:  # the in-game panel, even while a game has the focus
            self._guide = "chord"
            self._swallow.add(button)
            self.overlay.emit()
            return
        if button == BUTTON_A and down and self._guide:
            self._guide = "chord"
            self._swallow.add(button)
            self._send(QUICK_ACCESS)
            return
        if not down and button in self._swallow:
            self._swallow.discard(button)
            return
        key = self._buttons.get(button)
        if key is not None:
            self._set(key, down)

    def _axis(self, pad, axis, value):
        low, high = (Qt.Key_Left, Qt.Key_Right) if axis == 0 else (Qt.Key_Up, Qt.Key_Down)
        current = self._stick.get((pad, axis))
        wanted = current
        if abs(value) < STICK_OFF:
            wanted = None
        elif value <= -STICK_ON:
            wanted = low
        elif value >= STICK_ON:
            wanted = high
        if wanted != current:
            if current is not None:
                self._set(current, False)
            if wanted is not None:
                self._set(wanted, True)
            self._stick[(pad, axis)] = wanted

    def _trigger(self, pad, axis, value):
        on = self._stick.get((pad, axis))
        if not on and value >= TRIGGER_ON:
            self._stick[(pad, axis)] = True
            self._set(TRIGGERS[axis], True, PAGE)
        elif on and value <= TRIGGER_OFF:
            self._stick[(pad, axis)] = False
            self._set(TRIGGERS[axis], False, PAGE)

    def _set(self, key, down, mods=Qt.NoModifier):
        held = (key, mods)
        if not down:
            self._held.pop(held, None)
            return
        if key in REPEATING:
            now = time.monotonic()
            self._held[held] = (now + FIRST_REPEAT, now)
        self._send(key, mods)

    def _send(self, key, mods=Qt.NoModifier, repeat=False):
        window = QGuiApplication.focusWindow()
        if window is None:  # a game (or anything else) has focus: stay out of the way
            self._held.clear()
            return
        self.activity.emit()  # TV mode's screensaver waits for a quiet controller
        for kind in (QEvent.KeyPress, QEvent.KeyRelease):
            QGuiApplication.postEvent(window, QKeyEvent(kind, key, mods, "", repeat))
