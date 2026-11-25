"""Battle.net: runs Blizzard's own launcher (under Proton on Linux, as it is on Windows) and
lists what it installed.

Blizzard has no public library API, so games are installed inside the
Battle.net app. Cornerplay installs/starts that app and reads its product database
to show each installed game as its own tile.
"""
import os
from pathlib import Path

from ..config import CACHE_DIR, CONFIG_DIR, game_options, read_json, write_json
from ..osinfo import WINDOWS, process_programs, reg_subkeys, reg_value, terminate
from ..runner import StoreError, compat, prefix_path, wine_env, wrapper_argv
from .base import Command, Game, Store

SETUP_URL = "https://downloader.battle.net/download/getInstaller?os=win&installer=Battle.net-Setup.exe"
LAUNCHER_ID = "battlenet-app"
# The Battle.net app's own tile: a cover drawn for Cornerplay (art/battlenet-cover.png).
LAUNCHER_COVER = (Path(__file__).resolve().parent.parent / "art" / "battlenet-cover.png").as_uri()
UMU_ID = "umu-battlenet"

# product code (as in product.db) -> (title, code for `Battle.net.exe --exec="launch CODE"`)
PRODUCTS = {
    "wow": ("World of Warcraft", "WoW"),
    "wow_classic": ("World of Warcraft Classic", "WoWC"),
    "wow_classic_era": ("WoW Classic Era", "WoWC"),
    "d3": ("Diablo III", "D3"),
    "fenris": ("Diablo IV", "Fen"),
    "osi": ("Diablo II: Resurrected", "OSI"),
    "anbs": ("Diablo Immortal", "ANBS"),
    "pro": ("Overwatch 2", "Pro"),
    "hs_beta": ("Hearthstone", "WTCG"),
    "s1": ("StarCraft: Remastered", "S1"),
    "s2": ("StarCraft II", "S2"),
    "heroes": ("Heroes of the Storm", "Hero"),
    "w3": ("Warcraft III: Reforged", "W3"),
    "gryphon": ("Warcraft Rumble", "GRY"),
    "rtro": ("Blizzard Arcade Collection", "RTRO"),
    "wlby": ("Crash Bandicoot 4", "WLBY"),
    "viper": ("Call of Duty: Black Ops 4", "VIPR"),
    "odin": ("Call of Duty: Modern Warfare", "ODIN"),
    "lazarus": ("Call of Duty: MW2 Campaign Remastered", "LAZR"),
    "zeus": ("Call of Duty: Black Ops Cold War", "ZEUS"),
    "fore": ("Call of Duty: Vanguard", "FORE"),
    "auks": ("Call of Duty", "AUKS"),
}
# Launch code -> the product's uid (what `--game=` and the uninstaller take): "Fen" -> "fenris".
UID_BY_LAUNCH = {}
for _uid, (_t, _code) in PRODUCTS.items():
    UID_BY_LAUNCH.setdefault(_code.lower(), _uid)
# Games the Blizzard account still lists that are no longer sold or played through Battle.net.
MOVED = {1146311730}  # Destiny 2: on Steam since 2019
# Games that also start without Battle.net (their own sign-in screen), by uid: the program,
# relative to the game's folder. A game's Options > "Start without Battle.net".
DIRECT = {"wow": "_retail_/Wow.exe", "wow_classic": "_classic_/WowClassic.exe",
          "wow_classic_era": "_classic_era_/WowClassic.exe"}
# Blizzard titles that are also sold on Steam, so their box art can come from there.
STEAM_APPIDS = {"pro": 2357570, "fenris": 2344520, "osi": 2536520, "auks": 1938090,
                "odin": 2000950, "zeus": 1985810, "wlby": 1378990}
NOT_GAMES = {"agent", "bna", "battle.net", "battlenet"}

