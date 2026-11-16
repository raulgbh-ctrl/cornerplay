"""Play on another screen: Sunshine on the gaming PC, Moonlight on the TV, laptop or Deck.

- This PC hosts (Sunshine): add_to_sunshine() puts "Cornerplay (TV mode)" and your favourite
  games into Sunshine's app list (~/.config/sunshine/apps.json), so Moonlight anywhere in the
  house can start them, and nothing else: Sunshine's Desktop and Big Picture entries go (the
  old list is kept as apps.json.before-cornerplay), and a game's stream ends when it closes.
- This PC plays (Moonlight): play_on_host() wakes the gaming PC (Wake-on-LAN, when its network
  card's MAC address is set) and starts Moonlight streaming that PC's Cornerplay TV mode.
- Setting Sunshine up (status, start, pairing a device with its PIN, paired devices) goes
  through Sunshine's own web API on https://localhost:47990, with a login Cornerplay creates
  when Sunshine has none yet (or the one the user types).
- The stream fits the screen: Moonlight asks for this screen's resolution and refresh rate, and
  on the gaming PC each entry's prep-cmd switches the display to the closest mode while the
  stream runs (Hyprland, Sway, KDE), then back.
In the Flatpak, Sunshine's file and Moonlight are on the host: reached through flatpak-spawn.
"""
import json
import os
import re
import shlex
import socket
import subprocess
import time
from pathlib import Path

from . import host

TV_APP = "Cornerplay (TV mode)"
MARK = "cornerplay"   # entries whose command runs Cornerplay are Cornerplay's own
MOONLIGHT_FLATPAK = "com.moonlight_stream.Moonlight"
SUNSHINE_FLATPAK = "dev.lizardbyte.app.Sunshine"
API_PORT = 47990


# --- Wake-on-LAN -------------------------------------------------------------------------
def mac_bytes(mac: str) -> bytes:
    digits = re.sub(r"[^0-9a-fA-F]", "", mac or "")
    if len(digits) != 12:
        raise ValueError("a MAC address has 12 hex digits, like 3c:7c:3f:12:34:56")
    return bytes.fromhex(digits)


def magic_packet(mac: str) -> bytes:
    return b"\xff" * 6 + mac_bytes(mac) * 16


def wake(mac: str, broadcast: str = "255.255.255.255"):
    """Send the Wake-on-LAN magic packet (UDP 9, and 7 for older cards)."""
    packet = magic_packet(mac)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        for port in (9, 7):
            s.sendto(packet, (broadcast, port))


# --- Moonlight (this PC plays) -----------------------------------------------------------------
def moonlight() -> list:
    """The command that runs Moonlight, or [] when it is not installed."""
    for name in ("moonlight", "moonlight-qt"):
        exe = host.which(name)
        if exe:
            return [exe]
    try:
        r = subprocess.run(host.argv(["flatpak", "info", MOONLIGHT_FLATPAK]), capture_output=True, timeout=10)
        if r.returncode == 0:
            return ["flatpak", "run", MOONLIGHT_FLATPAK]
    except (OSError, subprocess.TimeoutExpired):
        pass
    return []


def _check_pc(pc: str):
    if not pc or not re.fullmatch(r"[A-Za-z0-9.:\-\[\]_]+", pc):
        raise RuntimeError("the gaming PC's name or address looks wrong")


def _moonlight_or_raise() -> list:
    exe = moonlight()
    if not exe:
        raise RuntimeError("Moonlight is not installed (" + _moonlight_hint() + ")")
    return exe


def _moonlight_hint() -> str:
    from . import pkgs
    return pkgs.hint("moonlight")


def stream_size(width: int, height: int, fps: float, cap: int = 3840) -> tuple:
    """What to ask the gaming PC for: this screen's size (even numbers, at most `cap` wide, the
    aspect kept) and refresh rate (30 to 240)."""
    w, h = max(640, int(width)), max(360, int(height))
    if w > cap:
        h, w = round(h * cap / w), cap
    fps = int(round(fps or 60))
    return w - w % 2, h - h % 2, max(30, min(240, fps))


def stream_argv(pc: str, app: str = TV_APP, size: tuple = ()) -> list:
    """Moonlight streaming `app` from `pc`; size = (width, height, fps) makes the stream fit
    this screen (Moonlight's own setting is used otherwise)."""
    exe = _moonlight_or_raise()
    _check_pc(pc)
    extra = []
    if size:
        w, h, fps = size
        extra = ["--resolution", f"{w}x{h}", "--fps", str(fps)]
    return host.argv(exe + ["stream", pc, app] + extra)


