"""Xbox / PC Game Pass games on Linux, through Nexus Launcher (built on Xodus).

Nexus Launcher (github.com/domsvoboda/nexus-launcher, MIT) signs in to the Microsoft account,
downloads Xbox PC games with their licences and runs them in its own Wine. Cornerplay installs
it for you (the newest release, checked against GitHub's SHA-256 and the release's own SHA-512,
then laid out by Nexus's own installer script from the same release, so Nexus's updates and
shortcuts keep working), lists the games it installed, and starts them with --launch-game.

Unofficial: neither Nexus nor Xodus comes from Microsoft, and some games do not run yet.

    python -m cornerplay.nexus install       install or update Nexus Launcher
    python -m cornerplay.nexus open [ID]     install it if needed, then open it (or start game ID)
"""
import ctypes.util
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = "domsvoboda/nexus-launcher"
HOME = Path.home()
APP_DIR = Path(os.environ.get("XODUS_NEXUS_PREFIX") or HOME / ".local") / "opt" / "xodus-nexus"
APPIMAGES = ("Nexus-Launcher.AppImage", "Xodus-Nexus.AppImage")  # the current name, then the old one
PROFILE = Path(os.environ.get("XDG_CONFIG_HOME") or HOME / ".config") / "xodus-nexus"
MIN_GLIBC = (2, 38)
# Libraries Nexus needs from the system (its installer installs these with sudo, which a window
# cannot do): what to look for, and the pkgs.NAMES entry that installs it.
LIBS = {"fuse": "nexus-fuse", "webkit2gtk-4.1": "nexus-webkit", "gtk-3": "nexus-gtk", "nss3": "nexus-nss",
        "Xtst": "nexus-xtst"}


def appimage():
    """Nexus Launcher's program, or None when it is not installed."""
    for name in APPIMAGES:
        p = APP_DIR / name
        if p.is_file() and os.access(p, os.X_OK):
            return str(p)
    found = shutil.which("xodus-nexus")
    return os.path.realpath(found) if found else None


def glibc():
    try:
        v = os.confstr("CS_GNU_LIBC_VERSION") or ""  # "glibc 2.42"
        return tuple(int(x) for x in v.split()[-1].split(".")[:2])
    except (ValueError, OSError, IndexError, AttributeError):
        return (0, 0)


def unsupported() -> str:
    """Why Nexus cannot run on this PC ("" when it can)."""
    import platform
    if not sys.platform.startswith("linux"):
        return "Nexus Launcher is for Linux"
    if platform.machine() != "x86_64":
        return "Nexus Launcher is published for x86_64 PCs only"
    if glibc() < MIN_GLIBC:
        return "Nexus Launcher needs a newer Linux (glibc 2.38 or later: Ubuntu 24.04, a current Fedora, Arch or SteamOS)"
    return ""


def missing_libs() -> list:
    """The pkgs.NAMES keys of the system libraries Nexus needs and this PC lacks."""
    return [key for lib, key in LIBS.items() if not ctypes.util.find_library(lib)]


def env() -> dict:
    """Extra environment for starting the AppImage: without FUSE 2 it unpacks itself and runs."""
    return {} if ctypes.util.find_library("fuse") else {"APPIMAGE_EXTRACT_AND_RUN": "1"}


