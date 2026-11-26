"""Xbox and PC Game Pass games on Linux, inside Cornerplay (no Nexus Launcher window needed).

The hard parts are Xodus's (GPL-3.0, github.com/xodus-gaming/xodus) as patched by the Nexus
project, and they run here as separate programs, downloaded from their own releases and checked
against the checksums published with them:

- the backend, xodus-cli (domsvoboda/nexus-backend, ~9 MB): the Microsoft account (kept in the
  system keyring, so a sign-in made in Nexus Launcher counts here too), what the account owns,
  downloading a game (`streaming`, with progress, pause and resume), and starting it (`run`);
- the runtime (domsvoboda/nexus-runtime, ~355 MB): Proton with the pieces Xbox PC games need
  (xgameruntime.dll and friends).

What this module adds is Nexus Launcher's glue, ported from its source: one Proton prefix per
game with the runtime's checked components in it, and the launch script `run` is given as Wine.

    python -m cornerplay.xodus install <product id> <folder>   (prints Progress: lines)
    python -m cornerplay.xodus play <folder>                    (runs the game until it closes)
"""
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import time
from pathlib import Path

from .config import DATA_DIR, settings

ROOT = DATA_DIR / "xbox"
BACKEND_REPO = "domsvoboda/nexus-backend"
RUNTIME_REPO = "domsvoboda/nexus-runtime"
STATE = ROOT / "games.json"     # {product id: {"title", "path", "contentId", "exe", "installed": t}}
PROGRESS_PREFIX = "NEXUS_PROGRESS "
UMU_ID = "xodus-nexus"


# --- the backend --------------------------------------------------------------------------------
def backend() -> str:
    """xodus-cli: Cornerplay's own copy, else Nexus Launcher's ("" when there is neither)."""
    own = sorted((ROOT / "backend").glob("*/xodus-cli"))
    for exe in reversed(own):
        if os.access(exe, os.X_OK):
            return str(exe)
    from .nexus import _nexus_backend
    return _nexus_backend()


def _release_with_sha512(repo: str, suffix: str):
    """(tag, url, sha512, name) of the newest release asset ending in suffix, checked by the
    .sha512sum file published next to it."""
    from .net import latest_release, requests
    rel = latest_release(repo)
    assets = {a.get("name", ""): a.get("browser_download_url", "") for a in rel.get("assets") or []}
    name = next((n for n in assets if n.endswith(suffix) and "-source" not in n), "")
    if not name:
        raise RuntimeError(f"{repo}: no {suffix} in the newest release")
    sums = next((u for n, u in assets.items() if n == name.replace(".tar.xz", ".sha512sum")), "")
    if not sums:
        raise RuntimeError(f"{repo}: no published checksum for {name}; not installing it unchecked")
    text = requests.get(sums, timeout=30).text
    m = re.search(r"\b([0-9a-f]{128})\b", text)
    if not m:
        raise RuntimeError(f"{repo}: the checksum file could not be read")
    return rel.get("tag_name", ""), assets[name], m.group(1), name


def _download_sha512(url, dest: Path, sha512: str, progress=None):
    from .net import requests
    tmp = Path(str(dest) + ".part")
    h = hashlib.sha512()
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length") or 0)
        done = 0
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
                h.update(chunk)
                done += len(chunk)
                if progress and total:
                    progress(done, total)
    if h.hexdigest() != sha512:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"{dest.name} did not match its published checksum; deleted")
    tmp.rename(dest)


def _unpack(archive: Path, into: Path):
    tmp = Path(str(into) + ".part")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    with tarfile.open(archive) as t:
        try:
            t.extractall(tmp, filter="tar")
        except TypeError:  # Python before 3.12 has no extraction filter
            for m in t.getmembers():
                if m.name.startswith("/") or ".." in Path(m.name).parts:
                    raise RuntimeError(f"Unsafe path in {archive.name}: {m.name}")
            t.extractall(tmp)
    shutil.rmtree(into, ignore_errors=True)
    tmp.rename(into)
    archive.unlink(missing_ok=True)


