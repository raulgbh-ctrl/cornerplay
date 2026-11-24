"""Health check: is everything a game needs in place? One row per check, with a fix.

Each row: {"id", "name", "ok": True/False/None (None = not needed here), "detail", "fix": {...}}
fix kinds: {"kind": "command", "command": "sudo apt-get install ..."}  (shown, copied; never run as root)
           {"kind": "action", "action": "<app slot name>", "arg": "...", "label": "..."}
"""
import os

from . import host, pkgs, runner, storage
from .config import find_tool, settings
from .runner import StoreError


def _install(thing):
    """A fix that installs `thing` the way this distribution does it (pkgs.py), or none."""
    cmd = pkgs.install_command(thing)
    return {"kind": "command", "command": cmd} if cmd else {}


LAYER_DIRS = ("/usr/share/vulkan/implicit_layer.d", "/etc/vulkan/implicit_layer.d")


def mangohud_32bit_missing(layer_dirs=LAYER_DIRS) -> bool:
    """MangoHud is installed for 64-bit games but not for 32-bit ones (its x86 Vulkan layer)."""
    names = set()
    for d in layer_dirs:
        try:
            names.update(n.lower() for n in os.listdir(d))
        except OSError:
            pass
    return "mangohud.x86_64.json" in names and "mangohud.x86.json" not in names


# Controller makers whose pads need udev rules for raw access (Sony, Nintendo, 8BitDo, Valve,
# Microsoft over USB, Logitech, PowerA, Hori, Razer)
PAD_VENDORS = {"054C", "057E", "2DC8", "28DE", "045E", "046D", "20D6", "0F0D", "1532"}


def _controller_hidraws():
    """[(name, readable)] for the raw HID devices of plugged-in controllers."""
    out = []
    try:
        names = sorted(os.listdir("/sys/class/hidraw"))
    except OSError:
        return out
    for n in names:
        try:
            uevent = open(f"/sys/class/hidraw/{n}/device/uevent").read()
        except OSError:
            continue
        hid_id = next((l.split("=", 1)[1] for l in uevent.splitlines() if l.startswith("HID_ID=")), "")
        parts = hid_id.split(":")
        vendor = parts[1][-4:].upper() if len(parts) > 2 else ""
        if vendor in PAD_VENDORS:
            name = next((l.split("=", 1)[1] for l in uevent.splitlines() if l.startswith("HID_NAME=")), n)
            out.append((name, os.access(f"/dev/{n}", os.R_OK | os.W_OK)))
    return out


