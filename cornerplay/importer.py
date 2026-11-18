"""Bring games that are already on disk into Cornerplay, instead of downloading them again.

- a folder: GOG games inside it (goggame-<id>.info or a Linux version's gameinfo) are found
  from then on (the folder joins library_dirs)
- an Epic or Amazon game's folder: `legendary import` / `nile import` with the game chosen
- Heroic's installs: read its installed lists and import each game (native and Flatpak Heroic)
"""
import glob
import json
import os
import shutil

from .config import HOME, read_json, settings
from .stores.base import run

HEROIC_DIRS = [HOME / ".config/heroic", HOME / ".var/app/com.heroicgameslauncher.hgl/config/heroic"]


def gog_in(folder):
    """GOG game folders in folder (itself, or one level down): [(game id, path)]."""
    found = []
    for pattern, linux in (("goggame-*.info", False), ("gameinfo", True)):
        for base in (folder, os.path.join(folder, "*")):
            for f in glob.glob(os.path.join(base, pattern)):
                try:
                    if linux:
                        lines = open(f, errors="replace").read().splitlines()
                        gid = lines[4].strip() if len(lines) >= 5 else ""
                    else:
                        info = json.load(open(f))
                        gid = str(info.get("gameId", ""))
                        if gid != str(info.get("rootGameId", gid)):
                            continue  # a DLC's info file
                except (OSError, ValueError):
                    continue
                if gid.isdigit():
                    found.append((gid, os.path.dirname(f)))
    return list(dict(found).items())


def add_library_dir(path):
    dirs = [d for d in settings.get("library_dirs") or [] if isinstance(d, str)]
    if path not in dirs:
        settings.set("library_dirs", dirs + [path])


def import_gog(folder):
    """Returns how many GOG games were found (their parent folders now get scanned)."""
    games = gog_in(folder)
    for _gid, path in games:
        add_library_dir(os.path.dirname(path))
    return len(games)


def import_epic(legendary, app_name, folder):
    r = run([legendary, "import", app_name, folder, "--disable-check"], timeout=300)
    return r.returncode == 0, (r.stderr or r.stdout or "").strip().splitlines()[-1:] or [""]


def import_amazon(nile, gid, folder):
    r = run([nile, "import", gid, "--path", folder], timeout=300)
    return r.returncode == 0, (r.stderr or r.stdout or "").strip().splitlines()[-1:] or [""]


def heroic_installs():
    """What Heroic installed: [{"store", "id", "title", "path"}] (Epic, GOG, Amazon)."""
    out = []
    for base in HEROIC_DIRS:
        epic = read_json(base / "legendaryConfig/legendary/installed.json") or {}
        for app, e in epic.items() if isinstance(epic, dict) else []:
            if isinstance(e, dict) and e.get("install_path") and not e.get("is_dlc"):
                out.append({"store": "epic", "id": app, "title": e.get("title", app), "path": e["install_path"]})
        gog = (read_json(base / "gog_store/installed.json") or {}).get("installed") or []
        for e in gog:
            if isinstance(e, dict) and e.get("install_path") and e.get("appName"):
                out.append({"store": "gog", "id": str(e["appName"]), "title": e.get("title", ""), "path": e["install_path"]})
        amazon = read_json(base / "nile_config/nile/installed.json") or []
        for e in amazon if isinstance(amazon, list) else []:
            if isinstance(e, dict) and e.get("path") and e.get("id"):
                out.append({"store": "amazon", "id": e["id"], "title": e.get("title", ""), "path": e["path"]})
    return [g for g in out if os.path.isdir(g["path"])]


# --- Lutris -------------------------------------------------------------------------------
LUTRIS_DBS = ("~/.local/share/lutris/pga.db", "~/.var/app/net.lutris.Lutris/data/lutris/pga.db")


def lutris_games():
    """Lutris's installed games: [{"id", "title", "runner", "flatpak"}] from its database (read
    only). They join Cornerplay as games that start through Lutris, so Lutris keeps its runners,
    wine builds and install scripts."""
    import sqlite3
    out = []
    for path in LUTRIS_DBS:
        db = os.path.expanduser(path)
        if not os.path.isfile(db):
            continue
        try:
            con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=2)
            rows = con.execute("SELECT id, name, runner FROM games WHERE installed = 1 ORDER BY name").fetchall()
            con.close()
        except sqlite3.Error:
            continue
        for gid, name, runner in rows:
            if name and runner != "steam":  # Steam games are in Cornerplay already
                out.append({"id": int(gid), "title": str(name), "runner": runner or "", "flatpak": "/.var/app/" in db})
    return out


def lutris_command(game):
    """The program and arguments that start a Lutris game."""
    if game["flatpak"]:
        return shutil.which("flatpak") or "/usr/bin/flatpak", f"run net.lutris.Lutris lutris:rungameid/{game['id']}"
    return shutil.which("lutris") or "/usr/bin/lutris", f"lutris:rungameid/{game['id']}"
