"""Before a game starts and after it closes (a game's Options > Before and after).

Each line is a command, run by the shell. Before the game: one after another, each given up to
a minute (connect a VPN, mount a drive, start a server), and a line ending in "&" is started and
left running (Discord, a mod manager, a music player). After it closes: one after another, in the
background. Output goes to the game's log folder. Lines starting with # are notes.

Presets in the dialog add the usual ones: open Discord, the performance power mode during the
game (power-profiles-daemon) and back to balanced after.
"""
import os
import re
import subprocess

from . import host
from .config import LOG_DIR

WAIT = 60

PRESETS = {
    "discord": {"before": "discord &", "after": ""},
    "power": {"before": "powerprofilesctl set performance", "after": "powerprofilesctl set balanced"},
    "close_discord": {"before": "", "after": "pkill -x Discord; pkill -x discord"},
}
if os.name == "nt":  # the same presets in Windows' words (Discord's own updater starts it)
    PRESETS = {
        "discord": {"before": '"%LOCALAPPDATA%\\Discord\\Update.exe" --processStart Discord.exe &', "after": ""},
        "power": {"before": "powercfg /setactive SCHEME_MIN", "after": "powercfg /setactive SCHEME_BALANCED"},
        "close_discord": {"before": "", "after": "taskkill /IM Discord.exe"},
    }


def lines(text):
    return [ln.strip() for ln in (text or "").splitlines() if ln.strip() and not ln.strip().startswith("#")]


def _log(key):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    return open(LOG_DIR / (re.sub(r"[^A-Za-z0-9_.-]", "_", key) + ".steps.log"), "a")


def _shell(script):
    """The command line that runs a line (or several) of the user's own commands: sh on Linux,
    cmd on Windows (several lines one after another, like sh's)."""
    if os.name == "nt":
        return ["cmd", "/d", "/c", " & ".join(ln for ln in script.splitlines() if ln.strip())]
    return host.argv(["sh", "-c", script])


def before(key, text):
    """Run the before-lines (blocking, on a worker thread). Returns the lines that failed."""
    failed = []
    for ln in lines(text):
        detached = ln.endswith("&")
        cmd = ln.rstrip("&").strip()
        if not cmd:
            continue
        with _log(key) as log:
            log.write(f"$ {ln}\n")
            log.flush()
            try:
                if detached:
                    subprocess.Popen(_shell(cmd), stdout=log, stderr=log, stdin=subprocess.DEVNULL,
                                     start_new_session=True, cwd=os.path.expanduser("~"))
                    continue
                r = subprocess.run(_shell(cmd), stdout=log, stderr=log, stdin=subprocess.DEVNULL,
                                   timeout=WAIT, cwd=os.path.expanduser("~"))
                if r.returncode != 0:
                    failed.append(cmd)
            except (OSError, subprocess.TimeoutExpired):
                failed.append(cmd)
    return failed


def after(key, text):
    """Start the after-lines, one after another, in the background."""
    todo = lines(text)
    if not todo:
        return
    script = "\n".join(ln.rstrip("&").strip() for ln in todo)
    with _log(key) as log:
        log.write("# after the game\n" + script + "\n")
        log.flush()
        try:
            subprocess.Popen(_shell(script), stdout=log, stderr=log, stdin=subprocess.DEVNULL,
                             start_new_session=True, cwd=os.path.expanduser("~"))
        except OSError:
            pass


def add_preset(current, extra):
    """current text plus the preset's lines that are not in it yet."""
    have = lines(current)
    new = [ln for ln in lines(extra) if ln not in have]
    return "\n".join([*(current or "").rstrip("\n").splitlines(), *new]).strip("\n")
