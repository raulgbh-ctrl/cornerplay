"""Each game's settings on every PC (with a sync folder, Settings > People & sync).

What travels: Proton version, MangoHud, GameMode, gamescope, performance profile, FPS counter,
environment variables, launch arguments, Linux or Windows version, the store a merged game
launches from, cloud saves and hidden. A game's settings move as one: the newer change wins.
A Proton build is sent by its folder name and used on the other PC only when a build with that
name is there; otherwise that PC keeps its own choice. Custom covers stay (they are files here).

    <sync folder>/Cornerplay/game-settings.json   {key: {"t": changed, "o": {name: value}}}
"""
import os
import re
import shlex

from .config import game_options, read_json, write_json

SYNCED = ("proton", "mangohud", "gamemode", "env", "args", "perf", "show_fps", "platform",
          "gamescope", "gamescope_hdr", "prefer", "cloud_saves", "hidden")
FILE = "game-settings.json"


def portable(opts):
    """A game's synced options, with a Proton folder path turned into the folder's name."""
    out = {k: opts[k] for k in SYNCED if k in opts}
    p = out.get("proton")
    if isinstance(p, str) and os.path.isabs(p):
        out["proton"] = {"name": os.path.basename(p.rstrip("/"))}
    return out


def local_proton(value, builds=None):
    """The value to use here for a synced Proton: a name kept as it is ("GE-Proton"), a folder
    name matched to a build on this PC; None when this PC has no such build."""
    if not isinstance(value, dict):
        return value if isinstance(value, str) else None
    name = str(value.get("name") or "")
    if builds is None:
        from . import protons
        builds = [b["path"] for b in protons.find()]
    return next((b for b in builds if os.path.basename(b.rstrip("/")) == name), None)


# Variables that make every program the game starts load or run something else: a synced
# setting must never carry them (a shared or compromised sync folder would run code here).
RISKY_ENV = re.compile(r"^(LD_\w+|BASH_ENV|ENV|PATH|PYTHON\w*|PERL5\w*|RUBY\w*|NODE_OPTIONS|GIO_\w+|GTK_MODULES|"
                       r"QT_PLUGIN_PATH|VK_LAYER_PATH|VK_ADD_LAYER_PATH|VK_ICD_FILENAMES|VK_DRIVER_FILES|"
                       r"WINEDLLPATH|WINESERVER|WINELOADER|PROTON_\w*PATH\w*|STEAM_COMPAT_\w+|PRESSURE_VESSEL_\w+)$", re.I)


def safe_env(text):
    """A synced env line without the variables above (kept as typed otherwise)."""
    from .runner import parse_env
    if not isinstance(text, str):
        return ""
    keep = {k: v for k, v in parse_env(text).items() if not RISKY_ENV.match(k)}
    return " ".join(f"{k}={shlex.quote(v)}" for k, v in keep.items())


def _clean(remote):
    """The shared file comes from other PCs: keep only well-formed entries."""
    out = {}
    for k, v in (remote if isinstance(remote, dict) else {}).items():
        if isinstance(k, str) and ":" in k and isinstance(v, dict) and isinstance(v.get("t"), (int, float)) \
                and isinstance(v.get("o"), dict):
            o = {n: x for n, x in v["o"].items() if n in SYNCED}
            if "env" in o:
                o["env"] = safe_env(o["env"])
            if "args" in o and not isinstance(o["args"], str):
                o.pop("args")
            out[k] = {"t": float(v["t"]), "o": o}
    return out


def sync(root, builds=None):
    """Merge this PC's game settings with the sync folder both ways. Returns how many games
    took settings from another PC."""
    path = root / FILE
    remote = _clean(read_json(path, {}))
    taken = 0
    keys = set(remote) | {k for k in game_options.times if k in game_options.data or k in remote}
    merged = {}
    for key in keys:
        mine_t = float(game_options.times.get(key, 0))
        theirs = remote.get(key)
        if theirs and theirs["t"] > mine_t + 1:
            current = game_options.get(key)
            for name in SYNCED:
                value = theirs["o"].get(name)
                if name == "proton" and value is not None:
                    value = local_proton(value, builds)
                    if value is None:
                        continue  # no such build here: keep this PC's choice
                if current.get(name) != value:
                    entry = game_options.data.setdefault(key, {})
                    if value in ("", None, "default"):
                        entry.pop(name, None)
                    else:
                        entry[name] = value
            if not game_options.data.get(key, True):
                game_options.data.pop(key, None)
            game_options.times[key] = theirs["t"]
            merged[key] = theirs
            taken += 1
        elif mine_t:
            merged[key] = {"t": mine_t, "o": portable(game_options.get(key))}
    if taken:
        game_options.save()
    write_json(path, merged)
    return taken
