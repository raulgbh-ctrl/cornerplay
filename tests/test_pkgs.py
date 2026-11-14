"""Install hints name each distribution's own packages, never pacman's on Debian or Fedora."""
import pytest

from cornerplay import pkgs


@pytest.fixture
def distro(monkeypatch):
    def use(pm, ids=("linux",), flatpak=False, venv=False):
        have = {pm, "flatpak"} if flatpak else {pm}
        monkeypatch.setattr(pkgs.host, "which", lambda n: f"/usr/bin/{n}" if n in have else None)
        monkeypatch.setattr(pkgs, "_os_ids", lambda: set(ids))
        monkeypatch.setattr(pkgs, "_in_venv", lambda: venv)
        monkeypatch.setattr(pkgs.os.path, "exists", lambda p: False)
    return use


def test_each_manager_gets_its_own_names(distro):
    distro("apt-get", ("ubuntu", "debian"))
    assert pkgs.install_command("steam") == "sudo apt-get install steam-installer"
    assert "i386" in pkgs.hint("steam")
    distro("apt-get", ("debian",))
    assert pkgs.install_command("steam") == ""      # contrib is off by default on Debian
    assert "steam.deb" in pkgs.hint("steam")
    assert pkgs.install_command("vulkan-amd") == "sudo apt-get install mesa-vulkan-drivers mesa-vulkan-drivers:i386"
    distro("dnf", ("fedora",))
    assert pkgs.install_command("vulkan-intel") == "sudo dnf install mesa-vulkan-drivers mesa-vulkan-drivers.i686"
    assert "RPM Fusion" in pkgs.hint("steam")
    distro("zypper", ("opensuse-tumbleweed",))
    assert pkgs.install_command("sdl2") == "sudo zypper install libSDL2-2_0-0"
    distro("pacman", ("arch",))
    assert pkgs.install_command("mangohud") == "sudo pacman -S --needed mangohud lib32-mangohud"


def test_no_pacman_outside_arch(distro):
    for pm in ("apt-get", "dnf", "zypper"):
        distro(pm, flatpak=True)
        for thing in list(pkgs.NAMES) + ["umu-launcher"]:
            assert "pacman" not in pkgs.hint(thing)


def test_unpackaged_falls_back_to_flathub_or_words(distro):
    distro("apt-get", ("debian",), flatpak=True)
    assert pkgs.install_command("prismlauncher") == "flatpak install flathub org.prismlauncher.PrismLauncher"
    distro("dnf", ("fedora",))
    assert pkgs.install_command("umu-launcher") == ""
    assert pkgs.hint("umu-launcher")


def test_ubuntu_nvidia_and_immutable(distro, monkeypatch):
    distro("apt-get", ("ubuntu", "debian"))
    assert pkgs.install_command("vulkan-nvidia") == "sudo ubuntu-drivers install"
    distro("pacman", ("steamos", "arch"))
    assert pkgs.manager() == ""


def test_private_python_uses_pip(distro):
    distro("apt-get", venv=True)
    assert "-m pip install" in pkgs.install_command("webengine")
    assert pkgs.install_command("yaml").endswith("-m pip install pyyaml")
