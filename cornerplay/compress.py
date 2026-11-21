"""Compress a game's files on btrfs (zstd): often 20-40% less disk, nothing to change in the game.

btrfs compresses files transparently: the game reads them as usual. A folder mounted with
compress=... already compresses what is written from then on (CachyOS and Fedora do this by
default, at a light level); this rewrites what is there at zstd's default level, catching files
written before and anything the light level skipped, and marks the folder (chattr +c) so later
updates are compressed too. It needs no root: btrfs lets you rewrite files you own.

The saving is read from the drive's free space before and after (an exact count needs root), so
it is a close estimate. With btrfs snapshots of the folder, rewriting makes the files new copies
next to the snapshot's: it then uses more space until those snapshots go.
"""
import os
import shutil
import subprocess

from . import host


def low_priority(argv: list) -> list:
    """Run at idle disk priority and lower CPU priority (Settings: on), so a big install, update
    or compression never makes the game you are playing stutter. ionice and nice exec the
    program, so it keeps the same process id (pausing and cancelling still work)."""
    from .config import settings
    if not settings.get("jobs_low_priority", True):
        return list(argv)
    out = list(argv)
    if shutil.which("nice"):
        out = ["nice", "-n", "10"] + out
    if shutil.which("ionice"):
        out = ["ionice", "-c", "3"] + out
    return out


def filesystem(path) -> dict:
    """{"btrfs": bool, "auto": "zstd:1" or ""}: the drive under `path`, and whether it already
    compresses new files (its mount option)."""
    path = str(path or "")
    while path and not os.path.exists(path):
        path = os.path.dirname(path)
    if not path or not host.which("findmnt"):
        return {"btrfs": False, "auto": ""}
    try:
        r = subprocess.run(host.argv(["findmnt", "-no", "FSTYPE,OPTIONS", "-T", path]),
                           capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return {"btrfs": False, "auto": ""}
    fstype, _, options = (r.stdout or "").strip().partition(" ")
    auto = next((o.split("=", 1)[1] for o in options.split(",") if o.startswith(("compress=", "compress-force="))), "")
    return {"btrfs": fstype == "btrfs", "auto": auto}


def available(path) -> bool:
    return bool(path) and os.path.isdir(path) and bool(host.which("btrfs")) and filesystem(path)["btrfs"]


def compress(path) -> dict:
    """Blocking (minutes for a big game). {"ok", "saved": bytes (estimate), "error"}."""
    if not available(path):
        return {"ok": False, "saved": 0, "error": "Not on a btrfs drive"}
    before = shutil.disk_usage(path).free
    try:
        # +c on the folder: new files there (updates) are compressed too
        subprocess.run(host.argv(["chattr", "-R", "+c", path]), capture_output=True, timeout=600)
        r = subprocess.run(host.argv(low_priority(["btrfs", "filesystem", "defragment", "-r", "-czstd", path])),
                           capture_output=True, text=True, timeout=6 * 3600)
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"ok": False, "saved": 0, "error": type(e).__name__}
    subprocess.run(["sync", "-f", path], capture_output=True, timeout=120) if shutil.which("sync") else None
    saved = max(0, shutil.disk_usage(path).free - before)
    if r.returncode != 0:
        err = (r.stderr or r.stdout or "").strip().splitlines()
        return {"ok": False, "saved": saved, "error": (err[-1] if err else "btrfs failed")[-160:]}
    return {"ok": True, "saved": saved, "error": ""}