# Owned games, read from the Blizzard account site by a hidden page in the app (qml/BlizzardSync.qml)
# while the user is signed in there. Blizzard's titleId -> (title, launch code); from Playnite's table.
OWNED_FILE = CONFIG_DIR / "blizzard_owned.json"
TITLE_IDS = {
    5730135: ("World of Warcraft", "WoW"), 17459: ("Diablo III", "D3"), 21298: ("StarCraft II", "S2"),
    21297: ("StarCraft: Remastered", "S1"), 1465140039: ("Hearthstone", "WTCG"),
    1214607983: ("Heroes of the Storm", "Hero"), 5272175: ("Overwatch 2", "Pro"),
    1447645266: ("Call of Duty: Black Ops 4", "VIPR"), 1329875278: ("Call of Duty: Modern Warfare", "ODIN"),
    22323: ("Warcraft III: Reforged", "W3"), 1279351378: ("Call of Duty: MW2 Campaign Remastered", "LAZR"),
    1514493267: ("Call of Duty: Black Ops Cold War", "ZEUS"), 1464615513: ("Crash Bandicoot 4", "WLBY"),
    5198665: ("Diablo II: Resurrected", "OSI"), 1381257807: ("Blizzard Arcade Collection", "RTRO"),
    1179603525: ("Call of Duty: Vanguard", "FORE"), 1095647827: ("Diablo Immortal", "ANBS"),
    1096108883: ("Call of Duty", "AUKS"), 4613486: ("Diablo IV", "Fen"), 1146246220: ("Diablo", "D1"),
    5714258: ("Warcraft: Remastered", "W1R"), 5714514: ("Warcraft II: Remastered", "W2R"),
    1463898673: ("Warcraft: Orcs & Humans", "W1"), 1462911566: ("Warcraft II: Battle.net Edition", "W2"),
    4674137: ("Warcraft Rumble", "GRY"), 1095911763: ("Doom: The Dark Ages", "ARIS"),
    1396920146: ("Sea of Thieves", "SCOR"), 4280907: ("The Outer Worlds 2", "ARK"),
    1279414849: ("Tony Hawk's Pro Skater 3 + 4", "LBRA"), 1095849281: ("Avowed", "AQUA"),
}
# Launch code -> Steam app, for box art (same games as STEAM_APPIDS, keyed by launch code).
STEAM_BY_LAUNCH = {"Pro": 2357570, "Fen": 2344520, "OSI": 2536520, "AUKS": 1938090,
                   "ODIN": 2000950, "ZEUS": 1985810, "WLBY": 1378990}


def owned():
    """The owned-games list the account site last gave, or None when no Blizzard account is linked."""
    data = read_json(OWNED_FILE)
    return data if isinstance(data, dict) else None


def save_owned(raw):
    """Keep what the account site returned: {"games": [gameAccounts…], "classic": [classicGames…]}."""
    import time
    games = []
    for a in raw.get("games") or []:
        try:
            tid = int(a.get("titleId") or 0)
        except (TypeError, ValueError):
            tid = 0
        if tid in MOVED:
            continue
        known = TITLE_IDS.get(tid)
        name = (known[0] if known else "") or (a.get("localizedGameName") or "").strip()
        if name:
            games.append({"title_id": tid, "title": name, "launch": known[1] if known else ""})
    for c in raw.get("classic") or []:
        name = (c.get("localizedGameName") or "").strip()
        if name:
            games.append({"title_id": 0, "title": name, "launch": "", "classic": True})
    write_json(OWNED_FILE, {"t": time.time(), "games": games, "expired": False})
    return games


def mark_expired():
    """Blizzard wants the password again: keep the list, remember it needs a new sign-in.
    Returns True the first time (so the user is told once, not at every start)."""
    data = owned()
    if not data or data.get("expired"):
        return False
    data["expired"] = True
    write_json(OWNED_FILE, data)
    return True


def forget_owned():
    try:
        OWNED_FILE.unlink()
    except OSError:
        pass