def pair_argv(pc: str, pin: str) -> list:
    """Moonlight pairing with `pc` using a PIN chosen here (typed on the gaming PC)."""
    exe = _moonlight_or_raise()
    _check_pc(pc)
    if not re.fullmatch(r"\d{4}", pin or ""):
        raise RuntimeError("the PIN has 4 digits")
    return host.argv(exe + ["pair", pc, "--pin", pin])


def new_pin() -> str:
    import secrets
    return f"{secrets.randbelow(10000):04d}"


def parse_app_list(text: str) -> list:
    """The apps `moonlight list PC [--csv]` printed: [{"name", "hidden"}]. The CSV has a header
    (Name, ID, HDR Supported, App Collection Game, Hidden, Direct Launch, Boxart URL); older
    Moonlights print one name per line."""
    import csv
    import io
    lines = [l for l in (text or "").splitlines() if l.strip()]
    if not lines:
        return []
    if lines[0].lower().startswith("name,"):
        rows = list(csv.reader(io.StringIO("\n".join(lines)), skipinitialspace=True))
        head = [h.strip().lower() for h in rows[0]]
        out = []
        for r in rows[1:]:
            row = dict(zip(head, (c.strip() for c in r)))
            if row.get("name"):
                out.append({"name": row["name"], "hidden": row.get("hidden", "").lower() == "true"})
        return out
    return [{"name": l.strip(), "hidden": False} for l in lines]


def list_apps(pc: str, timeout: float = 25) -> list:
    """What the gaming PC offers (Sunshine's app list), through Moonlight; this PC must be paired."""
    exe = _moonlight_or_raise()
    _check_pc(pc)
    r = subprocess.run(host.argv(exe + ["list", pc, "--csv"]), capture_output=True, text=True, timeout=timeout)
    apps = parse_app_list(r.stdout)
    if r.returncode != 0 and not apps:
        err = (r.stderr or r.stdout).strip().splitlines()
        msg = err[-1] if err else "Moonlight could not reach it"
        if "pair" in msg.lower():
            raise RuntimeError("not paired with it yet: use Pair with it first")
        raise RuntimeError(msg)
    return [a for a in apps if not a["hidden"]]


# --- Sunshine (this PC hosts) --------------------------------------------------------------------
HOST_FILE = "${XDG_CONFIG_HOME:-$HOME/.config}/sunshine/apps.json"   # as the host's shell spells it


def sunshine_dir() -> Path:
    """Sunshine's config folder: its Flatpak's when only the Flatpak is installed."""
    native = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "sunshine"
    flat = Path.home() / ".var/app" / SUNSHINE_FLATPAK / "config/sunshine"
    if sunshine_kind() == "flatpak" or (flat.is_dir() and not native.is_dir()):
        return flat
    return native


def sunshine_file() -> Path:
    return sunshine_dir() / "apps.json"


_kind_cache = []


def sunshine_kind() -> str:
    """"native", "flatpak" or "" (not installed). Remembered for the session once found."""
    if _kind_cache and _kind_cache[0]:
        return _kind_cache[0]
    kind = ""
    if host.which("sunshine"):
        kind = "native"
    else:
        try:
            r = subprocess.run(host.argv(["flatpak", "info", SUNSHINE_FLATPAK]), capture_output=True, timeout=10)
            kind = "flatpak" if r.returncode == 0 else ""
        except (OSError, subprocess.TimeoutExpired):
            pass
    _kind_cache[:] = [kind]
    return kind


def _read() -> str | None:
    if not host.IN_FLATPAK:
        try:
            return sunshine_file().read_text()
        except OSError:
            return None
    r = subprocess.run(host.argv(["sh", "-c", f'cat "{HOST_FILE}" 2>/dev/null']), capture_output=True, text=True, timeout=15)
    return r.stdout if r.returncode == 0 else None


def _write(text: str):
    if not host.IN_FLATPAK:
        f = sunshine_file()
        f.parent.mkdir(parents=True, exist_ok=True)
        tmp = f.with_suffix(".json.tmp")
        tmp.write_text(text)
        tmp.replace(f)
        return
    script = f'f="{HOST_FILE}"; mkdir -p "$(dirname "$f")" && printf "%s" "$1" > "$f.tmp" && mv "$f.tmp" "$f"'
    subprocess.run(host.argv(["sh", "-c", script, "sh", text]), check=True, timeout=15)


