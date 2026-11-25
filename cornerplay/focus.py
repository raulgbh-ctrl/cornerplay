"""Focus while playing: when a game starts, quiet the PC down; when the last one closes, put
everything back. Each part is a setting (Settings > Games & Proton, TV mode's Settings > Games):

  focus_dnd        notifications held back: Ryoku's Game Mode (do not disturb, lighter desktop
                   effects), else swaync, dunst, mako or GNOME's do-not-disturb
  focus_awake      the screen stays on and the PC does not sleep (systemd-inhibit), for games
                   that do not ask for it themselves (most under Wine)
  focus_power      the Performance power mode (power-profiles-daemon), back to the old one after
  focus_downloads  downloads pause while you play and carry on after (done in app.py)

Only what Cornerplay changed is changed back: Game Mode or do-not-disturb that was already
on stays on.
"""
import json
import os
import subprocess
from pathlib import Path

from . import host, syscontrol

RYOKU_FLAGS = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state") / "ryoku" / "flags.json"


def _run(cmd, timeout=5):
    if not host.which(cmd[0]):
        return None
    try:
        r = subprocess.run(host.argv(cmd), capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout if r.returncode == 0 else None


def _ryoku_flags(change=None):
    """Read Ryoku's shell flags, or merge `change` into them (the shell watches the file)."""
    try:
        data = json.loads(RYOKU_FLAGS.read_text())
    except (OSError, ValueError):
        return None
    if change:
        data.update(change)
        tmp = RYOKU_FLAGS.with_suffix(".cornerplay.tmp")
        tmp.write_text(json.dumps(data, indent=4))
        os.replace(tmp, RYOKU_FLAGS)  # atomic, as the shell itself writes it
    return data


def dnd_on() -> dict:
    """Quiet notifications; returns what to undo."""
    flags = _ryoku_flags()
    if flags is not None:
        if flags.get("gameMode"):
            return {}
        # Both flags: the shell turns DND on with Game Mode only when the switch is flipped in it.
        _ryoku_flags({"gameMode": True, "dnd": True, "gameDndPrev": bool(flags.get("dnd"))})
        return {"ryoku": True, "ryoku_dnd": bool(flags.get("dnd"))}
    if host.which("swaync-client"):
        was = (_run(["swaync-client", "-D"]) or "").strip() == "true"
        if not was:
            _run(["swaync-client", "-dn"])
        return {} if was else {"swaync": True}
    if host.which("dunstctl"):
        was = (_run(["dunstctl", "is-paused"]) or "").strip() == "true"
        if not was:
            _run(["dunstctl", "set-paused", "true"])
        return {} if was else {"dunst": True}
    if host.which("makoctl"):
        modes = (_run(["makoctl", "mode"]) or "").split()
        if "do-not-disturb" not in modes:
            _run(["makoctl", "mode", "-a", "do-not-disturb"])
            return {"mako": True}
        return {}
    if "GNOME" in os.environ.get("XDG_CURRENT_DESKTOP", "") and host.which("gsettings"):
        was = (_run(["gsettings", "get", "org.gnome.desktop.notifications", "show-banners"]) or "").strip()
        if was == "true":
            _run(["gsettings", "set", "org.gnome.desktop.notifications", "show-banners", "false"])
            return {"gnome": True}
    return {}


def dnd_off(undo: dict):
    if undo.get("ryoku"):
        _ryoku_flags({"gameMode": False, "dnd": bool(undo.get("ryoku_dnd"))})
    if undo.get("swaync"):
        _run(["swaync-client", "-df"])
    if undo.get("dunst"):
        _run(["dunstctl", "set-paused", "false"])
    if undo.get("mako"):
        _run(["makoctl", "mode", "-r", "do-not-disturb"])
    if undo.get("gnome"):
        _run(["gsettings", "set", "org.gnome.desktop.notifications", "show-banners", "true"])


class _WindowsAwake:
    """Windows: the screen stays on and the PC awake (SetThreadExecutionState) until terminate().
    The state belongs to the thread that set it: Cornerplay's main thread, which lives on."""
    ES_CONTINUOUS, ES_SYSTEM_REQUIRED, ES_DISPLAY_REQUIRED = 0x80000000, 0x00000001, 0x00000002

    def __init__(self):
        import ctypes
        self._set = ctypes.windll.kernel32.SetThreadExecutionState
        self._set.restype = ctypes.c_uint32
        self._set.argtypes = (ctypes.c_uint32,)
        if not self._set(self.ES_CONTINUOUS | self.ES_SYSTEM_REQUIRED | self.ES_DISPLAY_REQUIRED):
            raise OSError("SetThreadExecutionState failed")

    def terminate(self):
        self._set(self.ES_CONTINUOUS)


def stay_awake():
    """A process that keeps the screen on and the PC awake until it is stopped."""
    if os.name == "nt":
        try:
            return _WindowsAwake()
        except (OSError, AttributeError):
            return None
    if not host.which("systemd-inhibit"):
        return None
    try:
        return subprocess.Popen(host.argv(["systemd-inhibit", "--what=idle:sleep", "--who=Cornerplay",
                                           "--why=Playing a game", "--mode=block", "sleep", "infinity"]),
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError:
        return None


def begin(want: dict) -> dict:
    """A game started. want: {"dnd", "awake", "power"} from the settings. Returns the undo state."""
    undo = {}
    if want.get("dnd"):
        undo["dnd"] = dnd_on()
    if want.get("awake"):
        undo["awake"] = stay_awake()
    if want.get("power"):
        p = syscontrol.power_profiles()
        if p.get("profile") and p["profile"] != "performance" and "performance" in p.get("profiles", []):
            if syscontrol.set_power_profile("performance"):
                undo["power"] = p["profile"]
    if want.get("tdp"):  # the game's own power limit (tdp.py)
        from . import tdp
        before = tdp.current()
        err = tdp.apply(int(want["tdp"]))
        if err:
            undo["tdp_error"] = err
        elif before:
            undo["tdp"] = before
    if want.get("clips"):  # the replay buffer for "Save a clip" (clips.py)
        from . import clips
        undo["clips"] = clips.start(want["clips"])
    if want.get("lowlat") or want.get("quantum") or want.get("hdr"):
        from . import playtweaks
        if want.get("hdr"):  # the game's screen in HDR (Hyprland), when it can show it
            undo.update(playtweaks.hdr_begin())
        if want.get("lowlat"):  # tearing + VRR on Hyprland (Ryoku's Game Mode does it there)
            flags = _ryoku_flags()
            ryoku_gm = flags is not None and (bool(want.get("dnd")) or bool(flags.get("gameMode")))
            undo.update(playtweaks.low_latency_begin(ryoku_gm))
        if want.get("quantum"):  # a small PipeWire buffer (playtweaks.py)
            undo.update(playtweaks.audio_begin())
    if want.get("scheduler"):  # a gaming CPU scheduler (scx.py)
        from . import scx
        undo.update(scx.begin())
    if want.get("screen") or want.get("vrr"):  # the game's own screen mode / VRR (screenmode.py)
        from . import screenmode
        undo.update(screenmode.begin(want.get("screen") or "", bool(want.get("vrr"))))
    if want.get("audio"):  # the game's own sound output (audioout.py)
        from . import audioout
        undo.update(audioout.begin(want["audio"]))
    return undo


def end(undo: dict):
    """The last game closed: put back what begin() changed."""
    if undo.get("dnd"):
        dnd_off(undo["dnd"])
    proc = undo.get("awake")
    if proc is not None:
        try:
            proc.terminate() if os.name == "nt" else os.killpg(proc.pid, 15)
        except (OSError, ProcessLookupError):
            pass
    if undo.get("power"):
        syscontrol.set_power_profile(undo["power"])
    if undo.get("tdp"):
        from . import tdp
        tdp.apply(undo["tdp"])
    if undo.get("clips") is not None:
        from . import clips
        clips.stop(undo["clips"])
    if undo.get("lowlat") or undo.get("lowlat_rule") or undo.get("quantum") or undo.get("hdr"):
        from . import playtweaks
        playtweaks.hdr_end(undo)
        playtweaks.low_latency_end(undo)
        playtweaks.audio_end(undo)
    if undo.get("scx_before"):
        from . import scx
        scx.end(undo)
    if undo.get("screen_mode") or undo.get("vrr"):
        from . import screenmode
        screenmode.end(undo)
    if undo.get("audio_was"):
        from . import audioout
        audioout.end(undo)
