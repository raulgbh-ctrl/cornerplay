"""Clean up what games leave behind (Storage > Clean up).

Three kinds, each safe to delete:
- shaders: Steam's shader caches of games that are no longer installed in any Steam library
  (steamapps/shadercache/<appid>; non-Steam shortcuts are left alone);
- crashes: crash dumps over a day old, in game folders and the games' Proton prefixes
  (*.dmp, Unreal's Saved/Crashes, Unity's Crashes folders, Windows' CrashDumps);
- redist: the DirectX / Visual C++ / .NET installers games ship (Steam's _CommonRedist,
  GOG's __redist, and Redist / DirectX / vcredist folders that hold nothing but installers), only
  for games already played: they run once, at the first start.
  Steam may download _CommonRedist again when it verifies a game's files.
Saves, settings and Proton prefixes are never touched (Storage lists leftover prefixes separately).
"""
import os
import re
import shutil
import time

from .storage import _walk, nice

DAY = 86400
REDIST_DIRS = {"_commonredist", "__redist"}
SHORTCUT_IDS = 1 << 31  # non-Steam shortcuts get app ids above this


def _steam_libraries():
    try:
        from .stores.steam import Steam
        return [lib for lib in Steam().library_dirs() if os.path.isdir(lib)]
    except Exception:
        return []


def orphan_shader_caches(libraries=None):
    """[(path, appid)] for shader caches whose game isn't installed in any Steam library."""
    libraries = _steam_libraries() if libraries is None else libraries
    installed = set()
    for lib in libraries:
        try:
            names = os.listdir(os.path.join(lib, "steamapps"))
        except OSError:
            continue
        installed |= {m.group(1) for m in (re.match(r"appmanifest_(\d+)\.acf$", n) for n in names) if m}
    out = []
    for lib in libraries:
        root = os.path.join(lib, "steamapps", "shadercache")
        for name in sorted(os.listdir(root)) if os.path.isdir(root) else []:
            path = os.path.join(root, name)
            if name.isdigit() and int(name) < SHORTCUT_IDS and name not in installed and os.path.isdir(path) \
                    and not os.path.islink(path):
                out.append((path, name))
    return out


def _old(path, now):
    """Over a day old: a file by its date, a folder by the newest file in it."""
    try:
        newest = os.lstat(path).st_mtime if not os.path.isdir(path) else 0
        if os.path.isdir(path):
            for base, _dirs, files in os.walk(path, onerror=lambda e: None):
                for f in files:
                    newest = max(newest, os.lstat(os.path.join(base, f)).st_mtime)
        return newest > 0 and now - newest > DAY
    except OSError:
        return False


def crash_dumps(game_dirs, prefixes, now=None):
    """Crash dump files and folders (over a day old) in game folders and Proton prefixes."""
    now = now or time.time()
    found = []

    def walk(root, depth):
        """*.dmp files and Crashes folders under root, at most depth folders down."""
        base_depth = root.rstrip(os.sep).count(os.sep)
        for base, dirs, files in os.walk(root, onerror=lambda e: None):
            if base.count(os.sep) - base_depth >= depth:
                dirs[:] = []
            dirs[:] = [d for d in dirs if not os.path.islink(os.path.join(base, d))]
            for d in list(dirs):
                low = d.lower()
                if low == "crashes" or (low == "crashdumps" and "appdata" in base.lower()):
                    p = os.path.join(base, d)
                    if _old(p, now):
                        found.append(p)
                    dirs.remove(d)
            for f in files:
                if f.lower().endswith((".dmp", ".mdmp")):
                    p = os.path.join(base, f)
                    if _old(p, now):
                        found.append(p)

    for g in game_dirs:
        if g and os.path.isdir(g):
            walk(g, 5)
    for pfx in prefixes:
        appdata = os.path.join(pfx, "drive_c", "users", "steamuser", "AppData")
        for sub in ("Local", "LocalLow", "Roaming"):
            if os.path.isdir(os.path.join(appdata, sub)):
                walk(os.path.join(appdata, sub), 5)
    return sorted(set(found))


# Folders other games use for the same installers: removed only when everything in them is an
# installer or its notes (a game may keep DLLs it really loads in a folder called "redist").
MAYBE_REDIST = {"redist", "redists", "redistributables", "directx", "vcredist", "_installer", "installers",
                "dotnetfx", "physx", "oalinst"}
INSTALLER_FILES = (".exe", ".msi", ".cab", ".txt", ".ini", ".xml", ".rtf", ".htm", ".html", ".url", ".pdf")


def _only_installers(folder, limit=4000):
    n = 0
    for root, _dirs, files in os.walk(folder):
        for f in files:
            n += 1
            if n > limit or not f.lower().endswith(INSTALLER_FILES):
                return False
    return n > 0


def redist_installers(played_game_dirs):
    """Installer folders (_CommonRedist, __redist, and Redist / DirectX / vcredist ... holding only
    installers) at the top of games you have played."""
    out = []
    for g in played_game_dirs:
        try:
            names = os.listdir(g)
        except OSError:
            continue
        for n in names:
            p = os.path.join(g, n)
            if not os.path.isdir(p) or os.path.islink(p):
                continue
            low = n.lower()
            if low in REDIST_DIRS or (low in MAYBE_REDIST and _only_installers(p)):
                out.append(p)
    return sorted(out)


def scan(game_dirs, played_game_dirs, prefixes):
    """{"groups": [{id, count, bytes, size, items: [{path, name, bytes, size}]}], "bytes", "size"}."""
    def rows(paths, name_of=os.path.basename):
        items = []
        for p in paths:
            b = _walk(p) if os.path.isdir(p) else (os.path.getsize(p) if os.path.isfile(p) else 0)
            if b:
                items.append({"path": p, "name": name_of(p), "bytes": b, "size": nice(b)})
        items.sort(key=lambda r: -r["bytes"])
        return items

    shaders = orphan_shader_caches()
    names = {p: a for p, a in shaders}
    groups = [
        {"id": "shaders", "items": rows([p for p, _a in shaders], lambda p: names.get(p, os.path.basename(p)))},
        {"id": "crashes", "items": rows(crash_dumps(game_dirs, prefixes),
                                        lambda p: os.path.relpath(p, _owner(p, game_dirs, prefixes)))},
        {"id": "redist", "items": rows(redist_installers(played_game_dirs),
                                       lambda p: os.path.basename(os.path.dirname(p)))},
    ]
    total = 0
    for g in groups:
        g["count"] = len(g["items"])
        g["bytes"] = sum(r["bytes"] for r in g["items"])
        g["size"] = nice(g["bytes"])
        total += g["bytes"]
    return {"groups": groups, "bytes": total, "size": nice(total)}


def _owner(path, game_dirs, prefixes):
    for root in sorted(list(game_dirs) + list(prefixes), key=len, reverse=True):
        if root and path.startswith(root.rstrip(os.sep) + os.sep):
            return os.path.dirname(root.rstrip(os.sep))
    return os.path.dirname(path)


def delete(paths, allowed):
    """Delete these paths (each must be one the last scan found). Returns bytes freed."""
    freed = 0
    for p in paths:
        if p not in allowed or os.path.islink(p):
            continue
        try:
            if os.path.isdir(p):
                b = _walk(p)
                shutil.rmtree(p)
            else:
                b = os.path.getsize(p)
                os.unlink(p)
            freed += b
        except OSError:
            continue
    return freed