def _launcher(kind: str = "") -> list:
    """How Sunshine starts Cornerplay. Sunshine's Flatpak runs its apps on the host through
    flatpak-spawn."""
    if host.IN_FLATPAK:
        cmd = ["flatpak", "run", host.APP_ID]
    else:
        import shutil
        cmd = [shutil.which("cornerplay") or str(Path.home() / ".local/bin/cornerplay")]
    return (["flatpak-spawn", "--host"] if kind == "flatpak" else []) + cmd


def _ours(app: dict) -> bool:
    cmds = " ".join([str(app.get("cmd") or "")] + [str(c) for c in app.get("detached") or []])
    return MARK in cmds.lower() and (app.get("name") == TV_APP or "--play" in cmds or "--tv" in cmds)


MAX_GAMES = 60


def sunshine_apps(existing: dict, games: list, icon: str = "", fit: bool = True, kind: str = "",
                  only_ours: bool = True) -> dict:
    """Sunshine's apps.json with Cornerplay's entries replaced: TV mode, then games
    [{"key", "title", "image"?}]. Detached: Cornerplay hands over to a copy already running.
    fit: each entry switches this PC's display to the stream's size while it runs (prep-cmd).
    only_ours: Sunshine's own entries (Desktop, Steam Big Picture) go, so Moonlight offers
    games and never the whole desktop. A game's stream lasts as long as `--play` waits for it:
    the game closes, the stream ends (no auto-detach, so a game that fails at once ends it too)."""
    data = dict(existing) if isinstance(existing, dict) else {}
    apps = [] if only_ours else [a for a in (data.get("apps") or []) if isinstance(a, dict) and not _ours(a)]
    run = " ".join(shlex.quote(a) for a in _launcher(kind))
    # Sunshine's Flatpak cannot hand its environment over to the host: the size goes as arguments
    # (Sunshine fills in $(NAME) itself).
    size = " $(SUNSHINE_CLIENT_WIDTH) $(SUNSHINE_CLIENT_HEIGHT) $(SUNSHINE_CLIENT_FPS)" if kind == "flatpak" else ""
    prep = [{"do": f"{run} --stream-display start{size}", "undo": f"{run} --stream-display stop", "elevated": "false"}]
    tv = {"name": TV_APP, "detached": [f"setsid {run} --tv"], "auto-detach": "true"}
    if icon:
        tv["image-path"] = icon
    ours = [tv]
    for g in games[:MAX_GAMES]:
        app = {"name": g["title"][:60], "cmd": f"{run} --play {shlex.quote(g['key'])}", "auto-detach": "false"}
        if g.get("image"):
            app["image-path"] = g["image"]
        ours.append(app)
    if fit:
        for a in ours:
            a["prep-cmd"] = prep
    data.setdefault("env", {"PATH": "$(PATH):$(HOME)/.local/bin"})
    data["apps"] = apps + ours
    return data


def add_to_sunshine(games: list, icon: str = "", fit: bool = True) -> int:
    """Write Cornerplay's entries into Sunshine's app list; returns how many. Sunshine reads the
    file when it starts: restart_sunshine() afterwards when it is running."""
    text = _read()
    try:
        existing = json.loads(text) if text and text.strip() else {}
    except ValueError:
        raise RuntimeError("Sunshine's apps.json is not valid JSON; left as it is")
    others = [a for a in (existing.get("apps") or []) if isinstance(a, dict) and not _ours(a)] \
        if isinstance(existing, dict) else []
    if others and not host.IN_FLATPAK:  # Desktop & co. are dropped: keep the list as it was, once
        backup = sunshine_file().with_name("apps.json.before-cornerplay")
        if not backup.exists():
            backup.write_text(text)
    data = sunshine_apps(existing, games, icon, fit, sunshine_kind())
    _write(json.dumps(data, indent=2))
    return 1 + min(len(games), MAX_GAMES)


# --- Sunshine: installed, running, its login, pairing ------------------------------------------
def sunshine_running(port: int = API_PORT) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.6):
            return True
    except OSError:
        return False


SERVICES = ("sunshine.service", "app-dev.lizardbyte.app.Sunshine.service")


def _service() -> str:
    """Sunshine's systemd user unit, when its package has one."""
    for unit in SERVICES:
        try:
            r = subprocess.run(host.argv(["systemctl", "--user", "cat", unit]), capture_output=True, timeout=10)
            if r.returncode == 0:
                return unit
        except (OSError, subprocess.TimeoutExpired):
            return ""
    return ""


