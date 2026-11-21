"""A gaming CPU scheduler while you play (sched-ext, CachyOS and other kernels built with it).

sched-ext lets the kernel run a scheduler loaded at runtime. LAVD in its Gaming mode keeps a game's
frames steady while other programs run. scx_loader starts and stops them for the desktop (scxctl
talks to it over D-Bus); its policy asks an administrator's password each time, so turning the
setting on installs, with one password, a polkit rule that lets you (an administrator in the
wheel group, at the PC) switch schedulers without it. Remove it with that rule's file.

begin() switches to LAVD Gaming and remembers what ran before; end() puts that back (or stops the
scheduler when none ran, so the kernel's own one is back).
"""
import os
import re
import subprocess

from . import host

RULE = "/etc/polkit-1/rules.d/50-cornerplay-scx.rules"
RULE_TEXT = """// Cornerplay: switch sched-ext schedulers while playing, without a password, for
// administrators sitting at the PC. Delete this file to undo.
polkit.addRule(function(action, subject) {
    if (action.id == "org.scx.loader.manage-schedulers" &&
        subject.local && subject.active && subject.isInGroup("wheel")) {
        return polkit.Result.YES;
    }
});
"""
SCHED, MODE = "lavd", "gaming"


def available() -> bool:
    return bool(host.which("scxctl")) and os.path.exists("/sys/kernel/sched_ext/state")


def _scxctl(*args, timeout=15):
    try:
        r = subprocess.run(host.argv(["scxctl", *args]), capture_output=True, text=True, timeout=timeout,
                           stdin=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout if r.returncode == 0 else None


def current():
    """(scheduler, mode) running now, or None. scxctl get: "running Lavd in Gaming mode"."""
    out = _scxctl("get") or ""
    m = re.search(r"running (\w+)(?: in (\w+) mode)?", out, re.I)
    return (m.group(1).lower(), (m.group(2) or "auto").lower()) if m else None


def install_rule() -> str:
    """Asks for the administrator's password once (pkexec). "" when done, else why not."""
    if not host.which("pkexec"):
        return "pkexec is missing"
    try:
        r = subprocess.run(host.argv(["pkexec", "sh", "-c", f"cat > {RULE} && chmod 644 {RULE}"]),
                           input=RULE_TEXT, capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.TimeoutExpired) as e:
        return type(e).__name__
    return "" if r.returncode == 0 else ((r.stderr or "").strip().splitlines() or ["not allowed"])[-1][-160:]


def begin() -> dict:
    """Switch to LAVD Gaming; returns what to undo ({} when nothing changed)."""
    if not available():
        return {}
    before = current()
    if before == (SCHED, MODE):
        return {}
    ok = _scxctl("switch", "--sched", SCHED, "--mode", MODE) if before else _scxctl("start", "--sched", SCHED, "--mode", MODE)
    if ok is None:
        return {}
    return {"scx_before": list(before) if before else "none"}


def end(undo: dict):
    before = (undo or {}).get("scx_before")
    if not before:
        return
    if before == "none":
        _scxctl("stop")
    else:
        _scxctl("switch", "--sched", before[0], "--mode", before[1])
