"""Freeze a game while you are away from it (Hyprland), like a console's suspend.

A game's Options > "Pause when you switch away": when another window gets the focus (or an
empty workspace), the game's processes are stopped (SIGSTOP) after a few seconds, so it uses no
CPU, GPU or battery; back on its window, they carry on (SIGCONT) exactly where they were. For
single-player games: an online game would lose its connection.

The game is every process under the one Cornerplay started (Proton's container reaps orphans,
so Wine's processes stay in that tree), or, for Battle.net's games, the processes found by
their folder. Hyprland tells which window has the focus on its event socket (socket2).
"""
import os
import signal
import socket
import threading
import time

from . import hypr

DELAY = 3.0  # seconds away before the game stops: a quick look elsewhere does not stop it


def _ppids() -> dict:
    out = {}
    for d in os.listdir("/proc"):
        if not d.isdigit():
            continue
        try:
            with open(f"/proc/{d}/stat") as f:
                rest = f.read().rsplit(")", 1)[1].split()
            out[int(d)] = int(rest[1])
        except (OSError, IndexError, ValueError):
            pass
    return out


def tree(root: int) -> list:
    """root and everything under it."""
    kids = {}
    for pid, ppid in _ppids().items():
        kids.setdefault(ppid, []).append(pid)
    out, todo = [], [int(root)]
    while todo:
        p = todo.pop()
        if p in out:
            continue
        out.append(p)
        todo.extend(kids.get(p, []))
    return out


def _signal(pids, sig):
    for p in pids:
        try:
            os.kill(p, sig)
        except OSError:
            pass


class Freezer:
    """games: {key: {"root": pid} or {"pids": [..]}} of the games that asked for it."""

    def __init__(self, on_frozen=None):
        self.games = {}
        self.frozen = {}   # key -> pids stopped
        self.on_frozen = on_frozen
        self._timer = None
        self._lock = threading.Lock()
        self._thread = None
        self._stop = False

    def _pids(self, g):
        return list(g.get("pids") or []) or (tree(g["root"]) if g.get("root") else [])

    def set_games(self, games: dict):
        with self._lock:
            for key in [k for k in self.frozen if k not in games]:
                _signal(self.frozen.pop(key), signal.SIGCONT)  # closed or switched off: never left stopped
            self.games = dict(games)
        if games and not self._thread and hypr.running():
            self._stop = False
            self._thread = threading.Thread(target=self._listen, daemon=True, name="freeze")
            self._thread.start()

    def thaw_all(self):
        with self._lock:
            for pids in self.frozen.values():
                _signal(pids, signal.SIGCONT)
            self.frozen.clear()

    def thaw(self, key):
        with self._lock:
            pids = self.frozen.pop(key, None)
        if pids:
            _signal(pids, signal.SIGCONT)

    def stop(self):
        self._stop = True
        self.thaw_all()

    # --- focus ---------------------------------------------------------------------------
    def focused(self, address: str):
        """A window got the focus ("" = none): the game owning it carries on, the others stop soon."""
        pid = 0
        if address:
            a = address if address.startswith("0x") else "0x" + address
            w = next((c for c in hypr.clients() if c.get("address") == a), None)
            pid = int((w or {}).get("pid") or 0)
        if pid == os.getpid():
            return  # Cornerplay's own panel or quick access over the game: not away
        with self._lock:
            games = dict(self.games)
        here = None
        for key, g in games.items():
            if pid and pid in (self.frozen.get(key) or self._pids(g)):
                here = key
        if here:
            self.thaw(here)
        if self._timer:
            self._timer.cancel()
        away = [k for k in games if k != here and k not in self.frozen]
        if away:
            self._timer = threading.Timer(DELAY, self._freeze, args=(away, address))
            self._timer.daemon = True
            self._timer.start()

    def _freeze(self, keys, address):
        for key in keys:
            with self._lock:
                g = self.games.get(key)
                if not g or key in self.frozen:
                    continue
                pids = [p for p in self._pids(g) if p != os.getpid()]
                if not pids:
                    continue
                _signal(pids, signal.SIGSTOP)
                self.frozen[key] = pids
            if self.on_frozen:
                self.on_frozen(key)

    def _listen(self):
        sig = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE", "")
        path = os.path.join(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"), "hypr", sig, ".socket2.sock")
        while not self._stop:
            try:
                s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                s.connect(path)
                buf = b""
                while not self._stop:
                    data = s.recv(4096)
                    if not data:
                        break
                    buf += data
                    while b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        ev, _, arg = line.decode("utf-8", "replace").partition(">>")
                        if ev == "activewindowv2" and self.games:
                            self.focused(arg.strip())
            except OSError:
                time.sleep(5)  # Hyprland restarting: try again
            finally:
                try:
                    s.close()
                except (OSError, UnboundLocalError):
                    pass
        self._thread = None
