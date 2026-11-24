"""Paths, settings and backend-tool discovery."""
import json
import os
import shutil
import time
from pathlib import Path

# Debian and Ubuntu put Steam and GameMode's gamemoderun in /usr/games, which a session started
# some ways (a launcher, systemd) leaves off PATH: add it, so every shutil.which() finds them.
_path = os.environ.get("PATH", "").split(os.pathsep)
for _d in ("/usr/games", "/usr/local/games"):
    if _d not in _path and os.path.isdir(_d):
        _path.append(_d)
os.environ["PATH"] = os.pathsep.join(p for p in _path if p)

APP = "cornerplay"
HOME = Path.home()
CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", HOME / ".config")) / APP
DATA_DIR = Path(os.environ.get("XDG_DATA_HOME", HOME / ".local/share")) / APP
CACHE_DIR = Path(os.environ.get("XDG_CACHE_HOME", HOME / ".cache")) / APP
BIN_DIR = DATA_DIR / "bin"
LOG_DIR = CACHE_DIR / "logs"
XDG_CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", HOME / ".config"))

LANGUAGES = {"en": "English", "ro": "Română"}  # interface languages: cornerplay/i18n (English is the source)
OLD_NAMES = ("aiolaunch", "kura")  # earlier names of the app, newest first


def _migrate_from_kura():
    """The app was called Kura, then AIO Launch: move the newest old folders over once,
    and keep games where they are."""
    import shutil
    moved_config = False
    for new in (CONFIG_DIR, DATA_DIR, CACHE_DIR):
        for name in OLD_NAMES:
            old = new.with_name(name)
            if old.is_dir() and not new.exists():
                shutil.move(str(old), str(new))
                moved_config |= new == CONFIG_DIR
    old_games = next((HOME / "Games" / n for n in OLD_NAMES if (HOME / "Games" / n).is_dir()), None)
    settings_file = CONFIG_DIR / "settings.json"
    if old_games:
        data = read_json(settings_file, {}) or {}
        if "games_dir" not in data:
            data["games_dir"] = str(old_games)  # installed games and prefixes stay put
            write_json(settings_file, data)



