"""btrfs tricks that cost no disk: a safety copy of a game before it updates, and identical Windows
files shared between Proton prefixes.

Safety copy (Settings: on): before Epic, GOG or Amazon update a game on btrfs, its folder is
copied with cp --reflink (instant; the copy shares every byte with the game until the update
changes a file, so it costs only what the update replaces). If the update breaks the game, the
game's menu has "Undo the last update": the copy goes back in place. Copies older than a week go
by themselves. The store's own record keeps the new version number, so it may offer the update
again: skip it until the game is fixed upstream.

Shared prefix files (Storage): every Windows game has its own Proton prefix, and most of a prefix
is the same Windows DLLs. Files that are byte-for-byte the same across prefixes are made to share
their data (a reflink copy over each duplicate, checked byte for byte first): nothing changes for
the games, the disk keeps one copy.
"""
import hashlib
import os
import shlex
import shutil
import subprocess
import time

from .config import settings

KEEP_DAYS = 7


def _root(path):
    """The safety copies live next to the games (same drive, or reflink cannot share)."""
    return os.path.join(os.path.dirname(os.path.abspath(path)), ".cornerplay-before-update")


def copy_path(key, path):
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in key)
    return os.path.join(_root(path), safe)


def wrap(key, path, cmd):
    """An update Command that first makes the safety copy (in the job's own process, so the window
    never waits). Any problem with the copy is skipped: the update still runs."""
    from . import compress
    if not settings.get("update_safety") or not path or not os.path.isdir(path) or not compress.available(path):
        return cmd
    dest = copy_path(key, path)
    script = (f"rm -rf {shlex.quote(dest)}.new; mkdir -p {shlex.quote(_root(path))} && "
              f"cp -a --reflink=always {shlex.quote(path)} {shlex.quote(dest)}.new && "
              f"rm -rf {shlex.quote(dest)} && mv {shlex.quote(dest)}.new {shlex.quote(dest)} && "
              f"touch {shlex.quote(dest)} || rm -rf {shlex.quote(dest)}.new; "
              'exec "$@"')
    from .stores.base import Command
    return Command(["sh", "-c", script, "sh", *cmd.argv], cmd.env, cmd.cwd)


def has_copy(key, path) -> float:
    """When the safety copy was made (0 if there is none)."""
    if not path:
        return 0
    try:
        return os.path.getmtime(copy_path(key, path))
    except OSError:
        return 0


def roll_back(key, path) -> str:
    """Put the safety copy back in place of the game's folder. "" when done, else why not."""
    src = copy_path(key, path)
    if not os.path.isdir(src):
        return "No copy from before the update"
    broken = f"{path}.cornerplay-broken-{int(time.time())}"
    try:
        os.rename(path, broken)
        os.rename(src, path)
    except OSError as e:
        if not os.path.exists(path) and os.path.isdir(broken):
            os.rename(broken, path)  # put it back as it was
        return e.strerror or "Could not move the folders"
    shutil.rmtree(broken, ignore_errors=True)
    return ""


def prune(paths):
    """Drop safety copies older than a week (paths: the games folders' parents in use)."""
    cutoff = time.time() - KEEP_DAYS * 86400
    for root in {_root(p) for p in paths if p}:
        try:
            entries = os.listdir(root)
        except OSError:
            continue
        for e in entries:
            full = os.path.join(root, e)
            try:
                if os.path.getmtime(full) < cutoff:
                    shutil.rmtree(full, ignore_errors=True)
            except OSError:
                pass


# --- shared prefix files ------------------------------------------------------------------------
def _digest(path):
    h = hashlib.blake2b(digest_size=20)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.digest()


def share_prefix_files(prefixes_dir, min_size=64 * 1024) -> dict:
    """Blocking. {"files": shared, "saved": bytes (estimate from free space), "error"}."""
    from . import compress
    if not os.path.isdir(prefixes_dir) or not compress.available(prefixes_dir):
        return {"files": 0, "saved": 0, "error": "Not on a btrfs drive"}
    by_size = {}
    for pfx in os.listdir(prefixes_dir):
        win = os.path.join(prefixes_dir, pfx, "pfx", "drive_c", "windows")
        for root, _dirs, files in os.walk(win):
            for name in files:
                p = os.path.join(root, name)
                try:
                    st = os.lstat(p)
                except OSError:
                    continue
                if os.path.islink(p) or not os.path.isfile(p) or st.st_size < min_size:
                    continue
                by_size.setdefault(st.st_size, []).append(p)
    before = shutil.disk_usage(prefixes_dir).free
    shared = 0
    for paths in by_size.values():
        if len(paths) < 2:
            continue
        groups = {}
        for p in paths:
            try:
                groups.setdefault(_digest(p), []).append(p)
            except OSError:
                continue
        for same in groups.values():
            keep = same[0]
            for p in same[1:]:
                tmp = p + ".cornerplay-share"
                try:
                    # byte-for-byte equal already (same hash, same size); the clone takes the
                    # original's permissions and times, then replaces it in one rename
                    from .compress import low_priority
                    r = subprocess.run(low_priority(["cp", "--reflink=always", "--preserve=mode,timestamps", keep, tmp]),
                                       capture_output=True, timeout=60)
                    if r.returncode != 0:
                        if os.path.exists(tmp):
                            os.remove(tmp)
                        continue
                    os.replace(tmp, p)
                    shared += 1
                except (OSError, subprocess.TimeoutExpired):
                    if os.path.exists(tmp):
                        os.remove(tmp)
    subprocess.run(["sync", "-f", prefixes_dir], capture_output=True, timeout=120)
    return {"files": shared, "saved": max(0, shutil.disk_usage(prefixes_dir).free - before), "error": ""}