def install_backend(log=print) -> str:
    tag, url, sha512, name = _release_with_sha512(BACKEND_REPO, "-linux-x86_64.tar.xz")
    folder = ROOT / "backend" / tag
    if not (folder / "xodus-cli").exists():
        folder.parent.mkdir(parents=True, exist_ok=True)
        log(f"Downloading the Xbox backend ({tag})")
        archive = folder.parent / name
        _download_sha512(url, archive, sha512)
        _unpack(archive, folder)
        inner = [p for p in folder.iterdir() if p.is_dir()]
        if not (folder / "xodus-cli").exists() and len(inner) == 1 and (inner[0] / "xodus-cli").exists():
            for p in inner[0].iterdir():
                p.rename(folder / p.name)
            inner[0].rmdir()
    return backend()


# --- the runtime --------------------------------------------------------------------------------
def runtime() -> Path | None:
    """The newest Nexus Runtime here (a Proton folder), else Nexus Launcher's own."""
    found = sorted(p for p in (ROOT / "runtime").glob("*/*") if (p / "proton").exists())
    if found:
        return found[-1]
    nexus = sorted(p for p in (Path.home() / ".local/share/xodus-nexus/runtimes").glob("**/proton") if p.is_file())
    return nexus[-1].parent if nexus else None


def install_runtime(progress=None, log=print) -> Path:
    tag, url, sha512, name = _release_with_sha512(RUNTIME_REPO, "-x86_64.tar.xz")
    folder = ROOT / "runtime" / tag
    if not any(folder.glob("*/proton")):
        folder.parent.mkdir(parents=True, exist_ok=True)
        log(f"Downloading the Xbox game runtime ({tag}, about 350 MB, once)")
        archive = folder.parent / name
        _download_sha512(url, archive, sha512, progress)
        _unpack(archive, folder)
    return runtime()


# --- what is installed ----------------------------------------------------------------------------
def state() -> dict:
    try:
        with open(STATE, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_state(data: dict):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1))
    tmp.replace(STATE)


def games() -> list:
    """Games Cornerplay installed itself: [{"id", "title", "path", "storeId", "ready"}]."""
    out = []
    for pid, g in state().items():
        if isinstance(g, dict) and g.get("path"):
            out.append({"id": "xb-" + pid, "title": g.get("title") or pid, "path": g["path"], "storeId": pid,
                        "ready": bool(g.get("installed")) and os.path.isdir(g["path"])})
    return out


def find_exe(folder: str) -> str:
    """The game's program, as its MicrosoftGame.config names it."""
    from .winxbox import parse_config
    for name in os.listdir(folder) if os.path.isdir(folder) else []:
        if name.lower() == "microsoftgame.config":
            exe = parse_config(os.path.join(folder, name)).get("exe") or ""
            if exe:
                return exe
    return ""


def resolve(product_id: str) -> dict:
    """The PC package to download for a product: {"contentId", "downloadBytes", "title"}."""
    r = subprocess.run([backend(), "resolve-package", product_id, "--json", "--market", _market()],
                       capture_output=True, text=True, timeout=120, stdin=subprocess.DEVNULL)
    data = json.loads(r.stdout or "{}")
    for c in data.get("choices") or []:
        if c.get("supported") and c.get("platform") == "Windows.Desktop":
            return c
    for c in data.get("choices") or []:
        if c.get("supported"):
            return c
    raise RuntimeError("Microsoft has no PC version of this game that can be installed here")


def _market() -> str:
    from .gamepass import market
    return market()