# --- what Nexus has installed -------------------------------------------------------------------
def state() -> dict:
    try:
        with open(PROFILE / "launcher-state.json", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def games() -> list:
    """Games Nexus installed: [{"id", "title", "path", "storeId", "cover", "hero", "ready"}]."""
    out = []
    for g in state().get("games") or []:
        if not isinstance(g, dict) or not g.get("id") or not g.get("path"):
            continue
        out.append({"id": str(g["id"]), "title": str(g.get("title") or g["id"]), "path": str(g["path"]),
                    "storeId": str(g.get("storeId") or ""), "cover": str(g.get("coverUrl") or ""),
                    "hero": str(g.get("heroUrl") or ""),
                    "ready": g.get("installState") in ("ready", "imported") and not g.get("updateIncomplete")})
    return out


def backend() -> str:
    """The Xbox backend (xodus-cli): Cornerplay's own copy first (xodus.py), else Nexus's."""
    from .xodus import backend as own
    return own()


def _nexus_backend() -> str:
    try:
        with open(PROFILE / "xodus-backends" / "current.json", encoding="utf-8") as f:
            path = str((json.load(f) or {}).get("binaryPath") or "")
    except (OSError, ValueError, AttributeError):
        return ""
    return path if path and os.access(path, os.X_OK) else ""


OWNED_TTL = 6 * 3600


def owned(force: bool = False) -> list:
    """The Store product ids of the games the signed-in Microsoft account owns (bought, not only
    installed), read by Nexus's backend without starting a sign-in. Cached for a few hours; the
    cached list when it cannot be asked, [] when Nexus is not signed in."""
    import time
    from .config import CACHE_DIR, read_json, write_json
    cache = CACHE_DIR / "xbox-owned.json"
    cached = read_json(cache) or {}
    if not force and time.time() - cached.get("t", 0) < OWNED_TTL:
        return list(cached.get("ids") or [])
    exe = backend()
    if not exe:
        return list(cached.get("ids") or [])
    try:
        r = subprocess.run([exe, "library", "--json"], capture_output=True, text=True, timeout=90,
                           stdin=subprocess.DEVNULL)
        data = json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else None
    except (OSError, subprocess.SubprocessError, ValueError):
        data = None
    if not isinstance(data, dict):
        return list(cached.get("ids") or [])
    from .gamepass import PASSES
    ids, via_pass, passes = [], False, set()
    for e in data.get("entitlements") or []:
        if not isinstance(e, dict) or e.get("isTrial") or str(e.get("status") or "Active") != "Active":
            continue
        if any(str(e.get(k) or "").startswith(PASS_PREFIX) for k in ("productId", "satisfiedByProductId")):
            via_pass = True  # the pass itself, or a game that comes with it
        passes.update(str(e.get(k) or "") for k in ("productId", "satisfiedByProductId")
                      if str(e.get(k) or "") in PASSES)
        pid = str(e.get("productId") or "").strip()
        if pid and pid not in ids and not pid.startswith(PASS_PREFIX):
            ids.append(pid)
    write_json(cache, {"t": time.time(), "ids": ids, "pass": via_pass, "passes": sorted(passes)})
    return ids


PASS_PREFIX = "CFQ7TTC0"  # Microsoft's subscription products: Game Pass Ultimate, PC Game Pass...


def gamepass_tier() -> str:
    """Which Game Pass the signed-in account has: "full" (Ultimate or PC Game Pass), "premium",
    "essential", "starter", "console", or "" for none. Nexus checks the membership with Microsoft
    and keeps the answer with the profile ("active" plus the pass's product ids); the passes in the
    library count too. A pass that is active but names no product we know counts as "full"."""
    from datetime import datetime, timezone
    from .config import CACHE_DIR, read_json
    from .gamepass import TIER_RANK, tier_of
    best = ""
    for path in _profile_files("xbox-profile-license.json", "xbox-profile.json"):
        try:
            with open(path, encoding="utf-8") as f:
                sub = (json.load(f) or {}).get("subscription") or {}
        except (OSError, ValueError, AttributeError):
            continue
        if not isinstance(sub, dict):
            continue
        if str(sub.get("status") or "").lower() == "active" or sub.get("productIds"):
            until = str(sub.get("validUntil") or "")
            try:
                if until and datetime.fromisoformat(until.replace("Z", "+00:00")) < datetime.now(timezone.utc):
                    continue  # ran out
            except ValueError:
                pass
            tier = tier_of(sub.get("productIds") or []) or "full"
            if TIER_RANK[tier] > TIER_RANK[best]:
                best = tier
    owned = read_json(CACHE_DIR / "xbox-owned.json") or {}
    tier = tier_of(owned.get("passes") or []) or ("full" if owned.get("pass") and not owned.get("passes") else "")
    return tier if TIER_RANK[tier] > TIER_RANK[best] else best


def gamepass_member() -> bool:
    """Does the signed-in account have a Game Pass with PC games? (see gamepass_tier)"""
    return gamepass_tier() not in ("", "console")


def _profile_files(*names) -> list:
    """The account files: Cornerplay's own copy (xodus.read_profile, from its sign-in) first, then
    Nexus Launcher's."""
    from .xodus import account_dir
    return [d / n for d in (account_dir(), PROFILE) for n in names]


def gamertag() -> str:
    for path in _profile_files("xbox-profile.json", "xbox-profile-license.json"):
        try:
            with open(path, encoding="utf-8") as f:
                tag = (json.load(f) or {}).get("gamertag") or ""
            if tag:
                return str(tag)
        except (OSError, ValueError, AttributeError):
            continue
    return ""


def argv(game_id: str = "") -> list:
    """Open Nexus Launcher, or start one of its games (it waits until the game closes)."""
    exe = appimage()
    if not exe:
        raise FileNotFoundError("Nexus Launcher is not installed")
    return [exe, *(["--launch-game", game_id] if game_id else [])]


# --- installing it --------------------------------------------------------------------------------
def install(log=print) -> str:
    """Download the newest Nexus Launcher, check it, and install it the way its own installer does
    (into ~/.local/opt/xodus-nexus, a xodus-nexus command, an application-menu entry). Returns the
    AppImage's path. System libraries are left to the user (missing_libs())."""
    why = unsupported()
    if why:
        raise RuntimeError(why)
    from .config import CACHE_DIR
    from .net import download_checked, github_asset, requests
    tag, url, sha256 = github_asset(REPO, lambda n: n.endswith("-x86_64.AppImage"))
    if not sha256:
        raise RuntimeError("GitHub lists no checksum for Nexus Launcher's download; not installing it unchecked")
    name = url.rsplit("/", 1)[-1]
    log(f"Nexus Launcher {tag}: downloading {name}")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = download_checked(url, CACHE_DIR / name, sha256, mode=0o755)
    try:
        sums = requests.get(url + ".sha512sum", timeout=30)
        sums.raise_for_status()
        sha512 = sums.text.split()[0].strip().lower()
        h = hashlib.sha512()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        if h.hexdigest() != sha512:
            raise RuntimeError("Nexus Launcher's download does not match its published SHA-512")
        # Nexus's installer from the same release lays it out (and updates an earlier copy in place).
        script = requests.get(f"https://raw.githubusercontent.com/{REPO}/{tag}/scripts/install.sh", timeout=30)
        script.raise_for_status()
        script_path = CACHE_DIR / "nexus-install.sh"
        script_path.write_text(script.text, encoding="utf-8")
        mode = "upgrade" if appimage() else "install"
        env = dict(os.environ, XODUS_NEXUS_SKIP_DEPS="1", XODUS_NEXUS_MODE=mode,
                   XODUS_NEXUS_APPIMAGE=str(path), XODUS_NEXUS_APPIMAGE_SHA512=sha512)
        r = subprocess.run(["bash", str(script_path), f"--{mode}"], env=env, stdin=subprocess.DEVNULL,
                           capture_output=True, text=True, timeout=600)
        if r.returncode != 0:
            tail = [ln for ln in (r.stderr or r.stdout or "").splitlines() if ln.strip()][-1:] or ["no details"]
            raise RuntimeError("Nexus Launcher's installer failed: " + tail[0][-200:])
    finally:
        Path(path).unlink(missing_ok=True)
    exe = appimage()
    if not exe:
        raise RuntimeError("Nexus Launcher was installed but cannot be found")
    log(f"Nexus Launcher {tag}: installed at {exe}")
    return exe


def latest_tag() -> str:
    from .net import latest_release
    return latest_release(REPO).get("tag_name", "")


WINDOW_CLASS = "org.xodusgaming.nexus"


def running() -> bool:
    """Is Nexus Launcher open? Its profile's SingletonLock points at "<host>-<pid>"."""
    try:
        pid = int(os.readlink(PROFILE / "SingletonLock").rsplit("-", 1)[1])
    except (OSError, ValueError, IndexError):
        return False
    from .osinfo import pid_alive
    return pid_alive(pid)


def raise_window() -> bool:
    """Bring an open Nexus Launcher to the front. A second start without a game does nothing in
    Nexus (it only hands over --launch-game), so Cornerplay does it: Hyprland by IPC, else
    wmctrl or kdotool where present. False when it is not open or could not be raised."""
    if not running():
        return False
    from . import hypr
    if hypr.running():
        for c in hypr.clients():
            if str(c.get("class") or "") == WINDOW_CLASS and c.get("address"):
                return hypr.focus_window(c["address"])
    for cmd in (["wmctrl", "-x", "-a", WINDOW_CLASS], ["kdotool", "search", "--class", WINDOW_CLASS, "windowactivate"]):
        if shutil.which(cmd[0]):
            try:
                if subprocess.run(cmd, capture_output=True, timeout=5).returncode == 0:
                    return True
            except (OSError, subprocess.SubprocessError):
                pass
    return False


def main(args=None):
    args = list(sys.argv[1:] if args is None else args)
    what = args[0] if args else "open"
    if what == "install":
        try:
            install()
            return 0
        except Exception as e:
            print(f"Nexus Launcher: not installed: {e}", file=sys.stderr)
            return 1
    if what == "open":
        if len(args) < 2 and raise_window():  # already open: Nexus ignores a second plain start
            return 0
        if not appimage():
            try:
                install()
            except Exception as e:
                print(f"Nexus Launcher: not installed: {e}", file=sys.stderr)
                return 1
        cmd = argv(args[1] if len(args) > 1 else "")
        os.execvpe(cmd[0], cmd, dict(os.environ, **env()))
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
