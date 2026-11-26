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
    """Nexus's own command-line backend (xodus-cli), "" before Nexus has fetched it."""
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
    ids = []
    for e in data.get("entitlements") or []:
        if not isinstance(e, dict) or e.get("isTrial") or str(e.get("status") or "Active") != "Active":
            continue
        pid = str(e.get("productId") or "").strip()
        if pid and pid not in ids:
            ids.append(pid)
    write_json(cache, {"t": time.time(), "ids": ids})
    return ids


def gamertag() -> str:
    for name in ("xbox-profile.json", "xbox-profile-license.json"):
        try:
            with open(PROFILE / name, encoding="utf-8") as f:
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