def install(product_id: str, folder: str, title: str = "") -> int:
    """Download (or carry on downloading) a game into folder, printing Cornerplay's progress
    lines; it is ready to play once this returns 0."""
    exe = backend() or install_backend()
    if not exe:
        print("The Xbox backend could not be installed", file=sys.stderr)
        return 1
    if not runtime():
        def rt_progress(done, total):
            print(f"Progress: {done * 100 / total:.1f}% ({done / 2**20:.1f} MiB/s) runtime", flush=True)
        install_runtime(rt_progress)
    choice = resolve(product_id)
    os.makedirs(folder, exist_ok=True)
    data = state()
    data[product_id] = {**data.get(product_id, {}), "title": title or choice.get("title") or product_id,
                        "path": folder, "contentId": choice.get("contentId", ""), "installed": 0}
    _save_state(data)
    p = subprocess.Popen([exe, "streaming", product_id, folder, "--selected-content-id", choice["contentId"],
                          "--progress-json", "--market", _market()],
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, text=True)
    t0 = time.monotonic()
    for line in p.stdout:
        line = line.strip()
        if not line.startswith(PROGRESS_PREFIX):
            if line:
                print(line, flush=True)
            continue
        try:
            ev = json.loads(line[len(PROGRESS_PREFIX):])
        except ValueError:
            continue
        done, total, speed = ev.get("completedBytes") or 0, ev.get("totalBytes") or 0, ev.get("bytesPerSecond") or 0
        if total:
            pct = done * 100 / total
            eta = int((total - done) / speed) if speed else 0
            print(f"Progress: {pct:.1f}% {speed / 2**20:.1f} MiB/s ETA: {eta // 3600:02d}:{eta % 3600 // 60:02d}:{eta % 60:02d}"
                  f" ({ev.get('phase', '')})", flush=True)
        if ev.get("phase") == "complete":
            break
    code = p.wait()
    if code == 0:
        data = state()
        data[product_id].update(installed=time.time(), exe=find_exe(folder))
        _save_state(data)
        print(f"Installed in {time.monotonic() - t0:.0f} s", flush=True)
    return code


def uninstall(product_id: str) -> None:
    data = state()
    g = data.pop(product_id, None) or {}
    if g.get("path") and os.path.isdir(g["path"]) and Path(g["path"]).resolve() != Path.home().resolve():
        shutil.rmtree(g["path"], ignore_errors=True)
    shutil.rmtree(_prefix_dir(product_id), ignore_errors=True)
    _save_state(data)


# --- playing: Nexus Launcher's Proton runner, ported ---------------------------------------------
def _prefix_dir(product_id: str) -> Path:
    return ROOT / "prefixes" / re.sub(r"[^A-Za-z0-9_-]", "_", product_id)


def _q(v) -> str:
    return shlex.quote(str(v))


def _patch(root: Path) -> dict:
    try:
        return json.loads((root / "XODUS_NEXUS_PATCH.json").read_text())
    except (OSError, ValueError):
        return {}


def _components(root: Path, meta: dict) -> list:
    """The runtime pieces Nexus copies into each prefix's system32, by the runtime's features."""
    feats = set(meta.get("features") or [])
    dxvk = ["d3d8.dll", "d3d9.dll", "d3d10core.dll", "d3d11.dll", "dxgi.dll"]
    names = ((["libnghttp2.dll"] if "wine-winhttp-http2-v1" in feats else [])
             + (["windows.web.dll"] if "winrt-json-v1" in feats else [])
             + (["libvkd3d-shader-1.dll"] if "hlsl-state-keywords-v1" in feats else [])
             + (["twinapi.appcore.dll"] if "appstate-registration-v1" in feats else [])
             + (dxvk if "dxvk-constant-compare-v1" in feats else []))
    expected = (meta.get("componentsByArch") or {}).get("x86_64-windows") or meta.get("components") or {}
    out = []
    for name in names:
        lib = "vkd3d" if name == "libvkd3d-shader-1.dll" else "wine/dxvk" if name in dxvk else "wine"
        src = root / "files" / "lib" / lib / "x86_64-windows" / name
        data = src.read_bytes()
        if expected.get(name) != hashlib.sha256(data).hexdigest():
            raise RuntimeError(f"The Xbox runtime has an invalid {name} checksum")
        out.append((name, data))
    return out


