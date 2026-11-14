"""How to install a missing program on this PC, in its distribution's own words.

Every "X is not installed (...)" hint in the app comes from here, so an Ubuntu user is told
`sudo apt-get install steam-installer` and a Fedora user `sudo dnf install steam`, never
pacman. When a distribution has no package for it, the Flathub app (if there is one) is named.
"""
import os
import sys

from . import host

MANAGERS = ("pacman", "apt-get", "dnf", "zypper")

# thing -> {package manager: packages}. A manager left out has no package for it.
NAMES = {
    "steam": {"pacman": "steam", "apt-get": "steam-installer", "dnf": "steam", "zypper": "steam"},
    "umu-launcher": {"pacman": "umu-launcher"},
    "webengine": {"pacman": "qt6-webengine", "apt-get": "python3-pyside6.qtwebenginequick",
                  "dnf": "python3-pyside6", "zypper": "python3-pyside6"},
    "yaml": {"pacman": "python-yaml", "apt-get": "python3-yaml", "dnf": "python3-pyyaml", "zypper": "python3-PyYAML"},
    "sdl2": {"pacman": "sdl2-compat", "apt-get": "libsdl2-2.0-0", "dnf": "SDL2", "zypper": "libSDL2-2_0-0"},
    "mangohud": {"pacman": "mangohud lib32-mangohud", "apt-get": "mangohud", "dnf": "mangohud", "zypper": "mangohud"},
    "gamescope": {"pacman": "gamescope", "apt-get": "gamescope", "dnf": "gamescope", "zypper": "gamescope"},
    "retroarch": {"pacman": "retroarch", "apt-get": "retroarch", "dnf": "retroarch", "zypper": "retroarch"},
    "prismlauncher": {"pacman": "prismlauncher", "zypper": "prismlauncher"},
    # Vulkan drivers, 64- and 32-bit (Proton runs 32-bit games too)
    "vulkan-intel": {"pacman": "vulkan-intel lib32-vulkan-intel", "apt-get": "mesa-vulkan-drivers mesa-vulkan-drivers:i386",
                     "dnf": "mesa-vulkan-drivers mesa-vulkan-drivers.i686", "zypper": "libvulkan_intel libvulkan_intel-32bit"},
    "vulkan-amd": {"pacman": "vulkan-radeon lib32-vulkan-radeon", "apt-get": "mesa-vulkan-drivers mesa-vulkan-drivers:i386",
                   "dnf": "mesa-vulkan-drivers mesa-vulkan-drivers.i686", "zypper": "libvulkan_radeon libvulkan_radeon-32bit"},
    "vulkan-nvidia": {"pacman": "nvidia-utils lib32-nvidia-utils", "apt-get": "nvidia-driver nvidia-vulkan-icd",
                      "dnf": "akmod-nvidia xorg-x11-drv-nvidia-cuda-libs"},
}
# thing -> Flathub app, for when the distribution has no package
FLATHUB = {"steam": "com.valvesoftware.Steam", "retroarch": "org.libretro.RetroArch",
           "prismlauncher": "org.prismlauncher.PrismLauncher"}
# Where a distribution keeps a package outside its default repositories, said in a few words
NOTES = {("steam", "dnf"): "from RPM Fusion", ("vulkan-nvidia", "dnf"): "from RPM Fusion",
         ("steam", "apt-get"): "after switching on 32-bit packages: sudo dpkg --add-architecture i386 && sudo apt-get update"}


def _os_ids() -> set:
    ids = set()
    try:
        for line in open("/etc/os-release"):
            k, _, v = line.strip().partition("=")
            if k in ("ID", "ID_LIKE"):
                ids.update(v.strip('"').split())
    except OSError:
        pass
    return ids


def immutable() -> bool:
    """SteamOS, Bazzite, Silverblue, ...: system files are read-only, packages are not the way."""
    return os.path.exists("/run/ostree-booted") or bool(
        _os_ids() & {"steamos", "bazzite", "silverblue", "kinoite", "aurora", "bluefin", "chimeraos"})


def manager() -> str:
    """This PC's package manager ("" on read-only systems or when it is none of the four)."""
    if immutable():
        return ""
    return next((m for m in MANAGERS if host.which(m)), "")


def _in_venv() -> bool:
    return sys.prefix != getattr(sys, "base_prefix", sys.prefix)


def install_command(thing: str) -> str:
    """A command that installs `thing` here, or "" when there is none to give."""
    # Cornerplay's own private Python (install.sh's venv) takes Python parts from pip, not the system.
    if _in_venv() and thing in ("webengine", "yaml"):
        if thing == "yaml":
            return f'"{sys.executable}" -m pip install pyyaml'
        import PySide6
        v = PySide6.__version__
        major, minor = (int(x) for x in v.split(".")[:2])
        pkg = f'"PySide6-WebEngine=={v}.*"' if (major, minor) >= (6, 12) else f"PySide6-Addons=={v}"
        return f'"{sys.executable}" -m pip install {pkg}'
    pm = manager()
    if thing == "vulkan-nvidia" and pm == "apt-get" and "ubuntu" in _os_ids():
        return "sudo ubuntu-drivers install"
    pkgs = NAMES.get(thing, {}).get(pm)
    if thing == "steam" and pm == "apt-get" and "ubuntu" not in _os_ids():
        pkgs = ""  # Debian keeps it in "contrib", off by default: Valve's steam.deb (see hint) or Flathub
    if pkgs:
        return {"pacman": f"sudo pacman -S --needed {pkgs}", "apt-get": f"sudo apt-get install {pkgs}",
                "dnf": f"sudo dnf install {pkgs}", "zypper": f"sudo zypper install {pkgs}"}[pm]
    if thing in FLATHUB and host.which("flatpak"):
        return f"flatpak install flathub {FLATHUB[thing]}"
    return ""


def note(thing: str) -> str:
    """A few words on where the package lives, when it is not in the default repositories."""
    return NOTES.get((thing, manager()), "")


def hint(thing: str) -> str:
    """Short advice for a message: "sudo apt-get install mangohud", "flatpak install flathub ..."."""
    cmd = install_command(thing)
    where = note(thing)
    if cmd and where and cmd.startswith("sudo"):
        cmd = f"{cmd}, {where}"
    if cmd and thing in FLATHUB and not cmd.startswith("flatpak"):
        cmd += ", or from Flathub"
    if not cmd:
        cmd = "from Flathub" if thing in FLATHUB else "with your package manager"
        if thing == "steam" and manager() == "apt-get":
            cmd = "Valve's steam.deb from store.steampowered.com/about, or from Flathub"
        if thing == "umu-launcher":
            cmd = "the Health check's Download button gets a portable copy"
    return cmd
