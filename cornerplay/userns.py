"""Ubuntu (23.10 and newer: Kubuntu, Mint 22, Pop!_OS, ...) lets only programs with an AppArmor
profile create user namespaces. Proton under umu-launcher runs each game in a container
(pressure-vessel, from ~/.local/share/umu/steamrt*), and that container needs one: without a
profile every Windows game dies the moment it starts ("bwrap: No permissions to create a new
namespace"). Steam's own copy is covered by Ubuntu's "steam" profile; umu's is not.

The fix is the same kind of profile Ubuntu ships for Steam, for umu's runtime, installed once
with the administrator password (pkexec shows the system's own password prompt).
"""
import os
import shutil
import subprocess
import tempfile

SYSCTL = "/proc/sys/kernel/apparmor_restrict_unprivileged_userns"
PROFILE = "/etc/apparmor.d/cornerplay-umu"
PROFILE_TEXT = """\
# Cornerplay: lets Proton's container from umu-launcher (pressure-vessel) create user namespaces,
# as Ubuntu's own "steam" profile does for Steam. Remove this file to undo.
abi <abi/4.0>,
include <tunables/global>

profile cornerplay-umu @{HOME}/.local/share/umu/**/pressure-vessel/** flags=(unconfined) {
  userns,

  include if exists <local/cornerplay-umu>
}
"""


def restricted() -> bool:
    """This kernel lets only AppArmor-profiled programs create user namespaces."""
    try:
        with open(SYSCTL) as f:
            return f.read().strip() == "1"
    except OSError:
        return False


def blocked() -> bool:
    """Windows games through umu would crash at start right now."""
    return restricted() and not os.path.exists(PROFILE)


def manual_command() -> str:
    """What to paste in a terminal when there is no password prompt (pkexec) to ask with."""
    return ("printf '%s' '" + PROFILE_TEXT.replace("'", "'\\''") + "' | sudo tee " + PROFILE
            + " >/dev/null && sudo apparmor_parser -r " + PROFILE)


def allow() -> bool:
    """Install the profile, asking for the administrator password. True when it is in place."""
    if not blocked():
        return True
    pkexec = shutil.which("pkexec")
    if not pkexec or not (os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY")):
        return False
    fd, tmp = tempfile.mkstemp(prefix="cornerplay-umu.", suffix=".apparmor")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(PROFILE_TEXT)
        os.chmod(tmp, 0o644)
        script = 'install -m 644 "$1" "$2" && apparmor_parser -r "$2"'
        subprocess.run([pkexec, "sh", "-c", script, "sh", tmp, PROFILE], timeout=300,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.TimeoutExpired):
        pass
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    return not blocked()
