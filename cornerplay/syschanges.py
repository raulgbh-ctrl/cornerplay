"""A game that worked last week and not today: what changed on the system since?

A system update can break a game (a new Mesa, kernel or graphics driver). From the package
manager's own log (pacman, apt/dpkg) this lists the updates since the game last ran that
matter to games, the btrfs snapshot taken just before them (snapper with snap-pac, the CachyOS,
openSUSE and Fedora way; Timeshift with timeshift-autosnap), and what can be done:
  - undo one package: its previous version from pacman's cache (asks for the password);
  - go back to the snapshot: pick it in the boot menu (Limine / GRUB list snapshots), or
    restore it in Btrfs Assistant / Timeshift.
Nothing is changed without a button press, and a whole-system rollback is left to the tools
made for it (snapper rollback silently does nothing on layouts that mount @ by name).
"""
import glob
import os
import re
import shutil
import subprocess

PACMAN_LOG = "/var/log/pacman.log"
DPKG_LOG = "/var/log/dpkg.log"
PKG_CACHE = "/var/cache/pacman/pkg"
# Packages that change how games run.
GAMING = re.compile(r"^(lib32-)?(mesa|vulkan-[\w-]+|nvidia[\w-]*|amdvlk|libdrm|llvm-libs|spirv-tools|"
                    r"linux(-[\w]+)?|linux-firmware[\w-]*|proton[\w-]*|wine[\w-]*|dxvk[\w-]*|vkd3d[\w-]*|"
                    r"gamescope|gamemode|mangohud|umu-launcher|steam|pipewire[\w-]*|wireplumber|sdl2[\w-]*|"
                    r"sdl3|xorg-xwayland|hyprland|kwin|mutter|libva[\w-]*|"
                    r"libgl1-mesa-dri|mesa-vulkan-drivers|libvulkan1|xserver-xorg-core)$")
PAC_LINE = re.compile(r"^\[(\S+)\] \[ALPM\] (upgraded|downgraded|installed|removed) (\S+) \(([^)]*)\)")
DPKG_LINE = re.compile(r"^(\S+ \S+) (upgrade|install|remove) (\S+?)(?::\w+)? (\S+) (\S+)")


def _ts(text):
    """pacman's "2026-11-24T18:25:14+0200", dpkg's and snapper's "2026-11-24 18:25:14" -> unix time."""
    from datetime import datetime
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M%z", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text.strip(), fmt).timestamp()  # no zone: local time
        except ValueError:
            continue
    return 0.0


def changes_since(since: float, pacman_log=PACMAN_LOG, dpkg_log=DPKG_LOG) -> list:
    """[{"pkg", "old", "new", "when", "action"}] of gaming packages changed after `since`,
    the last change per package, oldest first."""
    out = {}
    try:
        with open(pacman_log, errors="replace") as f:
            for line in f:
                m = PAC_LINE.match(line)
                if not m:
                    continue
                when, action, pkg, vers = _ts(m.group(1)), m.group(2), m.group(3), m.group(4)
                if when <= since or not GAMING.match(pkg):
                    continue
                old, _, new = vers.partition(" -> ")
                if action in ("installed", "removed"):
                    old, new = ("", vers) if action == "installed" else (vers, "")
                prev = out.get(pkg)
                out[pkg] = {"pkg": pkg, "old": prev["old"] if prev else old, "new": new, "when": when, "action": action}
    except OSError:
        pass
    try:
        with open(dpkg_log, errors="replace") as f:
            for line in f:
                m = DPKG_LINE.match(line)
                if not m:
                    continue
                when, action, pkg, old, new = _ts(m.group(1)), m.group(2), m.group(3), m.group(4), m.group(5)
                if when <= since or not GAMING.match(pkg):
                    continue
                prev = out.get(pkg)
                out[pkg] = {"pkg": pkg, "old": prev["old"] if prev else ("" if old == "<none>" else old),
                            "new": "" if new == "<none>" else new, "when": when, "action": action}
    except OSError:
        pass
    return sorted(out.values(), key=lambda c: c["when"])


