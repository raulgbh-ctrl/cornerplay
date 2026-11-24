"""Games on the fast cores: CPUs whose cores are not all alike.

Intel's hybrid chips (12th gen and later) have performance cores and efficiency cores; a game on
an efficiency core stutters. AMD's X3D chips with two core groups (7900X3D, 7950X3D, 9950X3D)
have the big 3D V-Cache on one group only; games run best there. Settings > Games on the fast
cores (and each game's Options) pins a game to those cores (taskset at start, inherited by every
process it starts); everything else keeps the whole CPU. On CPUs whose cores are all alike
there is nothing to choose, and the setting is hidden.
"""
import glob
import os
import shutil

SYS = "/sys/devices"


def _read(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return ""


def parse_list(text: str) -> list:
    """'0-3,8,10-11' -> [0, 1, 2, 3, 8, 10, 11]."""
    out = []
    for part in (text or "").split(","):
        part = part.strip()
        if not part:
            continue
        a, _, b = part.partition("-")
        try:
            out.extend(range(int(a), int(b or a) + 1))
        except ValueError:
            return []
    return out


def to_list(cpus) -> str:
    """[0, 1, 2, 3, 8] -> '0-3,8'."""
    cpus = sorted(set(cpus))
    out, i = [], 0
    while i < len(cpus):
        j = i
        while j + 1 < len(cpus) and cpus[j + 1] == cpus[j] + 1:
            j += 1
        out.append(str(cpus[i]) if i == j else f"{cpus[i]}-{cpus[j]}")
        i = j + 1
    return ",".join(out)


def _size(text):
    """'96M' / '32768K' -> bytes."""
    t = (text or "").strip().upper()
    mult = {"K": 1 << 10, "M": 1 << 20, "G": 1 << 30}.get(t[-1:], 1)
    try:
        return int(t.rstrip("KMG")) * mult
    except ValueError:
        return 0


def fast(sys_root=SYS) -> dict:
    """{"cpus": [..], "kind": "intel-hybrid" | "amd-x3d", "label"} for the fast cores, or {}."""
    p = parse_list(_read(os.path.join(sys_root, "cpu_core/cpus")))
    e = parse_list(_read(os.path.join(sys_root, "cpu_atom/cpus")))
    if p and e:
        return {"cpus": p, "kind": "intel-hybrid", "label": f"{len(p)} performance threads"}
    # AMD: core groups by the L3 cache they share; the X3D group's is three times bigger.
    groups = {}
    for idx in glob.glob(os.path.join(sys_root, "system/cpu/cpu[0-9]*/cache/index3")):
        shared = _read(os.path.join(idx, "shared_cpu_list"))
        if shared:
            groups[shared] = _size(_read(os.path.join(idx, "size")))
    if len(groups) >= 2:
        sizes = sorted(set(groups.values()))
        if len(sizes) >= 2 and sizes[-1] >= 2 * sizes[0]:
            big = [g for g, s in groups.items() if s == sizes[-1]]
            cpus = sorted(c for g in big for c in parse_list(g))
            return {"cpus": cpus, "kind": "amd-x3d", "label": f"{len(cpus)} threads with the 3D V-Cache"}
    return {}


def available() -> bool:
    return bool(fast()) and bool(shutil.which("taskset"))


def argv() -> list:
    """The taskset prefix for a game, or [] when there is nothing to pick."""
    f = fast()
    if not f or not shutil.which("taskset"):
        return []
    return ["taskset", "-c", to_list(f["cpus"])]


def pin(pid: int, cpus=None) -> bool:
    """Pin a running process and all its threads (Battle.net's games, which Battle.net starts)."""
    cpus = cpus if cpus is not None else fast().get("cpus")
    if not cpus:
        return False
    ok = False
    for task in glob.glob(f"/proc/{int(pid)}/task/*"):
        try:
            os.sched_setaffinity(int(os.path.basename(task)), cpus)
            ok = True
        except (OSError, ValueError):
            pass
    return ok