class BattleNet(Store):
    id = "battlenet"
    name = "Battle.net"
    color = "#148eff"
    tile = "#1673d9"  # its logo sits in white on a tile of this colour
    login_kind = "external"

    def problem(self):
        try:
            compat()
            return ""
        except StoreError as e:
            return str(e)

    def prefix(self):
        return prefix_path(self.id, "launcher")

    def drive_c(self):
        """C:\\ as Battle.net sees it: the prefix's drive_c on Linux, the real one on Windows."""
        if WINDOWS:
            return os.environ.get("SystemDrive", "C:") + "\\"
        return os.path.join(self.prefix(), "drive_c")

    def launcher_exe(self):
        root = self.drive_c()
        if WINDOWS:
            # Programs and Features' entry names the folder it was installed in.
            folder = reg_value(r"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Battle.net", "InstallLocation", "")
            for p in (os.path.join(folder, "Battle.net.exe") if folder else "",
                      os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), "Battle.net", "Battle.net.exe")):
                if p and os.path.isfile(p):
                    return p
        for rel in ("Program Files (x86)/Battle.net/Battle.net.exe",
                    "Program Files/Battle.net/Battle.net.exe",
                    "Program Files (x86)/Battle.net/Battle.net Launcher.exe"):
            p = os.path.join(root, rel)
            if os.path.isfile(p):
                return p
        return None

    def env(self):
        return wine_env(self.id, "launcher", UMU_ID)

    # Signing in to play happens inside the Battle.net app itself; the Blizzard account link
    # (Accounts > Battle.net > Link account) is only there to list the games you own.
    def logged_in(self):
        return bool(self.launcher_exe() or owned())

    def account(self):
        linked = owned()
        if linked and linked.get("expired"):
            return f"{len(linked.get('games') or [])} games owned · sign in again (Link account) to update the list"
        if linked:
            return f"Blizzard account linked · {len(linked.get('games') or [])} games owned"
        return "app installed; sign in inside it" if self.launcher_exe() else ""

    def login_begin(self):
        exe = self.launcher_exe()
        if not exe:
            raise StoreError("Install the Battle.net app first (its tile is in the library)")
        return {"command": [*wrapper_argv(gamescope=False), exe], "env": self.env()}

    def fetch(self):
        exe = self.launcher_exe()
        games = [Game(store=self.id, id=LAUNCHER_ID, title="Battle.net", installed=bool(exe),
                      install_path=os.path.dirname(exe) if exe else "",
                      cover=LAUNCHER_COVER, cover_fallback=LAUNCHER_COVER)]
        if exe:
            for p in products(self.product_db()):
                uid, code, path = p["uid"], p["code"], p["path"]
                if code.lower() in NOT_GAMES or uid.lower() in NOT_GAMES:
                    continue
                title, launch = PRODUCTS.get(code.lower()) or PRODUCTS.get(uid.lower()) or (
                    os.path.basename(path.replace("\\", "/").rstrip("/")) or uid, code)
                extra = {"launch": launch, "uid": uid, **({"steam_appid": STEAM_APPIDS[code.lower()]}
                                                         if code.lower() in STEAM_APPIDS else {})}
                if p["version"]:
                    extra["version"] = p["version"]
                if p["busy"]:  # Battle.net is downloading it: shown as its install/update progress
                    extra["bnet_busy"] = p["busy"]
                games.append(Game(store=self.id, id=uid, title=title, installed=p["playable"],
                                  install_path=self.linux_path(path) if p["playable"] else "",
                                  extra=extra))
        # Games the Blizzard account owns but this PC has not installed.
        have = {(g.extra.get("launch") or "").lower() for g in games} | {g.title.lower() for g in games}
        for o in (owned() or {}).get("games") or []:
            if o.get("title_id") in MOVED:
                continue
            launch, title = o.get("launch", ""), o.get("title", "")
            if (launch and launch.lower() in have) or title.lower() in have:
                continue
            have |= {launch.lower(), title.lower()} - {""}
            extra = {"launch": launch, "owned_only": True}
            if launch.lower() in UID_BY_LAUNCH:
                extra["uid"] = UID_BY_LAUNCH[launch.lower()]
            if launch in STEAM_BY_LAUNCH:
                extra["steam_appid"] = STEAM_BY_LAUNCH[launch]
            games.append(Game(store=self.id, id="owned-" + (launch or str(o.get("title_id") or title)),
                              title=title, installed=False, extra=extra))
        return games

    def install(self, game):
        if game.id != LAUNCHER_ID:
            exe = self.launcher_exe()
            if not exe:
                raise StoreError("Install the Battle.net app first (its tile is in the library), then install "
                                 + game.title + " from there")
            # Opens the Battle.net app on this game's page, where its Install button is.
            argv = [*wrapper_argv(gamescope=False), exe]
            uid = game.extra.get("uid") or UID_BY_LAUNCH.get((game.extra.get("launch") or "").lower())
            if uid:  # --game takes the product's uid ("fenris"), not its launch code ("Fen")
                argv.append("--game=" + uid)
            return Command(argv, env=self.env(), cwd=os.path.dirname(exe))
        setup = str(CACHE_DIR / "Battle.net-Setup.exe")
        if WINDOWS:  # download Blizzard's installer, then run it and wait
            ps = ("$ErrorActionPreference='Stop'; Invoke-WebRequest -UseBasicParsing -Uri $args[0] -OutFile $args[1]; "
                  "Start-Process -Wait -FilePath $args[1]")
            return Command(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
                            "& {" + ps + "}", SETUP_URL, setup])
        script = 'curl -fL --retry 3 -o "$1" "$2" && shift 2 && exec "$@"'
        return Command(["sh", "-c", script, "cornerplay", setup, SETUP_URL, *wrapper_argv(gamescope=False), setup],
                       env=self.env())

    def uninstall(self, game):
        """Blizzard's own uninstaller, with the command line Battle.net registered for the game."""
        if game.id == LAUNCHER_ID:
            raise StoreError("Battle.net itself stays: uninstall its games from their tiles")
        argv = (uninstall_argv_windows if WINDOWS else uninstall_argv)(self.prefix(), game.extra.get("uid") or game.id)
        if not argv:
            raise StoreError("Uninstall " + game.title + " from inside the Battle.net app")
        exe = argv[0]
        return Command([*wrapper_argv(gamescope=False), *argv], env=self.env(), cwd=os.path.dirname(exe))

    def product_db(self):
        return os.path.join(self.drive_c(), "ProgramData", "Battle.net", "Agent", "product.db")

    def linux_path(self, win_path):
        """"C:/Program Files (x86)/Overwatch" -> the folder inside this prefix (as it is on Windows)."""
        if WINDOWS:
            return os.path.normpath(win_path) if win_path else ""
        p = (win_path or "").replace("\\", "/")
        if len(p) > 1 and p[1] == ":":
            drive = os.path.join(self.prefix(), "dosdevices", p[0].lower() + ":")
            root = os.path.realpath(drive) if os.path.exists(drive) else os.path.join(self.prefix(), "drive_c")
            return os.path.join(root, p[2:].lstrip("/"))
        return p

    def launch(self, game):
        exe = self.launcher_exe()
        if not exe:
            raise StoreError("The Battle.net app is not installed yet")
        if game.id != LAUNCHER_ID and game_options.get(game.key).get("bnet_direct"):
            direct = self.direct_exe(game)
            if direct:  # its own sign-in screen, no Battle.net at all
                return Command([*wrapper_argv(), direct], env=self.env(), cwd=os.path.dirname(direct))
        keep_signed_in(self.prefix())
        argv = [*wrapper_argv(gamescope=False), exe]
        if game.id != LAUNCHER_ID:
            argv.append("--exec=launch " + game.extra.get("launch", game.id))
        return Command(argv, env=self.env(), cwd=os.path.dirname(exe))

    def direct_exe(self, game):
        """The game's own program when it can start without Battle.net (WoW), else ""."""
        rel = DIRECT.get(game.extra.get("uid") or game.id)
        if not rel or not game.install_path:
            return ""
        p = os.path.join(game.install_path, rel)
        return p if os.path.isfile(p) else ""