DEFAULTS = {
    "library_dirs": [],  # folders games were moved to (Storage > Move); GOG installs are found there too
    "update_check": True,  # look for a new Cornerplay release once a day
    "tray_while_playing": True,  # the window steps aside into the tray while a game runs (tray.py)
    "close_to_tray": False,      # closing the window keeps Cornerplay running in the tray
    "start_with_pc": False,      # an autostart entry that opens Cornerplay in the tray
    "stream_pc": "",             # the gaming PC Moonlight streams from (its name or address; stream.py)
    "stream_mac": "",            # its network card's MAC address, to wake it (Wake-on-LAN)
    "stream_fit": True,          # this PC hosts: the display switches to the stream's size while it runs
    "stream_screen_off": True,   # this PC hosts: its own screen goes dark while it streams (backlight 0)
    "stream_size": "screen",     # this PC plays: "screen" (fit this screen), "1080", "1440", "2160" or "" (Moonlight's own)
    "profiles": [],        # people using this PC (personal.py); empty: one profile, "Me"
    "profile": "",
    "sync_dir": "",        # a folder another tool syncs between PCs; Cornerplay keeps personal data there
    "machine_id": "",
    "download_limit": 0.0,    # MB/s for Epic / GOG / Amazon downloads; 0 = as fast as it goes (throttle.py)
    "download_limit_day_only": False,  # the limit only outside the overnight hours (full speed at night)
    "auto_update": False,     # update Epic / GOG / Amazon games overnight (mains power, not metered)
    "auto_update_from": 2,
    "auto_update_to": 6,
    "gog_native": True,    # GOG: install the Linux version when the game has one (no Proton)
    "view": "grid",            # main window: "grid" of covers or "list" (a table)
    "home_collapsed": ["free"],  # home sections folded away: "banner", "continue", "free" (Free on Epic starts as one line)
    "smart_lists": [],         # saved filters shown as lists in the sidebar: [{"name", "store", "installed", "tags"}]
    "ui_scale": 0.0,           # interface size: 0 = automatic, else 1.0 / 1.15 / 1.3 / 1.5 / 2.0 (after a restart)
    "save_backups": True,    # zip a game's saves before each start (savebackup.py)
    "sync_saves": True,      # with a sync folder: share each game's latest saves between your PCs (savebackup.share)
    "backup_keep": 5,        # backups kept per game
    "card_shadow": "none",   # cover shadows: "none", "soft", "deep"
    "evening_warmth": True,  # surfaces turn a little warmer in the evening and at night
    "wallpaper_backdrop": True,  # Follow wallpaper: the wallpaper, blurred, behind the main window
    "bg_mode": "",           # behind the library: "" (plain), "picture" (bg_picture), "gradient" (slowly moving), "game" (the last played game's art)
    "bg_picture": "",
    "shelf_backgrounds": {}, # a collection's own picture: {"c:<name>": path}
    "tv_reflection": False,  # TV mode: covers reflected on the shelf below
    "hover_preview": True,   # a details card after the pointer rests on a cover (Settings > Appearance)
    "card_tilt": True,       # desktop covers tip toward the pointer, with a soft light (Settings > Appearance)
    # Looks for the desktop library (Settings > Appearance > Look), each on its own:
    "look_ambient": False,   # the game's colour: a soft glow behind the library, coloured shadows under covers
    "look_glass": False,     # frosted sidebar and toolbar over the last game's art
    "look_showcase": False,  # a taller banner that drifts, turns between the last three games, with facts
    "look_rich": False,      # covers: title and playtime under them, colour on hover for games not installed
    "look_titles": False,    # bigger section titles and a greeting
    "look_motion": False,    # covers come in one after another; the library glides when it changes
    "look_page": True,       # a game's panel opens on its full art with the logo and facts
    "look_shelves": False,   # Home as rows (Continue, Ready to play, Recently added, Not played yet); every game in All games
    "look_wide": False,      # Continue playing as big cards: art, hours, achievements, your last screenshot
    "look_search": False,    # a floating search pill, with quick filters under it
    "look_sidebar": False,   # the sidebar's selection in the game's colour, and what is running or downloading at its foot
    "look_expand": False,    # resting on a cover opens it into a wide card with art, trailer and Play
    "look_skeleton": True,   # covers shimmer while their art loads (on by default: screens keep their shape)
    "look_playring": False,  # Play turns into a ring while the game starts, then a tick
    "look_aurora": False,    # three colours from the game's cover drift behind the library like an aurora
    "look_pagetabs": True,   # a game's page: section tabs, a slim header that stays when you scroll, a playtime chart
    "home_layout": "",       # Home's shape: "" (covers), "bento", "console", "magazine", "coverflow" (DeskHome.qml)
    "look_fullart": False,   # the whole window is the art of the game under the pointer, the rest frosted over it
    "look_island": False,    # a pill at the top that turns into the download, the game running, or the time
    "desk_skin": "",         # the TV skins on the desktop too: "phosphor", "gallery", "arcade"
    "quick_launcher": True,  # `cornerplay --launcher` (bind it to a key): a small search-and-play window
    "tv_intro": False,       # TV mode: a short start-up animation and chime
    "tv_animated": True,   # animated covers and banners in TV mode (SteamGridDB key; only when plugged in)
    "peer_reports": True,  # ProtonDB's monthly open data: what players with a PC like this one did (pdbreports.py)
    "shader_warmup": True,  # record games' shaders (Steam's Fossilize) and build them again after a driver update
    "shader_cache": True,  # keep each game's shader cache (DXVK, VKD3D, Mesa, NVIDIA) and let it grow
    "perf": "",            # default performance profile: "", "battery", "balanced", "quality"
    "show_fps": False,
    "perf_log": False,     # MangoHud logs each session; a game's page shows FPS, stutters and temperatures (perf.py)
    "games_dir": str(HOME / "Games" / APP),
    "proton": "GE-Proton",  # umu PROTONPATH: "GE-Proton", a path, or "" for UMU-Proton
    "mangohud": False,
    "gamescope": "",           # run games inside gamescope: "", "fullscreen" (at the screen's resolution) or "fsr" (upscaled)
    "gamescope_hdr": False,    # gamescope's HDR output (needs an HDR screen and a compositor that passes it on)
    "screen_size": [],         # the main screen in pixels, noted at start-up (gamescope's output size)
    "gamemode": False,
    "steam_api_key": "",
    "steam_id": "",
    "steamgriddb_key": "",
    "install_window": True,     # Install asks where, which language and DLCs first (Epic, GOG, Amazon)
    "language": "",             # interface language: "" = the system's, "en", "ro" (after a restart)
    "rom_dirs": [],             # folders with ROMs for Retro games (stores/retro.py)
    "screenshot_dirs": [],      # more folders to find your screenshots in (screenshots.py)
    "wishlist_sales": True,
    "dlc_watch": True,          # look up favourite/installed/recent games' DLC daily: card counts, new-DLC toasts
    "itad_key": "",             # IsThereAnyDeal API key: the best price on any store for the wishlist (itad.py)
    "price_watch": {},          # wishlist "store:id" -> the discount to wait for (1: any sale, 25/50/75/90 % off)
    "price_watch_told": [],
    "fps_cap": 0,               # frames per second cap for every game (each can set its own), 0 = none
    "tdp": 0,                   # power limit in watts for every game (AMD + ryzenadj, tdp.py), 0 = leave alone
    "clips": False,             # keep the last 30 s of a game to save on demand (gpu-screen-recorder, clips.py)
    "family": {},               # family limits per person (family.py)
    "family_pin": "",
    "lights": "",               # room lights in the game's colour: "", "openrgb", "hue" (lights.py)
    "hue_bridge": "",
    "hue_user": "",
    "hue_group": "0",           # all lights, or a room's group id
    "tv_skin": "",              # TV mode's look: "", "phosphor", "gallery", "arcade"
    "phone_remote": False,      # the phone remote and web library on the home network (remote.py), off by default
    "prelaunch_checks": True,   # before a game: battery, downloads, a missing controller, a full drive (toasts)
    "pad_battery_alerts": True, # a wireless controller at 20 % or less: say so (also over a game)
    "tv_library_view": "grid",  # TV mode's Library page: "grid" (covers) or "list"
    "tv_library_sort": "name",  # TV mode's Library page's own order
    "deal_alert_cut": 50,       # announce a wishlist deal at least this much off (or a new lowest price)
    "store_country": "",        # two letters for store prices (AU, RO, ...); empty: your GOG account's, else the system's     # "On sale from your wishlist" on the home page (Steam and GOG wishlists)
    "discord_presence": False,  # "Playing <game>" on Discord for Epic / GOG / Amazon games (discord.py)
    "discord_app_id": "",       # the Application ID of a Discord application named "Cornerplay"
    "igdb_client_id": "",      # a Twitch developer app, for IGDB's time-to-beat (timetobeat.py)
    "igdb_client_secret": "",
    "env": "",                 # extra environment for every game: KEY=VALUE KEY2=VALUE2
    "theme_auto": "",           # "" (as chosen), "system" (follow the desktop's light/dark), "sunset" (dark from 7 pm)
    "theme_light": "Paper",     # the light and dark presets for theme_auto
    "theme_dark": "Cornerplay",
    "theme_mode": "Cornerplay",  # "Cornerplay" (amber, the signature look), "ryoku" (wallpaper), a preset, or "custom"
    "theme_bg": "#141218",
    "theme_accent": "#d2bcfd",
    "card_size": 196,
    "seasonal": False,         # a small seasonal touch on empty screens and the splash (Seasonal.qml)
    "density": "comfortable",  # space between covers: "compact", "comfortable", "roomy"
    "title_font": "",          # game titles: "" (rounded, Nunito), "condensed", "serif", "pixel"
    "card_radius": 14,
    "show_badges": True,
    "show_titles": False,
    "dim_uninstalled": True,
    "merge_duplicates": True,
    "cloud_saves": True,
    "steam_games": False,      # keep installed games in Steam (Game Mode) automatically
    "performance": "auto",     # "auto", "light" or "full"
    "sort": "name",            # library order: "name", "recent" or "playtime"
    "tv_trailers": True,       # TV mode plays the focused game's trailer (muted) after a moment
    "hover_trailers": True,    # the library plays a cover's trailer (muted) inside it while it is pointed at
    "tv_sounds": False,        # TV mode makes soft clicks when moving and choosing
    "tv_rumble": False,        # TV mode: the controller buzzes lightly when moving and choosing
    "tv_music": False,         # TV mode: a calm, original ambient loop (fades out for trailers and games)
    "gpu": "auto",             # graphics card for games on two-card PCs: auto (the fast one) / discrete / integrated (gpu.py)
    "lan_share": False,        # other PCs at home may copy installed games from this one (lancopy.py)
    "lan_code": "",            # this PC's code for that, made when sharing is turned on
    "lan_peers": {},           # linked PCs: {name: {"host", "port", "code"}}
    "fast_cores": False,       # games pinned to the fast cores on hybrid Intel / dual-group X3D AMD CPUs (cores.py)
    "ntsync": True,            # Proton uses the kernel's NTSYNC when /dev/ntsync is there (runner.proton_extras)
    "focus_scheduler": False,
    "focus_lowlat": True,      # Hyprland: tearing + VRR for full-screen games while playing (Ryoku: its Game Mode) (playtweaks.py)
    "game_workspace": False,
    "hud_levels": False,       # MangoHud levels (off / FPS / basic / full) switched from quick access while playing (hudlevels.py)   # Hyprland: games open on an empty workspace; back to yours when they close
    "jobs_low_priority": True, # installs, updates, compression run at low disk/CPU priority (ionice/nice)  # a gaming CPU scheduler (sched-ext LAVD) while playing (scx.py)
    "battlenet_hide": True,    # Hyprland: Battle.net's window stays hidden while its games start (bnethide.py)
    "battlenet_warm": False,   # Battle.net started hidden with Cornerplay, so its games start in seconds
    "update_safety": True,     # btrfs: an instant copy of a game before it updates, to roll back (safety.py)
    "tv_screen": "auto",       # TV mode opens on: "auto" a TV/monitor when one is plugged in, "" this screen, or a name (tvscreen.py)
    "tv_screensaver": 3,       # TV mode: minutes without input before the slideshow of your games (0 = never)
    "tv_who": True,            # TV mode: "Who's playing?" at start when there are several people
    "show_protondb": True,     # ProtonDB rating badge on covers
    # gamescope's live display settings (TV mode's Performance tab), set again when a session starts
    "gs_fps_limit": 0,         # frames per second cap for games, 0 = none
    "gs_filter": "linear",     # upscaling: "linear", "nearest", "fsr", "nis", "pixel"
    "gs_scaler": "auto",       # fitting: "auto", "integer", "fit", "fill", "stretch"
    "gs_sharpness": 18,        # FSR / NIS sharpness, 0..20 (higher is sharper)
    "gs_tearing": False,       # allow tearing (lower latency)
    "gs_hdr": False,           # gamescope's HDR output, when the screen supports it
    "space_nudge_at": 0,
    "releases_announced": [],
    "night_queue": [],         # games to install in the overnight hours (auto_update_from / _to)
    "night_after": "",         # when the overnight installs are done: "", "suspend" or "shutdown"  # wishlist games already announced as out (the release calendar)       # when Cornerplay last said which old games take room (once a week at most)
    # Accessibility (Settings > Appearance; TV mode's Settings > Accessibility)
    "a11y_contrast": False,    # stronger contrast: text, outlines and edges toward black and white
    "a11y_colours": "",        # colour-blind friendly colours: "", "redgreen", "blueyellow"
    "a11y_motion": False,      # reduce motion: no sliding, zooming or drifting art
    "a11y_speak": False,       # TV mode reads out what is selected (speech.py)
    # Focus while playing (focus.py)
    "focus_dnd": True,         # hold notifications back (Ryoku: its Game Mode)
    "focus_awake": True,       # keep the screen on and the PC awake
    "focus_power": False,      # the Performance power mode while playing
    "focus_downloads": True,   # pause downloads while playing
    # Controllers
    "pad_keys_custom": {},     # My layout: controller as keyboard and mouse (padkeys.py)
    "pad_layout": "",          # games' controller layout (padlayout.py): "", "swap_ab", "nintendo", "southpaw", "shoulders"
    "pad_glyphs": "",          # button prompts: "" (from the controller), "xbox", "playstation", "nintendo"
    "pad_shape": "",           # Test your controller's drawing: "" (from the controller) or a gamepad.SHAPES name
    "pad_swap_confirm": False, # Cornerplay's menus: B chooses and A goes back (the Nintendo / Japanese way)
}

