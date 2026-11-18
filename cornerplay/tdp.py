"""A power limit per game (TDP) on AMD handhelds and laptops, through ryzenadj.

ryzenadj needs root. Cornerplay never asks for a password at a game's start: it runs
`sudo -n ryzenadj` and, when sudo would ask, says how to allow it once (Health / the toast):
    echo "$USER ALL=(root) NOPASSWD: $(command -v ryzenadj)" | sudo tee /etc/sudoers.d/cornerplay-ryzenadj
The limit is put back to what it was when the last game closes. Fan curves are left to the
firmware: there is no common, safe interface for them across machines.
"""
import re
import shutil
import subprocess

STEPS = (0, 5, 8, 10, 12, 15, 18, 20, 25, 30)  # watts; 0: leave it alone
SUDOERS = 'echo "$USER ALL=(root) NOPASSWD: $(command -v ryzenadj)" | sudo tee /etc/sudoers.d/cornerplay-ryzenadj'


def available() -> bool:
    if not shutil.which("ryzenadj"):
        return False
    try:
        with open("/proc/cpuinfo") as f:
            return "AuthenticAMD" in f.read(4096)
    except OSError:
        return False


def _run(args, timeout=5):
    try:
        r = subprocess.run(["sudo", "-n", shutil.which("ryzenadj") or "ryzenadj", *args],
                           capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r


def current() -> int:
    """The sustained (STAPM) limit in watts now, or 0 when it cannot be read."""
    r = _run(["-i"])
    if not r or r.returncode != 0:
        return 0
    m = re.search(r"STAPM LIMIT\s*\|\s*([\d.]+)", r.stdout)
    return int(round(float(m.group(1)))) if m else 0


def apply(watts: int) -> str:
    """Set all three limits (sustained, slow and fast boost a little above). "" or an error."""
    if not available():
        return "ryzenadj is not installed (or this is not an AMD CPU)"
    mw = int(watts) * 1000
    r = _run([f"--stapm-limit={mw}", f"--slow-limit={mw}", f"--fast-limit={int(mw * 1.2)}"])
    if r is None:
        return "ryzenadj did not answer"
    if r.returncode != 0:
        if "password" in (r.stderr or "").lower() or "sudo" in (r.stderr or "").lower():
            return "ryzenadj needs root: allow it once with " + SUDOERS
        return (r.stderr or r.stdout or "ryzenadj failed").strip().splitlines()[-1]
    return ""