def start_sunshine() -> str:
    """Start Sunshine (and have it start with the desktop, when it has a user service)."""
    kind = sunshine_kind()
    if not kind:
        raise RuntimeError("Sunshine is not installed")
    unit = _service()
    if unit:
        r = subprocess.run(host.argv(["systemctl", "--user", "enable", "--now", unit]), capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            raise RuntimeError((r.stderr or "systemctl failed").strip().splitlines()[-1])
    else:
        cmd = ["sunshine"] if kind == "native" else ["flatpak", "run", SUNSHINE_FLATPAK]
        subprocess.Popen(host.argv(["setsid"] + cmd), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
    for _ in range(40):
        if sunshine_running():
            return unit
        time.sleep(0.25)
    raise RuntimeError("Sunshine did not start (its log: journalctl --user -u sunshine)")


def restart_sunshine(login: dict = None):
    """Have Sunshine read its app list again: its API's restart, else the user service's."""
    if login:
        try:
            api("POST", "/api/restart", {}, login)
            return
        except RuntimeError:
            pass
    unit = _service()
    if unit:
        subprocess.run(host.argv(["systemctl", "--user", "restart", unit]), capture_output=True, timeout=30)


def has_login(state_dir: Path = None) -> bool:
    """Has Sunshine's web page a username and password yet (sunshine_state.json)?"""
    try:
        state = json.loads(((state_dir or sunshine_dir()) / "sunshine_state.json").read_text())
    except (OSError, ValueError):
        return False
    return bool(state.get("username"))


def api(method: str, path: str, body=None, login: dict = None, port: int = API_PORT, timeout: float = 10):
    """Call Sunshine's web API on this PC. Its certificate is its own (self-signed), so it is
    not checked, which is why this only ever talks to 127.0.0.1."""
    import base64
    import ssl
    import urllib.error
    import urllib.request
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"https://127.0.0.1:{port}{path}", data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if login:
        token = base64.b64encode(f"{login.get('username', '')}:{login.get('password', '')}".encode()).decode()
        req.add_header("Authorization", "Basic " + token)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=timeout) as r:
            text = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise RuntimeError("Sunshine did not accept the username and password")
        try:  # Sunshine explains a 400 in its body: {"status": false, "error": "..."}
            why = str(json.loads(e.read().decode("utf-8", "replace")).get("error") or "")
        except Exception:
            why = ""
        raise RuntimeError(f"Sunshine answered {e.code}" + (f": {why}" if why else ""))
    except (urllib.error.URLError, OSError) as e:
        raise RuntimeError("Sunshine is not running" if "refused" in str(e).lower() else f"Sunshine: {e}")
    try:
        out = json.loads(text) if text.strip() else {}
    except ValueError:
        out = {}
    if isinstance(out, dict) and str(out.get("status", "true")).lower() == "false":
        raise RuntimeError(out.get("error") or "Sunshine said no")
    return out


def create_login(username: str, password: str, port: int = API_PORT):
    """Sunshine's first-run step: set the web login (allowed without one while none exists)."""
    api("POST", "/api/password", {"currentUsername": "", "currentPassword": "", "newUsername": username,
                                  "newPassword": password, "confirmNewPassword": password}, None, port)


def pair_device(pin: str, name: str, login: dict, port: int = API_PORT):
    """Accept a Moonlight that shows `pin` (Moonlight > add PC > it shows a 4-digit PIN)."""
    if not re.fullmatch(r"\d{4}", (pin or "").strip()):
        raise RuntimeError("the PIN Moonlight shows has 4 digits")
    body = {"pin": pin.strip(), "name": (name or "Moonlight").strip()[:40]}
    # Sunshine from 2026 on keeps each waiting Moonlight apart and wants its pairing_id with the
    # PIN (GET /api/pin lists them); older Sunshine has no such list and takes the PIN alone.
    try:
        waiting = api("GET", "/api/pin", None, login, port).get("pairings")
    except (RuntimeError, AttributeError):
        waiting = None
    if isinstance(waiting, list):
        waiting = [w for w in waiting if isinstance(w, dict) and w.get("id")]
        if not waiting:
            raise RuntimeError("no Moonlight is waiting: add this PC in Moonlight first, then type the PIN it shows")
        body["pairing_id"] = waiting[-1]["id"]
    try:
        api("POST", "/api/pin", body, login, port, timeout=40)
    except RuntimeError as e:
        if str(e) == "Sunshine said no":
            raise RuntimeError("wrong PIN, or Moonlight stopped waiting") from None
        raise


def paired_devices(login: dict, port: int = API_PORT) -> list:
    out = api("GET", "/api/clients/list", None, login, port)
    rows = (out.get("named_certs") or []) if isinstance(out, dict) else []
    return [{"name": r.get("name") or "Moonlight", "uuid": r.get("uuid", "")} for r in rows if isinstance(r, dict)]


def unpair_device(uuid: str, login: dict, port: int = API_PORT):
    api("POST", "/api/clients/unpair", {"uuid": uuid}, login, port)


# --- The display follows the stream (prep-cmd on the gaming PC) ---------------------------------
def pick_mode(modes: list, width: int, height: int, fps: float):
    """The display mode closest to the stream: modes [(w, h, hz)]. Exactly its size if there is
    one; else the biggest one with its aspect that fits; else the biggest that fits; never a
    mode bigger than the stream unless nothing fits. The refresh rate closest to fps, not above."""
    if not modes or width <= 0 or height <= 0:
        return None
    sizes = {(w, h) for w, h, _ in modes}
    aspect = width / height
    fits = [s for s in sizes if s[0] <= width and s[1] <= height]
    same = [s for s in fits if abs(s[0] / s[1] - aspect) < 0.01]
    if (width, height) in sizes:
        size = (width, height)
    elif same:
        size = max(same, key=lambda s: s[0] * s[1])
    elif fits:
        size = max(fits, key=lambda s: s[0] * s[1])
    else:
        size = min(sizes, key=lambda s: s[0] * s[1])
    rates = sorted(hz for w, h, hz in modes if (w, h) == size)
    under = [r for r in rates if r <= fps + 0.5]
    hz = max(under) if under else min(rates)
    return size[0], size[1], hz


DISPLAY_STATE = "stream-display.json"


def _hypr_env() -> dict:
    """hyprctl needs to know which Hyprland: Sunshine's service may not have been given it."""
    env = dict(os.environ)
    if env.get("HYPRLAND_INSTANCE_SIGNATURE"):
        return env
    run = Path(env.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}") / "hypr"
    try:
        found = sorted((d for d in run.iterdir() if (d / ".socket.sock").exists()), key=lambda d: d.stat().st_mtime)
    except OSError:
        found = []
    if found:
        env["HYPRLAND_INSTANCE_SIGNATURE"] = found[-1].name
    return env


def _run(argv, env=None, timeout=15) -> str:
    r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, env=env)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout or "failed").strip()[:200])
    return r.stdout


