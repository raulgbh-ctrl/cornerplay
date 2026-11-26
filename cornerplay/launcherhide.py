"""Store apps out of sight while their games start (Hyprland).

Steam, Battle.net, Nexus Launcher (Xbox / Game Pass) and Prism Launcher open their own windows
when Cornerplay starts one of their games: the Steam client and its "launching" dialog, the
Battle.net app, Nexus's window, Prism's console. Nobody needs to look at them. While a game
starts, their windows go to a hidden workspace (special:cornerplay-<store>); a window that
needs you (a sign-in, an error, a cloud-save conflict) comes forward on the workspace you are
on. Lua-configured Hyprland (Ryoku) gets a window rule, so a window never flashes; classic
Hyprland has its windows moved as they appear. On Windows the apps' windows are found by
their program (steam.exe, Battle.net.exe) and hidden with ShowWindow (winwindows.py). Other
Linux desktops: the apps simply show, as before (Steam still starts with -silent, which keeps
its main window closed).
"""
import re
import threading
import time

from . import hypr, winwindows
from .osinfo import WINDOWS

ASK_WAIT = 10  # seconds a sign-in window may show before it counts as waiting for you


class Launcher:
    def __init__(self, store, name, classes, needs, quiet=(), patience=0, close_after=False, programs=()):
        self.store = store
        self.programs = tuple(programs)  # Windows: the programs whose windows these are (lower case)
        self.name = name                # shown in "Steam needs you (…)"
        self.classes = tuple(classes)   # window classes, exact (case-insensitive)
        self.needs = tuple(needs)       # title words of windows that want you
        self.quiet = tuple(quiet)       # exact titles of windows that never need you (the main window)
        self.patience = patience        # seconds without the game: then whatever is hidden shows
        self.close_after = close_after  # opened only for the game: close its windows (to the tray)
        self.place = f"special:cornerplay-{store}"
        self.rule_name = f"cornerplay-{store}-hidden"


LAUNCHERS = {
    # Steam's own windows are class "steam"; its games are steam_app_<id>, never touched.
    "steam": Launcher("steam", "Steam", ("steam",),
                      ("sign in", "steam guard", "login", "error", "cloud", "conflict", "agreement", "eula",
                       "licen", "install", "uninstall", "warning", "choose", "select", "password"),
                      quiet=("steam", "friends list", "special offers", "what's new"), patience=45, close_after=True,
                      programs=("steam.exe", "steamwebhelper.exe")),
    "battlenet": Launcher("battlenet", "Battle.net", ("steam_app_battlenet",),
                          ("battle.net login", "login", "sign in", "blizzard error", "error", "update required"),
                          programs=("battle.net.exe",)),
    "xbox": Launcher("xbox", "Nexus Launcher", ("org.xodusgaming.nexus",),
                     ("sign in", "login", "microsoft", "error", "update", "account")),
    "prism": Launcher("prism", "Prism Launcher",
                      ("org.prismlauncher.prismlauncher", "prismlauncher", "prism launcher"),
                      ("login", "sign in", "microsoft", "account", "error", "update", "java", "crash"),
                      programs=("prismlauncher.exe",)),
}


def available() -> bool:
    return winwindows.available() if WINDOWS else hypr.running()


def get(store_id):
    """The store's app, when this system has one to hide (Windows: Xbox games start through
    the Xbox app, which is left alone)."""
    spec = LAUNCHERS.get(store_id)
    return spec if spec and (spec.programs or not WINDOWS) else None


def windows(spec) -> list:
    if WINDOWS:
        return [c for c in winwindows.clients() if c.get("class") in spec.programs]
    return [c for c in hypr.clients() if str(c.get("class") or "").lower() in spec.classes]


def hidden(spec, w) -> bool:
    return ((w.get("workspace") or {}).get("name") or "") in (spec.place, winwindows.HIDDEN)


def _hide(spec, w) -> bool:
    if WINDOWS:
        return winwindows.hide(w["address"])
    return hypr.move_window(w["address"], spec.place)


def _bring(w, here, focus) -> bool:
    if WINDOWS:
        return winwindows.show(w["address"], focus)
    return hypr.move_window(w["address"], here, silent=not focus)


def rule(spec, on: bool) -> bool:
    """New windows of the app open hidden (Lua Hyprland); off replaces the rule with one that
    matches nothing. Classic Hyprland: False (park() does it instead)."""
    if WINDOWS or not hypr.lua():
        return False
    if on:
        alts = "|".join(re.escape(c) for c in spec.classes)
        match = {"class": f"(?i)^({alts})$"}
    else:
        match = {"class": "^(cornerplay-matches-nothing)$"}
    return hypr.window_rule(spec.rule_name, match, workspace=spec.place + " silent")