def prepare(product_id: str) -> Path:
    """Make (once) and refresh the game's Proton prefix; returns the launch script `run` uses."""
    root = runtime()
    if not root:
        raise RuntimeError("The Xbox game runtime is not installed")
    compat = _prefix_dir(product_id)
    steam = ROOT / "steam"
    compat.mkdir(parents=True, exist_ok=True)
    steam.mkdir(parents=True, exist_ok=True)
    base_env = {**os.environ, "STEAM_COMPAT_DATA_PATH": str(compat), "STEAM_COMPAT_CLIENT_INSTALL_PATH": str(steam),
                "SteamAppId": "0", "SteamGameId": "0", "UMU_ID": UMU_ID, "UMU_USE_STEAM": "0",
                "PYTHONDONTWRITEBYTECODE": "1"}
    if not (compat / "pfx" / "system.reg").exists():
        subprocess.run([str(root / "proton"), "run", "cmd", "/c", "exit"], env=base_env,
                       capture_output=True, timeout=600, stdin=subprocess.DEVNULL)
        if not (compat / "pfx" / "system.reg").exists():
            raise RuntimeError("The game's Proton prefix could not be made")
    meta = _patch(root)
    feats = set(meta.get("features") or [])
    system32 = compat / "pfx" / "drive_c" / "windows" / "system32"
    for name, data in _components(root, meta):
        target = system32 / name
        if not target.is_file() or target.read_bytes() != data:
            tmp = target.with_name(target.name + f".cp-{os.getpid()}")
            tmp.write_bytes(data)
            tmp.replace(target)
    files = root / "files"
    libs = ":".join(str(files / "lib" / d) for d in ("x86_64-linux-gnu", "aarch64-linux-gnu", "i386-linux-gnu"))
    host = "wine-host-libraries-v1" in feats
    if host:
        libs = "/usr/lib:" + libs
    gst = "/usr/lib/gstreamer-1.0" if host else ":".join(
        str(files / "lib" / d / "gstreamer-1.0") for d in ("x86_64-linux-gnu", "aarch64-linux-gnu", "i386-linux-gnu"))
    overrides = ("dxgi=n;d3d11=n;d3d10core=n;d3d9=n;d3d12=n;d3d12core=n"
                 + (";winhttp=b;libnghttp2=n" if "wine-winhttp-http2-v1" in feats else "")
                 + (";d3d8=n" if "dxvk-constant-compare-v1" in feats else ""))
    wineserver = files / "bin" / "wineserver"
    caches = compat / "shadercache"
    for sub in ("vkd3d", "nvidia", "mesa", "steamapp"):
        (caches / sub).mkdir(parents=True, exist_ok=True)

    def default(name, value):
        return [f'if [ "${{{name}+x}}" != x ]; then', f"  export {name}={_q(value)}", "fi"]

    lines = ["#!/bin/sh",
             f"export WINEPREFIX={_q(compat / 'pfx')}", "export WINEARCH='win64'",
             f"export WINEDLLPATH={_q(str(files / 'lib' / 'vkd3d') + ':' + str(files / 'lib' / 'wine'))}",
             f"export LD_LIBRARY_PATH={_q(libs)}",
             f"export ESPEAK_DATA_PATH={_q(files / 'share')}",
             f"export GST_PLUGIN_SYSTEM_PATH_1_0={_q(gst)}", "export GST_PLUGIN_PATH_1_0=''",
             f"export WINE_GST_REGISTRY_DIR={_q(compat / 'gstreamer-1.0')}",
             f"export MEDIACONV_BLANK_VIDEO_FILE={_q(files / 'share' / 'media' / 'blank.mkv')}",
             f"export MEDIACONV_BLANK_AUDIO_FILE={_q(files / 'share' / 'media' / 'blank.ptna')}",
             f"export PATH={_q(str(files / 'bin') + ':' + os.environ.get('PATH', ''))}",
             *default("WINEDLLOVERRIDES", overrides),
             'if [ "${WINE_LARGE_ADDRESS_AWARE+x}" = x ] && [ "${PROTON_FORCE_LARGE_ADDRESS_AWARE+x}" != x ]; then',
             "  export PROTON_FORCE_LARGE_ADDRESS_AWARE='0'", "fi",
             *default("VKD3D_SHADER_CACHE_PATH", caches / "vkd3d"),
             'if [ "${__GL_SHADER_DISK_CACHE_PATH+x}" != x ]; then',
             f"  export __GL_SHADER_DISK_CACHE_PATH={_q(caches / 'nvidia')}", "  export __GL_SHADER_DISK_CACHE=1", "fi",
             'if [ "${MESA_SHADER_CACHE_DIR+x}" != x ]; then', f"  export MESA_SHADER_CACHE_DIR={_q(caches / 'mesa')}", "fi",
             'if [ "${1:-}" = "--nexus-stop-prefix" ]; then', f"  exec {_q(wineserver)} -k", "fi",
             "export PYTHONDONTWRITEBYTECODE='1'",
             f"export STEAM_COMPAT_DATA_PATH={_q(compat)}",
             f"export STEAM_COMPAT_CLIENT_INSTALL_PATH={_q(steam)}",
             f"export STEAM_COMPAT_SHADER_PATH={_q(caches / 'steamapp')}",
             "unset STEAM_COMPAT_INSTALL_PATH STEAM_COMPAT_LIBRARY_PATHS",
             f"export UMU_ID='{UMU_ID}'", "export UMU_USE_STEAM='0'",
             'case "${1:-}" in', '  /*) nexus_game_command="Z:$1"; shift; set -- "$nexus_game_command" "$@" ;;', "esac",
             # Launchers may finish before the game they started: wait until the prefix is empty.
             "launch_status=0", f'{_q(root / "proton")} run "$@" || launch_status=$?',
             "wait_status=0", f"{_q(wineserver)} -w || wait_status=$?",
             'if [ "$launch_status" -ne 0 ]; then exit "$launch_status"; fi', 'exit "$wait_status"', ""]
    script = compat / "xodus-proton-game"
    tmp = script.with_name(script.name + ".tmp")
    tmp.write_text("\n".join(lines))
    tmp.chmod(0o700)
    tmp.replace(script)
    return script


