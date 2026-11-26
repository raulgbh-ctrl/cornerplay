"""The interface, kept only while it is needed (Linux and Windows alike).

Everything that keeps working out of sight (downloads, installs, playtime, the tray, controller
shortcuts, update checks) lives in Python (app.py). The interface (Main.qml and every page in it)
is most of Cornerplay's memory: a few hundred MB once the covers are in. So when the window has been
out of sight for a while (in the tray, or while a game runs), it is let go, and the memory given
back to the system; opening Cornerplay, or a shortcut that needs a page of it (the game panel,
quick access, the launcher), builds it again in a second or two.

Settings > General > "Free memory while in the tray" (light_background, on by default).
"""
import ctypes
import gc
import os
import sys

from PySide6.QtCore import QObject, QTimer, Signal

from .config import settings

IDLE_MS = int(os.environ.get("CORNERPLAY_UI_IDLE_MS") or 60_000)  # hidden this long before the interface is let go


def limit_malloc_arenas():
    """glibc gives each thread that allocates its own memory pool (up to 8 per core), and memory
    freed in one stays there; Cornerplay's many short background jobs left a few hundred MB that
    way. Two pools are plenty for an app like this. Call before the worker threads start."""
    if sys.platform.startswith("linux"):
        try:
            ctypes.CDLL("libc.so.6").mallopt(-8, 2)  # M_ARENA_MAX
        except (OSError, AttributeError):
            pass


def give_back_memory():
    """Hand freed memory back to the system (glibc keeps it otherwise; Windows trims the working set)."""
    gc.collect()
    try:
        if sys.platform.startswith("linux"):
            ctypes.CDLL("libc.so.6").malloc_trim(0)
        elif os.name == "nt":
            k32 = ctypes.windll.kernel32
            k32.SetProcessWorkingSetSize(k32.GetCurrentProcess(), ctypes.c_size_t(-1), ctypes.c_size_t(-1))
    except (OSError, AttributeError):
        pass


class Ui(QObject):
    windowChanged = Signal(object)  # the new window (None once let go)

    def __init__(self, qapp, build):
        super().__init__(qapp)
        self.qapp, self._build = qapp, build
        self.engine = None
        self.window = None
        self.built_once = False
        self._idle = QTimer(self)
        self._idle.setSingleShot(True)
        self._idle.setInterval(IDLE_MS)
        self._idle.timeout.connect(self._idle_unload)
        self.busy = lambda: False  # set by the tray: True while something needs the window kept

    # --- building -------------------------------------------------------------------------------
    def load(self, hidden=False) -> bool:
        if self.window is not None:
            return True
        engine = self._build(hidden)
        if not engine.rootObjects():
            return False
        self.engine = engine
        self.window = engine.rootObjects()[0]
        self.built_once = True
        self.window.visibleChanged.connect(self._visible_changed)
        self.windowChanged.emit(self.window)
        if hidden:
            self._idle.start()
        return True

    def run(self, fn):
        """Do fn once the interface exists (right away when it does)."""
        if self.window is not None:
            fn()
            return
        if self.load(hidden=True):
            QTimer.singleShot(400, fn)  # its Connections and windows are ready by then
            self._idle.start()

    # --- letting go -----------------------------------------------------------------------------
    def _visible_changed(self, visible):
        if visible:
            self._idle.stop()
        else:
            self._idle.start()

    def _idle_unload(self):
        if self.window is None or self.window.isVisible():
            return
        if not settings.get("light_background", True) or self.busy():
            self._idle.start()  # look again later
            return
        if any(w.isVisible() for w in self.qapp.topLevelWindows()):
            self._idle.start()  # a panel or dialog of it is on screen
            return
        self.unload()

    def unload(self, now=False):
        if self.window is None:
            return
        engine, window = self.engine, self.window
        self.engine = self.window = None
        self.windowChanged.emit(None)
        try:
            window.visibleChanged.disconnect(self._visible_changed)
        except (RuntimeError, TypeError):
            pass
        if now:
            del window
            del engine
            return
        for obj in engine.rootObjects():
            obj.deleteLater()
        engine.deleteLater()
        del window, engine
        QTimer.singleShot(1500, give_back_memory)  # after Qt has really deleted it
