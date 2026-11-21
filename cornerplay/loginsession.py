"""A "Cornerplay (TV)" session at the login screen, like the Steam Deck's Game Mode.

Picking it at login starts gamescope with Cornerplay in TV mode, full screen; leaving TV mode ends
the session (back to the login screen). Installing it writes two files, which needs the
administrator's password once (pkexec):
  /usr/share/wayland-sessions/cornerplay.desktop   what the login screen lists
  /usr/local/bin/cornerplay-session                 starts gamescope + Cornerplay
Removing it deletes both.
"""
import os
import shlex
import shutil
import subprocess
import sys

from . import host

DESKTOP = "/usr/share/wayland-sessions/cornerplay.desktop"
SCRIPT = "/usr/local/bin/cornerplay-session"


def installed() -> bool:
    return os.path.isfile(DESKTOP) and os.path.isfile(SCRIPT)


def available() -> bool:
    return bool(shutil.which("gamescope")) and bool(shutil.which("pkexec"))


def launcher() -> str:
    """How this Cornerplay is started: its launcher, else Python on the package folder."""
    found = shutil.which("cornerplay")
    if found:
        return shlex.quote(found)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return f"env PYTHONPATH={shlex.quote(root)} {shlex.quote(sys.executable)} -m cornerplay"


def _script() -> str:
    return f"""#!/bin/sh
# Cornerplay (TV): a console-style session. Written by Cornerplay; remove it from Settings.
export XDG_CURRENT_DESKTOP=gamescope
export CORNERPLAY_SESSION=1
# full screen at the display's own resolution, adaptive sync where the screen has it
exec gamescope -e -f --adaptive-sync -- {launcher()} --tv --session
"""


DESKTOP_TEXT = """[Desktop Entry]
Name=Cornerplay (TV)
Comment=Your games, full screen, for the controller
Exec=/usr/local/bin/cornerplay-session
Type=Application
DesktopNames=gamescope
"""


def install() -> str:
    """"" when done, else why not. Asks for the administrator's password once."""
    if not available():
        return "Needs gamescope" if not shutil.which("gamescope") else "Needs pkexec"
    script = (f"mkdir -p /usr/share/wayland-sessions /usr/local/bin && "
              f"printf %s {shlex.quote(_script())} > {SCRIPT} && chmod 755 {SCRIPT} && "
              f"printf %s {shlex.quote(DESKTOP_TEXT)} > {DESKTOP} && chmod 644 {DESKTOP}")
    try:
        r = subprocess.run(host.argv(["pkexec", "sh", "-c", script]), capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.TimeoutExpired) as e:
        return type(e).__name__
    return "" if r.returncode == 0 else ((r.stderr or "").strip().splitlines() or ["not allowed"])[-1][-160:]


def remove() -> str:
    try:
        r = subprocess.run(host.argv(["pkexec", "rm", "-f", DESKTOP, SCRIPT]), capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.TimeoutExpired) as e:
        return type(e).__name__
    return "" if r.returncode == 0 else ((r.stderr or "").strip().splitlines() or ["not allowed"])[-1][-160:]