def cached_package(pkg: str, version: str, cache=None) -> str:
    """pacman's cached file of that version ("" when it is not kept)."""
    cache = cache or PKG_CACHE
    if not version:
        return ""
    for path in sorted(glob.glob(os.path.join(cache, f"{pkg}-{version}-*.pkg.tar.*"))):
        if not path.endswith(".sig"):
            return path
    return ""


def downgrade_argv(pkgs: list) -> list:
    """pkexec pacman -U of the cached previous versions (several at once: lib32 pairs match)."""
    files = [cached_package(c["pkg"], c["old"]) for c in pkgs]
    files = [f for f in files if f]
    return ["pkexec", "pacman", "-U", "--noconfirm", *files] if files else []


def snapshots() -> list:
    """[{"number", "when", "what", "kind"}] from snapper's root config ([] without snapper or access)."""
    if not shutil.which("snapper"):
        return []
    try:
        r = subprocess.run(["snapper", "--csvout", "-c", "root", "list", "--columns", "number,date,description,type"],
                           capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return []
    out = []
    for line in (r.stdout or "").splitlines()[1:]:
        parts = line.split(",")
        if len(parts) < 4 or not parts[0].isdigit() or parts[0] == "0":
            continue
        out.append({"number": int(parts[0]), "when": _ts(parts[1]), "what": ",".join(parts[2:-1]), "kind": parts[-1]})
    return out


def snapshot_before(when: float, snaps=None) -> dict:
    """The newest snapshot taken before `when` ({} when there is none)."""
    snaps = snapshots() if snaps is None else snaps
    before = [s for s in snaps if s["when"] and s["when"] <= when + 2 and s["kind"] in ("pre", "single")]
    return max(before, key=lambda s: s["when"]) if before else {}


def protection() -> dict:
    """{"ok", "how"}: are snapshots taken before system updates here?"""
    if shutil.which("snapper"):
        if os.path.exists("/usr/share/libalpm/hooks/05-snap-pac-pre.hook") or shutil.which("snap-pac"):
            return {"ok": True, "how": "snapper + snap-pac"}
        if os.path.exists("/usr/lib/zypp/plugins/commit/snapper-zypp-plugin") or os.path.isdir("/usr/lib/zypp/plugins/commit"):
            return {"ok": True, "how": "snapper (zypper)"}
        if os.path.exists("/usr/lib64/libdnf5/plugins/snapper.so") or glob.glob("/usr/lib/python3*/site-packages/dnf-plugins/snapper.py"):
            return {"ok": True, "how": "snapper (dnf)"}
        return {"ok": False, "how": "snapper", "need": "snap-pac"}
    if shutil.which("timeshift"):
        if shutil.which("timeshift-autosnap") or os.path.exists("/etc/timeshift-autosnap.conf"):
            return {"ok": True, "how": "Timeshift + timeshift-autosnap"}
        return {"ok": False, "how": "timeshift", "need": "timeshift-autosnap"}
    return {"ok": False, "how": "", "need": ""}


def boot_menu_lists_snapshots() -> bool:
    return bool(shutil.which("limine-snapper-sync") or shutil.which("grub-btrfsd")
                or os.path.exists("/etc/grub.d/41_snapshots-btrfs"))


def groups(changes: list) -> list:
    """Changes that came together (same versions, same minute: Mesa with its lib32 and Vulkan
    parts) as one: [{"name", "pkgs": [..], "old", "new", "when", "canUndo"}], most game-relevant first."""
    out = {}
    for c in changes:
        k = (c["old"], c["new"], int(c["when"] // 120))
        out.setdefault(k, []).append(c)
    rank = re.compile(r"mesa|vulkan|nvidia|amdvlk|^linux|proton|wine|dxvk|vkd3d")
    res = []
    for (old, new, _), cs in out.items():
        name = min((c["pkg"] for c in cs), key=lambda n: (n.startswith("lib32-"), len(n)))
        res.append({"name": name, "pkgs": [c["pkg"] for c in cs], "old": old, "new": new,
                    "when": max(c["when"] for c in cs), "action": cs[0]["action"],
                    "canUndo": bool(old) and all(cached_package(c["pkg"], c["old"]) for c in cs)})
    return sorted(res, key=lambda g: (not rank.search(g["name"]), -g["when"]))
