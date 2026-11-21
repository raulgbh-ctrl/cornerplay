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