# Where Heroic keeps its bundled copies of legendary / gogdl / nile.
_HEROIC_BIN_DIRS = [
    "/opt/Heroic/resources/app.asar.unpacked/build/bin/x64/linux",
    "/opt/heroic/resources/app.asar.unpacked/build/bin/x64/linux",
    "/usr/lib/heroic/resources/app.asar.unpacked/build/bin/x64/linux",
]

BACKEND_REPOS = {"legendary": "Heroic-Games-Launcher/legendary", "gogdl": "Heroic-Games-Launcher/heroic-gogdl",
                 "nile": "imLinguin/nile"}


class Settings:
    def __init__(self):
        self.path = CONFIG_DIR / "settings.json"
        self.data = dict(DEFAULTS)
        try:
            self.data.update(json.loads(self.path.read_text()))
        except (OSError, ValueError):
            pass

    def get(self, key, default=None):
        """Like dict.get: the setting, else its default from DEFAULTS, else `default`."""
        return self.data.get(key, DEFAULTS.get(key, default))

    listeners: list = []  # called after every change (the app drops what it worked out from settings)

    def set(self, key, value):
        self.data[key] = value
        write_private(self.path, json.dumps(self.data, indent=2))
        for fn in list(self.listeners):
            fn()

    @property
    def games_dir(self) -> Path:
        return Path(os.path.expanduser(self.get("games_dir")))