def checks(stores, gamepad_available=True):
    rows = []

    def add(cid, name, ok, detail, fix=None):
        rows.append({"id": cid, "name": name, "ok": ok, "detail": detail, "fix": fix or {}})

    # Graphics: Vulkan with a GPU that is on
    gpus = runner._vulkan_gpus()
    vk = runner.vulkan_problem()
    if gpus > 0:
        add("vulkan", "Graphics (Vulkan)", True, f"{gpus} GPU{'s' if gpus > 1 else ''} ready for Windows games")
    else:
        cmd = vk.split("sudo ", 1)[1] if "sudo " in vk else ""
        add("vulkan", "Graphics (Vulkan)", False, vk.split(". Install")[0] + ".",
            {"kind": "command", "command": "sudo " + cmd} if cmd else {})

    # Flatpak: Proton runs 32-bit code and needs Flatpak's 32-bit runtime and graphics drivers.
    # Installed from Flathub they come along by themselves; from a .flatpak file they may not.
    if host.IN_FLATPAK:
        missing = [ext for ext, probe in (("org.freedesktop.Platform.Compat.i386", "/app/lib/i386-linux-gnu/ld-linux.so.2"),
                                          ("org.freedesktop.Platform.GL32.default", "/app/lib/i386-linux-gnu/GL/default/lib"))
                   if not os.path.exists(probe)]
        add("flatpak32", "32-bit support (Flatpak)", not missing,
            "Installed" if not missing else "Missing: Windows games and Battle.net will not start",
            {} if not missing else {"kind": "command", "command": "flatpak install --user flathub "
                                    + " ".join(f"{e}//{host.FLATPAK_BASE}" for e in missing)})

    # Proton runner
    try:
        kind, path = runner.compat()
        add("umu", "Proton runner (umu-launcher)", True, f"{os.path.basename(path)} found" + ("" if kind == "umu" else " (plain Wine)"))
    except StoreError as e:
        # Packaged on Arch; elsewhere a portable copy downloads like the store tools.
        add("umu", "Proton runner (umu-launcher)", False, str(e),
            _install("umu-launcher") or {"kind": "action", "action": "fetchBackends", "label": "Download"})

    # Ubuntu 23.10+: Proton's container needs an AppArmor profile to start (userns.py)
    from . import userns
    if userns.restricted():
        ok = not userns.blocked()
        add("userns", "Proton game container (Ubuntu)", ok,
            "Allowed" if ok else "Blocked by Ubuntu: Windows games crash at start",
            {} if ok else {"kind": "action", "action": "allowUserns", "label": "Allow"})

    # Proton version
    versions = runner.proton_versions()
    add("proton", "Proton versions", bool(versions), f"{len(versions)} available" if versions else "None found",
        {} if versions else {"kind": "action", "action": "downloadGe", "label": "Get GE-Proton"})

    # MangoHud's 32-bit half: without it a 32-bit game (Mafia II, say) starts with no FPS counter
    # and the log fills with "libMangoHud_shim.so ... cannot be preloaded".
    if not host.IN_FLATPAK and mangohud_32bit_missing():
        wanted = bool(settings.get("mangohud") or settings.get("show_fps") or settings.get("perf_log"))
        add("mangohud32", "FPS counter in 32-bit games", False if wanted else None,
            "MangoHud's 32-bit part is missing, so older 32-bit games run without the counter", _install("mangohud32"))

    # Store tools
    for tool, store in (("legendary", "Epic"), ("gogdl", "GOG"), ("nile", "Amazon")):
        found = find_tool(tool)
        add(f"tool-{tool}", f"{store} tool ({tool})", bool(found), "Installed" if found else "Missing",
            {} if found else {"kind": "action", "action": "fetchBackends", "label": "Download"})

    # RetroArch, when there are ROM folders
    from .stores import retro
    if retro.rom_dirs():
        argv, folders = retro.retroarch()
        systems = sorted({sid for sid, _ in retro.scan()})
        no_core = [retro.SYSTEM_NAMES[s] for s in systems if argv and not retro.find_core(s, folders)]
        add("retroarch", "RetroArch (retro games)", bool(argv) and not no_core,
            ("Missing" if not argv else f"No core yet for: {', '.join(no_core)} (RetroArch > Online Updater > Core Downloader)"
             if no_core else f"Ready for {len(systems)} system{'s' if len(systems) != 1 else ''}"),
            {} if argv else _install("retroarch"))

    # Steam client
    steam = stores.get("steam")
    has_steam = bool(steam and steam.client())
    where = pkgs.note("steam") if pkgs.install_command("steam").startswith("sudo") else ""
    add("steam", "Steam", has_steam, "Installed" if has_steam else "Not installed" + (f" (install it {where})" if where else ""),
        {} if has_steam else _install("steam"))

    # Sign-ins
    for sid in ("steam", "epic", "gog", "amazon", "battlenet", "humble"):
        s = stores.get(sid)
        if not s:
            continue
        try:
            logged = s.logged_in()
        except Exception:
            logged = False
        add(f"signin-{sid}", f"{s.name} sign-in", logged if logged else None,
            "Connected" if logged else "Not connected (only needed if you use it)",
            {} if logged else {"kind": "action", "action": "loginBegin", "arg": sid, "label": "Sign in"})

    # Disk space where games go
    games_dir = str(settings.games_dir)
    probe = games_dir if os.path.isdir(games_dir) else os.path.expanduser("~")
    d = storage.drive(probe)
    if d:
        pct = d["free"] * 100 / max(1, d["total"])
        add("disk", "Space for games", pct >= 10,
            f"{storage.nice(d['free'])} free on {d['label']} ({pct:.0f}%)",
            {} if pct >= 10 else {"kind": "action", "action": "openStorage", "label": "Free up space"})

    # The drives game folders are on: Windows file systems and noexec break games (drives.py)
    from . import drives
    folders = [games_dir] + [x for x in settings.get("library_dirs") or [] if isinstance(x, str)]
    steam = stores.get("steam") if hasattr(stores, "get") else None
    try:
        folders += [str(x) for x in (steam.library_dirs() if steam else [])]
    except Exception:
        pass
    seen = set()
    for folder in folders:
        if not folder or not os.path.isdir(folder):
            continue
        j = drives.judge(folder)
        if not j or j["mount"] in seen:
            continue
        seen.add(j["mount"])
        add("drive:" + j["mount"], f"Game drive {j['label']}", j["ok"], j["detail"],
            {} if j["ok"] and not j["warn"] else {"kind": "action", "action": "openStorage", "label": "Storage"})

    # Open-file limit: esync (and Proton's fallbacks) open a file per waitable object; a low limit
    # makes some Windows games crash at start. Steam asks for 524288; systemd's default is that.
    try:
        import resource
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        ok = hard == resource.RLIM_INFINITY or hard >= 524288
        add("nofile", "Open-file limit (Proton)", ok,
            f"{hard} files" if ok else f"Only {hard} open files allowed: some Windows games crash at start",
            {} if ok else {"kind": "command", "command": "echo 'DefaultLimitNOFILE=1024:524288' | sudo tee /etc/systemd/user.conf.d/90-cornerplay-nofile.conf "
                                   "/etc/systemd/system.conf.d/90-cornerplay-nofile.conf"})
    except (ImportError, ValueError, OSError):
        pass
    # Memory maps: a few big games (Hogwarts Legacy, CS2, Star Citizen) crash below about a million.
    try:
        maps = int(open("/proc/sys/vm/max_map_count").read())
        add("maxmap", "Memory-map limit (big games)", maps >= 1048576, f"{maps}",
            {} if maps >= 1048576 else {"kind": "command", "command":
                "echo 'vm.max_map_count = 2147483642' | sudo tee /etc/sysctl.d/80-cornerplay-games.conf && sudo sysctl --system"})
    except (OSError, ValueError):
        pass
    # Split locks: newer Intel CPUs let the kernel slow down a program doing split-lock memory
    # access on purpose; some games do, and stutter. SteamOS turns the slowdown off.
    try:
        has_sld = "split_lock_detect" in open("/proc/cpuinfo").read()
        mitigate = open("/proc/sys/kernel/split_lock_mitigate").read().strip()
        if has_sld:
            add("splitlock", "Split-lock slowdown (Intel)", mitigate == "0",
                "Off, as on SteamOS" if mitigate == "0" else "On: games that do split locks are slowed on purpose",
                {} if mitigate == "0" else {"kind": "command", "command":
                    "echo 'kernel.split_lock_mitigate = 0' | sudo tee /etc/sysctl.d/80-cornerplay-splitlock.conf && sudo sysctl --system"})
    except OSError:
        pass
    # Controllers: Steam Input and controller-as-keyboard need /dev/uinput; a plugged-in controller's
    # raw device (hidraw) needs the udev rules from Steam's steam-devices.
    pads = _controller_hidraws()
    blocked = [n for n, ok in pads if not ok]
    uinput = os.access("/dev/uinput", os.W_OK)
    if pads or not uinput:
        ok = not blocked and uinput
        add("padperm", "Controller access", ok,
            (f"{len(pads)} controller(s) ready" if pads else "Ready") if ok
            else ("Not allowed to read: " + ", ".join(blocked)) if blocked else "Not allowed to use /dev/uinput",
            {} if ok else (_install("steam-devices") or {"kind": "command", "command":
                "sudo curl -fsSL -o /etc/udev/rules.d/60-steam-input.rules https://raw.githubusercontent.com/ValveSoftware/steam-devices/master/60-steam-input.rules && sudo udevadm control --reload && sudo udevadm trigger"}))

    # NTSYNC (Linux 6.14+): Windows games' synchronisation done in the kernel
    if os.path.exists("/dev/ntsync"):
        nt_ok = runner.ntsync_ok()
        add("ntsync", "NTSYNC (smoother Windows games)", nt_ok,
            "On for Proton games" if nt_ok else "The kernel has it, but /dev/ntsync is not open to you",
            {} if nt_ok else {"kind": "command", "command": "echo 'KERNEL==\"ntsync\", MODE=\"0666\"' | sudo tee /etc/udev/rules.d/70-ntsync.rules && sudo udevadm trigger"})

    # Save backups read where games keep saves from a YAML manifest
    if settings.get("save_backups"):
        try:
            import yaml  # noqa: F401
            add("yaml", "Save backups", True, "Ready (save locations for 20,000+ games)")
        except ImportError:
            add("yaml", "Save backups", False, "Needs PyYAML to read where games keep their saves",
                _install("yaml"))

    # Built-in sign-in window, controllers
    from PySide6.QtCore import QLibraryInfo
    from pathlib import Path
    qml = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.QmlImportsPath))
    web = (qml / "QtWebEngine" / "qmldir").is_file()
    add("webengine", "Built-in sign-in window", web if web else None,
        "Available" if web else "Missing: sign-ins open your browser instead",
        {} if web else _install("webengine"))
    from . import sdl
    add("sdl", "Controller support (SDL2)", True if gamepad_available else False,
        "Ready" if gamepad_available else
        ("Being set up (downloading a private SDL2)" if sdl.can_fetch() else "SDL2 missing: controllers do nothing"),
        {} if gamepad_available or sdl.can_fetch() else _install("sdl2"))
    return rows