def display_backend() -> str:
    import shutil
    if shutil.which("hyprctl") and _hypr_env().get("HYPRLAND_INSTANCE_SIGNATURE"):
        return "hyprland"
    if shutil.which("swaymsg") and os.environ.get("SWAYSOCK"):
        return "sway"
    if shutil.which("kscreen-doctor"):
        return "kde"
    return ""


def _hypr_mode_list(mon: dict) -> list:
    out = []
    for m in mon.get("availableModes") or []:
        hit = re.fullmatch(r"(\d+)x(\d+)@([\d.]+)Hz", m.strip())
        if hit:
            out.append((int(hit[1]), int(hit[2]), float(hit[3])))
    return out


def _hypr_apply(name, w, h, hz, x, y, scale, env):
    mode = f"{w}x{h}@{hz:.2f}"
    lua = f'hl.monitor({{ output = {json.dumps(name)}, mode = "{mode}", position = "{x}x{y}", scale = {scale:g} }})'
    try:
        out = _run(["hyprctl", "eval", lua], env)
        if "error" not in out.lower() and "unknown" not in out.lower():
            return
    except RuntimeError:
        pass
    _run(["hyprctl", "keyword", "monitor", f"{name},{mode},{x}x{y},{scale:g}"], env)


def fit_display(width: int, height: int, fps: float, state_dir: Path = None) -> str:
    """Switch the main display to the mode closest to the stream, remembering how it was.
    Returns what was done, in a few words ("" when nothing needed changing)."""
    from .config import CACHE_DIR
    state = (state_dir or CACHE_DIR) / DISPLAY_STATE
    backend = display_backend()
    if backend == "hyprland":
        env = _hypr_env()
        mons = [m for m in json.loads(_run(["hyprctl", "monitors", "-j"], env)) if not m.get("disabled")]
        if not mons:
            return ""
        mon = next((m for m in mons if m.get("focused")), mons[0])
        pick = pick_mode(_hypr_mode_list(mon), width, height, fps)
        if not pick or (pick[0], pick[1]) == (mon["width"], mon["height"]) and abs(pick[2] - mon["refreshRate"]) < 0.5:
            return ""
        before = {"backend": backend, "output": mon["name"], "w": mon["width"], "h": mon["height"],
                  "hz": mon["refreshRate"], "x": mon["x"], "y": mon["y"], "scale": mon["scale"]}
        if not state.exists():   # a second start (another app) keeps the first "before"
            state.write_text(json.dumps(before))
        scale = 1 if pick[0] <= 1920 else mon["scale"]
        _hypr_apply(mon["name"], pick[0], pick[1], pick[2], mon["x"], mon["y"], scale, env)
        return f"{mon['name']} at {pick[0]}x{pick[1]}@{round(pick[2])}"
    if backend == "sway":
        outs = [o for o in json.loads(_run(["swaymsg", "-t", "get_outputs", "-r"])) if o.get("active")]
        if not outs:
            return ""
        o = next((o for o in outs if o.get("focused")), outs[0])
        modes = [(m["width"], m["height"], m["refresh"] / 1000) for m in o.get("modes") or []]
        cur = o.get("current_mode") or {}
        pick = pick_mode(modes, width, height, fps)
        if not pick or (pick[0], pick[1]) == (cur.get("width"), cur.get("height")):
            return ""
        if not state.exists():
            state.write_text(json.dumps({"backend": backend, "output": o["name"], "w": cur.get("width"), "h": cur.get("height"),
                                         "hz": (cur.get("refresh") or 60000) / 1000, "scale": o.get("scale", 1)}))
        _run(["swaymsg", "output", o["name"], "mode", f"{pick[0]}x{pick[1]}@{pick[2]:.3f}Hz"])
        return f"{o['name']} at {pick[0]}x{pick[1]}"
    if backend == "kde":
        info = json.loads(_run(["kscreen-doctor", "-j"]))
        outs = [o for o in info.get("outputs") or [] if o.get("enabled")]
        if not outs:
            return ""
        o = next((o for o in outs if o.get("priority") == 1), outs[0])
        modes = {m["id"]: (m["size"]["width"], m["size"]["height"], m["refreshRate"]) for m in o.get("modes") or []}
        pick = pick_mode(list(modes.values()), width, height, fps)
        if not pick:
            return ""
        mid = next(i for i, m in modes.items() if m == pick)
        if str(mid) == str(o.get("currentModeId")):
            return ""
        if not state.exists():
            state.write_text(json.dumps({"backend": backend, "output": o["name"], "mode": o.get("currentModeId")}))
        _run(["kscreen-doctor", f"output.{o['name']}.mode.{mid}"])
        return f"{o['name']} at {pick[0]}x{pick[1]}"
    return ""


