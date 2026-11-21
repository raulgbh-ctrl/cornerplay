"""Sound output per game (PipeWire / PulseAudio): headphones for one game, the TV for another.

A game can name an output (a sink) in its Options. While it plays, that output is the default
one, so the game's sound goes there whoever started it (Steam too); when the last game closes,
the default goes back to what it was. Games Cornerplay starts itself also get PULSE_SINK and
PIPEWIRE_NODE, so their sound starts on that output from the first moment.

Uses pactl (PipeWire's pipewire-pulse or PulseAudio), which every desktop with sound has.
"""
import json
import subprocess

from . import host


def _pactl(*args, timeout=5):
    if not host.which("pactl"):
        return None
    try:
        r = subprocess.run(host.argv(["pactl", *args]), capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout if r.returncode == 0 else None


def outputs() -> list:
    """[{"name", "label"}] for every output, by its human name ("Apple Audio Device", "HDMI / TV")."""
    out = _pactl("-f", "json", "list", "sinks")
    if out:
        try:
            return [{"name": s["name"], "label": s.get("description") or s["name"]}
                    for s in json.loads(out) if isinstance(s, dict) and s.get("name")]
        except ValueError:
            pass
    # An older pactl without JSON: the short list has the names only.
    rows = []
    for line in (_pactl("list", "short", "sinks") or "").splitlines():
        parts = line.split("\t")
        if len(parts) > 1:
            rows.append({"name": parts[1], "label": parts[1]})
    return rows


def default() -> str:
    return (_pactl("get-default-sink") or "").strip()


def set_default(name: str) -> bool:
    return bool(name) and _pactl("set-default-sink", name) is not None


def env(name: str) -> dict:
    """For a game Cornerplay starts: its sound goes to this output from the start."""
    return {"PULSE_SINK": name, "PIPEWIRE_NODE": name} if name else {}


def begin(name: str) -> dict:
    """Make `name` the default output while a game plays; returns what to undo ({} if nothing).
    An output that is gone (unplugged headphones) is left alone."""
    if not name or name not in {o["name"] for o in outputs()}:
        return {}
    was = default()
    if was == name or not set_default(name):
        return {}
    return {"audio_was": was}


def end(undo: dict):
    was = (undo or {}).get("audio_was")
    if was and was in {o["name"] for o in outputs()}:
        set_default(was)