def play_argv(product_id: str) -> list:
    g = state().get(product_id) or {}
    folder = g.get("path") or ""
    exe = g.get("exe") or find_exe(folder)
    if not exe:
        raise RuntimeError("The game's package names no program to start")
    script = prepare(product_id)
    return [backend(), "run", folder, str(script), "--exe", exe, "--materialize-chain", "--market", _market(),
            "--license-cache", str(_prefix_dir(product_id) / "licenses")]


class Service:
    """xodus-service: the account service a game asks for its Xbox sign-in tickets (and cloud
    saves). It listens on a private socket; a loopback bridge guarded by a random key lets the
    game reach it from inside Wine (XODUS_BRIDGE_PORT/KEY), as Nexus Launcher does."""

    def __init__(self):
        import secrets
        import tempfile
        self.dir = tempfile.mkdtemp(prefix="cp-xodus-")
        self.socket = os.path.join(self.dir, "xodus.sock")
        self.key = secrets.token_hex(32)
        self.proc = None
        self.server = None
        self.port = 0

    def start(self, timeout=90):
        import socket
        import threading
        exe = os.path.join(os.path.dirname(backend()), "xodus-service")
        if not os.access(exe, os.X_OK):
            raise RuntimeError("This Xbox backend has no xodus-service")
        self.proc = subprocess.Popen([exe], env={**os.environ, "XDG_RUNTIME_DIR": self.dir, "XODUS_LOG": "error"},
                                     stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if self.proc.poll() is not None:
                err = (self.proc.stderr.read() or b"").decode("utf-8", "replace").strip().splitlines()
                raise RuntimeError("The Xbox account service stopped: " + (err[-1] if err else f"code {self.proc.returncode}")
                                   + ". Sign in to Xbox again.")
            try:
                with socket.socket(socket.AF_UNIX) as probe:
                    probe.connect(self.socket)
                break
            except OSError:
                time.sleep(0.25)
        else:
            raise RuntimeError("The Xbox account service did not start in time")
        self.server = socket.create_server(("127.0.0.1", 0))
        self.port = self.server.getsockname()[1]
        threading.Thread(target=self._serve, daemon=True).start()
        return self

    def _serve(self):
        import hmac
        import socket
        import threading
        while True:
            try:
                client, _ = self.server.accept()
            except OSError:
                return
            def handle(c=client):
                try:
                    c.settimeout(10)
                    got = b""
                    while len(got) < 64:
                        chunk = c.recv(64 - len(got))
                        if not chunk:
                            return c.close()
                        got += chunk
                    if not hmac.compare_digest(got, self.key.encode()):
                        return c.close()
                    c.settimeout(None)
                    up = socket.socket(socket.AF_UNIX)
                    up.connect(self.socket)
                    def pipe(a, b):
                        try:
                            while True:
                                data = a.recv(65536)
                                if not data:
                                    break
                                b.sendall(data)
                        except OSError:
                            pass
                        for x in (a, b):
                            try:
                                x.shutdown(socket.SHUT_RDWR)
                            except OSError:
                                pass
                    threading.Thread(target=pipe, args=(up, c), daemon=True).start()
                    pipe(c, up)
                except OSError:
                    c.close()
            threading.Thread(target=handle, daemon=True).start()

    def env(self) -> dict:
        return {"XODUS_SOCKET": self.socket, "XODUS_BRIDGE_PORT": str(self.port), "XODUS_BRIDGE_KEY": self.key}

    def stop(self):
        import signal
        if self.server:
            self.server.close()
        if self.proc and self.proc.poll() is None:
            self.proc.send_signal(signal.SIGINT)
            try:
                self.proc.wait(4)
            except subprocess.TimeoutExpired:
                self.proc.terminate()
        shutil.rmtree(self.dir, ignore_errors=True)


def play(product_id: str) -> int:
    """Start the game with its account service and wait until it (and anything it started) ends."""
    argv = play_argv(product_id)
    os.makedirs(_prefix_dir(product_id) / "licenses", exist_ok=True)
    service = Service().start()
    try:
        return subprocess.run(argv, env={**os.environ, **service.env()}).returncode
    finally:
        service.stop()


def stop(product_id: str) -> None:
    script = _prefix_dir(product_id) / "xodus-proton-game"
    if script.exists():
        subprocess.run([str(script), "--nexus-stop-prefix"], capture_output=True, timeout=30)


# --- the account ---------------------------------------------------------------------------------
PROFILE_TTL = 6 * 3600


def account_dir() -> Path:
    from .config import CACHE_DIR
    return CACHE_DIR / "xbox-account"


def read_profile(force: bool = False) -> dict:
    """The signed-in Xbox account as the backend reads it (gamertag, account, Game Pass membership),
    kept in account_dir() as xbox-profile.json / xbox-profile-license.json, shaped like Nexus
    Launcher's own files so nexus.gamertag() and nexus.gamepass_tier() read either. The picture
    goes to gamerpic.jpg. {} when there is no backend or no account."""
    import base64
    d = account_dir()
    path = d / "xbox-profile.json"
    try:
        if not force and time.time() - path.stat().st_mtime < PROFILE_TTL:
            return json.loads(path.read_text(encoding="utf-8")) or {}
    except (OSError, ValueError):
        pass
    exe = backend()
    if not exe:
        return {}
    out = {}
    for name, extra in (("xbox-profile.json", []), ("xbox-profile-license.json", ["--license"])):
        try:
            r = subprocess.run([exe, "profile", "--json", *extra], capture_output=True, text=True, timeout=60,
                               stdin=subprocess.DEVNULL)
            data = json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else None
        except (OSError, subprocess.SubprocessError, ValueError):
            data = None
        if not isinstance(data, dict):
            continue
        pic = str(data.pop("gamerpicDataUrl", "") or "")
        d.mkdir(parents=True, exist_ok=True)
        if pic.startswith("data:image/") and "," in pic and not extra:
            try:
                (d / "gamerpic.jpg").write_bytes(base64.b64decode(pic.split(",", 1)[1]))
            except (ValueError, OSError):
                pass
        (d / name).write_text(json.dumps(data), encoding="utf-8")
        if not extra:
            out = data
    if not out:  # not signed in: remembered too, so the backend is not asked again at once
        d.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")
    return out


ACTIVITY_TTL = 6 * 3600


def activity(title_ids, force: bool = False) -> dict:
    """{title id: (seconds played, last played as a Unix time)} from Xbox's own records (what the
    account played anywhere, the Xbox app and consoles included), for games played at all.
    Cached for a few hours; asked one game at a time, only for the ones not known yet."""
    from datetime import datetime
    from .config import CACHE_DIR, read_json, write_json
    cache = CACHE_DIR / "xbox-activity.json"
    data = read_json(cache) or {}
    now = time.time()
    exe = backend()
    changed = False
    for tid in {str(t) for t in title_ids if t}:
        hit = data.get(tid)
        if exe and (force or not hit or now - hit.get("t", 0) > ACTIVITY_TTL):
            try:
                r = subprocess.run([exe, "game-activity", tid, "--json"], capture_output=True, text=True,
                                   timeout=60, stdin=subprocess.DEVNULL)
                d = json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else None
            except (OSError, subprocess.SubprocessError, ValueError):
                d = None
            if isinstance(d, dict):
                last = 0
                try:
                    if d.get("lastPlayed"):
                        last = int(datetime.fromisoformat(str(d["lastPlayed"]).replace("Z", "+00:00")).timestamp())
                except ValueError:
                    pass
                data[tid] = {"t": now, "seconds": int(d.get("minutesPlayed") or 0) * 60, "last": last}
                changed = True
    if changed:
        write_json(cache, data)
    return {t: (v.get("seconds", 0), v.get("last", 0)) for t, v in data.items()
            if t in {str(x) for x in title_ids} and (v.get("seconds") or v.get("last"))}


def gamerpic() -> str:
    p = account_dir() / "gamerpic.jpg"
    return str(p) if p.exists() else ""


def logout() -> None:
    """Sign the Microsoft account out of the backend (and so out of Nexus Launcher too: they share
    the keyring entry) and forget Cornerplay's copy of the profile."""
    exe = backend()
    if exe:
        try:
            subprocess.run([exe, "logout"], capture_output=True, timeout=60, stdin=subprocess.DEVNULL)
        except (OSError, subprocess.SubprocessError):
            pass
    shutil.rmtree(account_dir(), ignore_errors=True)
    from .config import CACHE_DIR
    (CACHE_DIR / "xbox-owned.json").unlink(missing_ok=True)


def signed_in() -> bool:
    exe = backend()
    if not exe:
        return False
    try:
        r = subprocess.run([exe, "account", "--json"], capture_output=True, text=True, timeout=30,
                           stdin=subprocess.DEVNULL)
        data = json.loads(r.stdout or "{}")
    except (OSError, subprocess.SubprocessError, ValueError):
        return False
    return bool(data.get("account") or data.get("signedIn") or data.get("stored"))


def main(args=None):
    args = list(sys.argv[1:] if args is None else args)
    what = args[0] if args else ""
    try:
        if what == "install" and len(args) >= 3:
            return install(args[1], args[2], args[3] if len(args) > 3 else "")
        if what == "play" and len(args) >= 2:
            return play(args[1])
        if what == "uninstall" and len(args) >= 2:
            uninstall(args[1])
            return 0
        if what == "setup":
            install_backend()
            install_runtime(lambda d, t: print(f"Progress: {d * 100 / t:.1f}%", flush=True))
            return 0
    except Exception as e:  # noqa: BLE001 (shown to the user in the job's log)
        print(f"Xbox: {e}", file=sys.stderr)
        return 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