def restore_display(state_dir: Path = None) -> bool:
    """Put the display back the way fit_display found it."""
    from .config import CACHE_DIR
    state = (state_dir or CACHE_DIR) / DISPLAY_STATE
    try:
        before = json.loads(state.read_text())
    except (OSError, ValueError):
        return False
    try:
        if before["backend"] == "hyprland":
            _hypr_apply(before["output"], before["w"], before["h"], before["hz"], before["x"], before["y"],
                        before["scale"], _hypr_env())
        elif before["backend"] == "sway":
            _run(["swaymsg", "output", before["output"], "mode", f"{before['w']}x{before['h']}@{before['hz']:.3f}Hz"])
        elif before["backend"] == "kde":
            _run(["kscreen-doctor", f"output.{before['output']}.mode.{before['mode']}"])
    finally:
        state.unlink(missing_ok=True)
    return True


def display_command(action: str, size: list = ()) -> int:
    """cornerplay --stream-display start|stop [W H FPS], run by Sunshine (prep-cmd) with the
    stream's size in SUNSHINE_CLIENT_WIDTH / _HEIGHT / _FPS (or as arguments)."""
    try:
        if action == "start":
            env = os.environ
            vals = list(size) + [""] * 3
            w = int(vals[0] or env.get("SUNSHINE_CLIENT_WIDTH") or 0)
            h = int(vals[1] or env.get("SUNSHINE_CLIENT_HEIGHT") or 0)
            fps = float(vals[2] or env.get("SUNSHINE_CLIENT_FPS") or 60)
            done = fit_display(w, h, fps) if w and h else ""
            print(f"stream display: {done or 'left as it is'}")
        else:
            print("stream display: " + ("put back" if restore_display() else "nothing to put back"))
    except Exception as e:   # never stop the stream over the display
        print(f"stream display: not changed ({e})")
    return 0