# --- product.db ---------------------------------------------------------
# A protobuf file: ProductDb { repeated ProductInstall = 1 }, where
# ProductInstall { uid = 1; product_code = 2; settings = 3 { install_path = 1 } }.

def _fields(buf):
    i, n = 0, len(buf)
    while i < n:
        tag, i = _varint(buf, i)
        num, wire = tag >> 3, tag & 7
        if wire == 0:
            val, i = _varint(buf, i)
        elif wire == 2:
            ln, i = _varint(buf, i)
            val, i = buf[i:i + ln], i + ln
        elif wire == 1:
            val, i = buf[i:i + 8], i + 8
        elif wire == 5:
            val, i = buf[i:i + 4], i + 4
        else:
            return
        yield num, wire, val


def _varint(buf, i):
    out = shift = 0
    while True:
        b = buf[i]
        i += 1
        out |= (b & 0x7F) << shift
        if not b & 0x80:
            return out, i
        shift += 7


def _double(b):
    import struct
    return struct.unpack("<d", b)[0] if len(b) == 8 else 0.0


def products(path):
    """Every product Battle.net knows here: [{"uid", "code", "path", "playable", "version",
    "busy"}]. busy is {"kind": "install"|"update", "progress": 0-100} while it downloads.
    product.db is a protobuf (checked against a real one, Battle.net 2.53):
      ProductInstall { 1 uid; 2 product_code; 3 settings { 1 install_path };
                       4 cached_product_state { 1 base { 1 installed; 2 playable; 3 update_complete;
                                                         7 version }
                                                4 update_progress { 2 progress (double, 1.0 = done) } } }"""
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError:
        return []
    out = []
    try:
        for num, wire, val in _fields(data):
            if num != 1 or wire != 2:
                continue
            p = {"uid": "", "code": "", "path": "", "installed": None, "playable": None,
                 "update_complete": None, "version": "", "progress": None}
            for n2, w2, v2 in _fields(val):
                if w2 != 2:
                    continue
                if n2 == 1:
                    p["uid"] = v2.decode("utf-8", "replace")
                elif n2 == 2:
                    p["code"] = v2.decode("utf-8", "replace")
                elif n2 == 3:
                    for n3, w3, v3 in _fields(v2):
                        if n3 == 1 and w3 == 2:
                            p["path"] = v3.decode("utf-8", "replace")
                elif n2 == 4:
                    for n3, w3, v3 in _fields(v2):
                        if n3 == 1 and w3 == 2:
                            for n4, w4, v4 in _fields(v3):
                                if w4 == 0 and n4 in (1, 2, 3):
                                    p[{1: "installed", 2: "playable", 3: "update_complete"}[n4]] = bool(v4)
                                elif n4 == 7 and w4 == 2:
                                    p["version"] = v4.decode("utf-8", "replace")
                        elif n3 == 4 and w3 == 2:
                            for n4, w4, v4 in _fields(v3):
                                if n4 == 2 and w4 == 1:
                                    p["progress"] = _double(v4)
            if not p["uid"]:
                continue
            p["code"] = p["code"] or p["uid"]
            # No state at all (an old Battle.net): trust the entry, as before.
            playable = p["playable"] if p["playable"] is not None else True
            busy = None
            prog = p["progress"]
            if not playable:
                busy = {"kind": "install", "progress": round(100 * prog, 1) if prog is not None and 0 <= prog < 1 else -1.0}
            elif p["update_complete"] is False and prog is not None and 0 <= prog < 1:
                busy = {"kind": "update", "progress": round(100 * prog, 1)}
            out.append({"uid": p["uid"], "code": p["code"], "path": p["path"], "playable": playable,
                        "version": p["version"], "busy": busy})
    except (IndexError, ValueError):
        pass
    return out