def find_tool(name: str) -> str | None:
    """Locate a backend binary: PATH, Cornerplay's own bin dir, then Heroic's bundle."""
    found = shutil.which(name)
    if found:
        return found
    from .host import BUNDLED_BIN
    for d in [str(BIN_DIR), BUNDLED_BIN, *_HEROIC_BIN_DIRS]:
        p = os.path.join(d, name)
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return None


def read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _tmp_for(path):
    """A temporary file next to path, its own for this write: two threads (or two Cornerplays)
    saving the same file at once each replace it whole instead of tripping over one .tmp."""
    import tempfile
    fd, name = tempfile.mkstemp(dir=path.parent, prefix="." + path.name + ".", suffix=".tmp")
    return fd, Path(name)


def write_json(path, data):
    write_private(path, json.dumps(data), private=False)


def write_private(path, text: str, private=True):
    """Write a file atomically; only this user can read it (settings with API keys, sign-in
    tokens) unless private is False."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = _tmp_for(path)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.chmod(tmp, 0o600 if private else 0o644)
        tmp.replace(path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def _lock_down():
    """Cornerplay's settings folder holds API keys and store sign-in tokens: only this user
    may open it (folders made by earlier versions were readable by everyone on the PC). The
    same for the sign-ins Cornerplay makes through legendary (Epic) and nile (Amazon): both
    leave their tokens readable by every account on the PC."""
    for f in (XDG_CONFIG / "legendary" / "user.json",):
        try:
            if f.stat().st_mode & 0o077:
                f.chmod(0o600)
        except OSError:
            pass
    for d in (CONFIG_DIR, DATA_DIR, XDG_CONFIG / "legendary", XDG_CONFIG / "nile"):
        try:
            if d.stat().st_mode & 0o077:
                d.chmod(0o700)
        except OSError:
            pass
    for f in CONFIG_DIR.glob("*.json"):
        try:
            if f.stat().st_mode & 0o077:
                f.chmod(0o600)
        except OSError:
            pass


class GameOptions:
    """Per-game overrides, keyed "store:id". A missing key means "use the default"."""
    KEYS = ("proton", "mangohud", "gamemode", "env", "args", "cover", "prefer", "cloud_saves", "hidden", "collections",
            "status", "rating", "note", "perf", "show_fps", "platform", "gamescope", "gamescope_hdr",
            "before", "after", "pad_layout", "put_away", "pad_keys", "gog_lang", "fps_cap", "tdp")

    def __init__(self):
        self.path = CONFIG_DIR / "games.json"
        self.data = read_json(self.path, {}) or {}
        self.times_path = CONFIG_DIR / "games_changed.json"  # when each game's options last changed (gamesync.py)
        self.times = read_json(self.times_path, {}) or {}
        self.listeners = []  # called after a change (the app syncs it out to other PCs)

    def get(self, key) -> dict:
        return dict(self.data.get(key, {}))

    _EMPTY = {}

    def peek(self, key) -> dict:
        """The entry itself, for reading only (no copy: the library asks this thousands of times)."""
        return self.data.get(key) or self._EMPTY

    def set(self, key, name, value):
        if name not in self.KEYS:
            return
        entry = self.data.setdefault(key, {})
        if value in ("", None, "default"):
            entry.pop(name, None)
        else:
            entry[name] = value
        if not entry:
            self.data.pop(key, None)
        write_private(self.path, json.dumps(self.data))
        self.times[key] = time.time()
        write_json(self.times_path, self.times)
        for fn in self.listeners:
            fn()

    def save(self):
        """After gamesync.py changed several games at once."""
        write_private(self.path, json.dumps(self.data))
        write_json(self.times_path, self.times)




_migrate_from_kura()
for _d in (CONFIG_DIR, DATA_DIR, CACHE_DIR, BIN_DIR, LOG_DIR):
    _d.mkdir(parents=True, exist_ok=True)
_lock_down()
settings = Settings()
game_options = GameOptions()