def wants_you(spec, w) -> bool:
    title = (w.get("title") or "").strip().lower()
    if title in spec.quiet:
        return False
    return any(t in title for t in spec.needs)


def park(spec, keep=()) -> int:
    """Hide every window of the app not already hidden (but those in `keep`, which were on
    screen before the game was started, and those that want you); how many moved."""
    n = 0
    for w in windows(spec):
        if w.get("address") in keep or hidden(spec, w) or wants_you(spec, w):
            continue
        n += _hide(spec, w)
    return n


def asking(spec) -> dict:
    """The window that needs you ({} when none): a sign-in, an error."""
    return next((w for w in windows(spec) if wants_you(spec, w)), {})


def _here():
    if WINDOWS:
        return ""
    here = hypr.workspace()
    return "1" if not here or here.startswith("special:") else here


def show(spec, only=None, focus=True) -> bool:
    """Bring the app's hidden windows (or just `only`) to the workspace you are on."""
    here = _here()
    ws = [only] if only else [w for w in windows(spec) if hidden(spec, w)] or (windows(spec) if focus else [])
    for w in ws:
        _bring(w, here, focus)
    if ws and focus and not WINDOWS:
        hypr.focus_window(ws[0]["address"])
    return bool(ws)


def put_away(spec) -> int:
    """After the game: the app's windows that are still hidden. Steam's are closed (it stays in
    the tray, as -silent starts it); other apps' come back quietly, without taking focus."""
    gone = [w for w in windows(spec) if hidden(spec, w)]
    for w in gone:
        if spec.close_after:
            winwindows.close(w["address"]) if WINDOWS else hypr.close_window(w["address"])
        else:
            _bring(w, _here(), focus=False)
    return len(gone)


class Hider:
    """Keeps one store app out of sight while a game starts, on a thread of its own.

    started(): the game is up (then hiding stops a few seconds later); None hides until
    finish(). on_need(title): a window wants you ("" once it is gone)."""

    def __init__(self, spec, started=None, on_need=None, start_wait=180.0, poll=0.4):
        self.spec, self.started, self.on_need = spec, started, on_need
        self.start_wait, self.poll = start_wait, poll
        self.keep = {w.get("address") for w in windows(spec) if not hidden(spec, w)}
        self.was_open = bool(self.keep)
        self.need = ""
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        rule(self.spec, True)
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return self

    def _set_need(self, title):
        if title != self.need:
            self.need = title
            if self.on_need:
                try:
                    self.on_need(title)
                except Exception:
                    pass

    def _loop(self):
        t0, up_at, ask_since, gave_up = time.time(), None, None, False
        while not self._stop.is_set():
            now = time.time()
            if self.started and up_at is None:
                try:
                    if self.started():
                        up_at = now
                except Exception:
                    pass
            if up_at is not None and now - up_at > 5:
                break  # the game is up: its store app has nothing more to show
            if self.started and up_at is None and now - t0 > self.start_wait:
                break
            if not gave_up:
                park(self.spec, self.keep)
            ask = asking(self.spec) if up_at is None else {}
            # A sign-in window shows for a few seconds even when it signs in by itself: only
            # one that is still there after ASK_WAIT really waits for you.
            if not ask:
                ask_since = None
            elif ask_since is None:
                ask_since = now
            if ask and (now - ask_since >= ASK_WAIT or self.need):
                if not self.need:
                    show(self.spec, ask)
                self._set_need(ask.get("title") or self.spec.name)
            elif not ask:
                self._set_need("")
            # Nothing started and nothing asked for a long while: something hidden is in the way
            # (a launch-options chooser, Steam updating itself). Show it instead of waiting on.
            if (not gave_up and self.spec.patience and up_at is None and not self.need
                    and now - t0 > self.spec.patience and any(hidden(self.spec, w) for w in windows(self.spec))):
                gave_up = True
                rule(self.spec, False)
                show(self.spec)
                self._set_need(self.spec.name)
            self._stop.wait(self.poll)
        rule(self.spec, False)

    def finish(self, wait=True):
        """The game closed (or, for Steam, Cornerplay's part is over): wait for the start to be
        seen, stop hiding, and put the app's hidden windows away."""
        if self._thread:
            if not (wait and self.started):
                self._stop.set()
            self._thread.join(timeout=self.start_wait + 5)
            self._stop.set()
        rule(self.spec, False)
        self._set_need("")
        if self.was_open:
            show(self.spec, focus=False)  # it was open before: back where it was, quietly
        else:
            put_away(self.spec)