def uninstall_argv(prefix, uid):
    """The uninstall command Battle.net registered for a product (Windows registry in the
    prefix): ["C:\\ProgramData\\...\\Blizzard Uninstaller.exe", "--lang=enUS", "--uid=pro", ...]."""
    import shlex
    try:
        with open(os.path.join(prefix, "system.reg"), encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError:
        return []
    for line in text.splitlines():
        if not line.startswith('"UninstallString"=') or "Blizzard Uninstaller" not in line:
            continue
        raw = line.split("=", 1)[1].strip()
        if raw.startswith('"') and raw.endswith('"'):
            raw = raw[1:-1]
        raw = raw.replace('\\"', '"').replace("\\\\", "\\")  # registry file escaping
        if f"--uid={uid}" not in raw.split():
            continue
        try:
            return shlex.split(raw.replace("\\", "\\\\"))
        except ValueError:
            return []
    return []


# --- the game's own process -----------------------------------------------------------------
# Battle.net starts the game and stays open after it closes (or closes as soon as it starts,
# with its "exit when a game starts" setting), so neither tells when you stopped playing.
# The game's processes are found by their program's path, in the game's folder.

def uninstall_argv_windows(_prefix, uid):
    """The same, from the real Windows registry (Programs and Features)."""
    import shlex
    base = r"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
    for sub in reg_subkeys(base):
        raw = reg_value(base + "\\" + sub, "UninstallString", "") or ""
        if "Blizzard Uninstaller" not in raw or f"--uid={uid}" not in raw.split():
            continue
        try:
            return shlex.split(raw.replace("\\", "\\\\"))
        except ValueError:
            return []
    return []


def _norm_path(p):
    return (p or "").replace("\\", "/").rstrip("/").lower()


def pids_under(folders):
    """Processes whose program is inside one of these folders (Windows "C:/..." or Linux paths)."""
    roots = [_norm_path(f) + "/" for f in folders if f and len(_norm_path(f)) > 3]
    if not roots:
        return []
    return [pid for pid, prog in process_programs() if any(_norm_path(prog).startswith(r) for r in roots)]


def game_folders(store, game):
    """Where a game's processes run from: its Windows path as Battle.net knows it, and the same
    folder seen from Linux."""
    win = ""
    for p in products(store.product_db()):
        if p["uid"] == (game.extra.get("uid") or game.id):
            win = p["path"]
    return [f for f in (win, store.linux_path(win) if win else "", game.install_path) if f]


def _launcher_dirs(store):
    exe = store.launcher_exe() if WINDOWS else ""
    return [os.path.join(store.drive_c(), "Program Files (x86)", "Battle.net"), "C:/Program Files (x86)/Battle.net",
            *([os.path.dirname(exe)] if exe else [])]


def launcher_running(store):
    return bool(pids_under(_launcher_dirs(store)))


def close_launcher(store) -> bool:
    """Close the Battle.net app (and its Agent, which goes with it) when Cornerplay started it
    only for a game that has now closed. Not while it downloads: that would stop the download."""
    if any(p["busy"] for p in products(store.product_db())):
        return False
    pids = pids_under(_launcher_dirs(store) + [os.path.join(store.drive_c(), "ProgramData", "Battle.net", "Agent"),
                                               "C:/ProgramData/Battle.net/Agent"])
    for pid in pids:
        if WINDOWS:
            terminate(pid)
            continue
        import signal
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
    return bool(pids)


def keep_signed_in(prefix):
    """Battle.net keeps you signed in between starts (its "AutoLogin"); set it when it is off.
    Only while Battle.net is closed: it writes its config back when it quits."""
    import json
    path = (os.path.join(os.environ.get("APPDATA", ""), "Battle.net", "Battle.net.config") if WINDOWS
            else os.path.join(prefix, "drive_c/users/steamuser/AppData/Roaming/Battle.net/Battle.net.config"))
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return
    client = data.setdefault("Client", {})
    if not isinstance(client, dict) or str(client.get("AutoLogin", "")).lower() == "true":
        return
    if pids_under([os.path.join(prefix, "drive_c/Program Files (x86)/Battle.net"), "C:/Program Files (x86)/Battle.net",
                   *([os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Battle.net")] if WINDOWS else [])]):
        return
    client["AutoLogin"] = "true"
    tmp = path + ".cornerplay"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        os.replace(tmp, path)
    except OSError:
        pass


def watch(store, game, proc, on_change, wait_start=1800, poll=2.0, grace=12.0, on_tick=None):
    """Wait for the game to start and then to close. on_change(pids) is called as its processes
    come and go. Returns (started, ended) times, or (0, 0) when it never started: Battle.net
    closed first, or nothing after wait_start seconds (a long patch: still counted from when
    the game appears, if it does in that time)."""
    import time
    folders = game_folders(store, game)
    begun = time.time()
    seen = last = 0.0
    known = []
    while True:
        now = time.time()
        if on_tick:
            on_tick(bool(seen))  # bnethide: keep Battle.net out of sight, bring it forward when it asks
        if proc is not None:
            proc.poll()  # reap Battle.net's starter when it hands over and exits
        pids = pids_under(folders)
        if pids:
            if not seen:
                seen = now
            last = now
            if sorted(pids) != known:
                known = sorted(pids)
                on_change(known)
        elif seen:
            if now - last > grace:  # gone for a while (a game restarting itself is back sooner)
                return seen, last
        elif now - begun > wait_start:
            return 0.0, 0.0
        elif now - begun > 20 and (proc is None or proc.poll() is not None) and not launcher_running(store):
            return 0.0, 0.0  # Battle.net was closed without starting it
        time.sleep(poll)


def read_product_db(path):
    """Yield (uid, product_code, install_path) for every installed product."""
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError:
        return []
    out = []
    try:
        for num, wire, val in _fields(data):
            if num != 1 or wire != 2:
                continue
            uid = code = install = ""
            for n2, w2, v2 in _fields(val):
                if w2 != 2:
                    continue
                if n2 == 1:
                    uid = v2.decode("utf-8", "replace")
                elif n2 == 2:
                    code = v2.decode("utf-8", "replace")
                elif n2 == 3:
                    for n3, w3, v3 in _fields(v2):
                        if n3 == 1 and w3 == 2:
                            install = v3.decode("utf-8", "replace")
            if uid:
                out.append((uid, code or uid, install))
    except (IndexError, ValueError):
        pass
    return out
