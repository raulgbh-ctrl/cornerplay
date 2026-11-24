"""Is this a good place for games? The drives under your game folders, checked.

Windows file systems (NTFS, exFAT, FAT) look fine and then break Proton games in odd ways: no
Linux permissions, no symbolic links, names that differ only in case clash, and Steam refuses
them outright. A drive mounted noexec cannot start a game at all. A hard disk or a slow SD
card works, with long loading. Health check lists each drive; Storage can test one's real
speed (written and read back past the cache, so the numbers are the drive's own).
"""
import os
import subprocess
import time

from . import host

# What a drive is like for games; also read by tools/toast_templates.py (translated).
DETAILS = {
    "windows": "A Windows file system: Proton games break here (no Linux permissions or links), "
               "and Steam will not use it. Format it as ext4 or btrfs for games.",
    "noexec": "Mounted noexec: no game can start from here. Remove noexec from its mount options (fstab).",
    "hdd": "A hard disk: games work, with long loading and some stutter in open worlds.",
    "sd": "An SD card: test its speed in Storage before installing big games.",
    "usb": "A USB drive: test its speed in Storage before installing big games.",
    "good": "Good for games",
    "slow": "Slow for games: long loading, stutter where games stream data",
    "fine": "Fine for smaller games; big open worlds load slowly",
    "fast": "Fast enough for any game",
}
WINDOWS_FS = {"ntfs", "ntfs3", "ntfs-3g", "fuseblk", "exfat", "vfat", "msdos", "fat", "fat32"}


def mount(path) -> dict:
    """{"target", "source", "fstype", "options": [..]} of the mount holding path, or {}."""
    path = str(path or "")
    while path and not os.path.exists(path):
        path = os.path.dirname(path)
    if not path or not host.which("findmnt"):
        return {}
    try:
        r = subprocess.run(host.argv(["findmnt", "-no", "TARGET,SOURCE,FSTYPE,OPTIONS", "-T", path]),
                           capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return {}
    parts = (r.stdout or "").split()
    if len(parts) < 4:
        return {}
    return {"target": parts[0], "source": parts[1], "fstype": parts[2].lower(), "options": parts[3].split(",")}


def disk(source: str) -> dict:
    """{"rotational", "removable", "transport"} of the disk a partition is on ({} if unknown)."""
    dev = (source or "").split("[")[0]  # btrfs shows /dev/nvme0n1p2[/@home]
    if not dev.startswith("/dev/") or not host.which("lsblk"):
        return {}
    try:
        r = subprocess.run(host.argv(["lsblk", "-ndo", "PKNAME", dev]), capture_output=True, text=True, timeout=5)
        parent = (r.stdout or "").strip() or os.path.basename(dev)
        r = subprocess.run(host.argv(["lsblk", "-ndo", "ROTA,RM,TRAN", "/dev/" + parent]), capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return {}
    f = (r.stdout or "").split()
    if len(f) < 2:
        return {}
    return {"rotational": f[0] == "1", "removable": f[1] == "1", "transport": f[2] if len(f) > 2 else ""}


def judge(path) -> dict:
    """{"ok": bool, "warn": bool, "label", "detail"} for one game folder's drive."""
    m = mount(path)
    if not m:
        return {}
    d = disk(m["source"])
    kind = ("SD card" if d.get("transport") == "mmc" or "mmcblk" in m["source"] else
            "USB drive" if d.get("transport") == "usb" else
            "hard disk" if d.get("rotational") else "SSD" if d else "")
    label = f"{m['target']} ({m['fstype']}{', ' + kind if kind else ''})"
    if m["fstype"] in WINDOWS_FS:
        return {"ok": False, "warn": False, "label": label, "mount": m["target"], "detail": DETAILS["windows"]}
    if "noexec" in m["options"]:
        return {"ok": False, "warn": False, "label": label, "mount": m["target"], "detail": DETAILS["noexec"]}
    if d.get("rotational"):
        return {"ok": True, "warn": True, "label": label, "mount": m["target"], "detail": DETAILS["hdd"]}
    if kind in ("SD card", "USB drive"):
        return {"ok": True, "warn": True, "label": label, "mount": m["target"],
                "detail": DETAILS["sd" if kind == "SD card" else "usb"]}
    return {"ok": True, "warn": False, "label": label, "mount": m["target"], "detail": DETAILS["good"]}


def speed(folder, mb: int = 256) -> dict:
    """Write mb MiB and read them back, past the page cache. {"write", "read"} in MB/s, or {"error"}."""
    path = os.path.join(folder, f".cornerplay-speedtest-{os.getpid()}")
    block = os.urandom(1 << 20)  # random: a compressing file system cannot shrink it
    try:
        t0 = time.monotonic()
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            for _ in range(mb):
                os.write(fd, block)
            os.fsync(fd)
        finally:
            os.close(fd)
        wrote = time.monotonic() - t0
        fd = os.open(path, os.O_RDONLY)
        try:
            os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)  # forget the cached copy: read the drive
            t0 = time.monotonic()
            while os.read(fd, 1 << 20):
                pass
            read = time.monotonic() - t0
        finally:
            os.close(fd)
    except OSError as e:
        return {"error": e.strerror or str(e)}
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
    size = mb * (1 << 20) / 1e6
    return {"write": round(size / max(wrote, 1e-6)), "read": round(size / max(read, 1e-6))}


def verdict(read_mbs: float) -> str:
    return DETAILS["slow" if read_mbs < 40 else "fine" if read_mbs < 90 else "fast"]
