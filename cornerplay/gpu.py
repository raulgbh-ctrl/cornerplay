"""Which graphics card a game runs on, on PCs with two (a laptop's Intel or AMD chip and a faster
AMD or NVIDIA card; Intel Macs with a Radeon).

The screen is driven by one card (the "boot" one); games started on it run there unless told
otherwise. A game's Options > Graphics card (default: Settings, "Automatic") picks:
  auto        the fast card when there are two (the one that is not driving the screen, when the
              screen's is the built-in chip); nothing set on single-card PCs
  discrete    the dedicated card       integrated   the built-in chip
Mesa (Intel, AMD, the Vulkan device-select layer) takes DRI_PRIME=pci-<address>; NVIDIA's
proprietary driver takes its PRIME render-offload variables.
"""
import glob
import os

INTEL, AMD, NVIDIA = "0x8086", "0x1002", "0x10de"


def gpus() -> list:
    """[{"pci", "vendor", "driver", "boot", "integrated"}] for each graphics card (not the Touch
    Bar's or a USB display's, which have no PCI vendor)."""
    out = []
    for card in sorted(glob.glob("/sys/class/drm/card[0-9]*")):
        if "-" in os.path.basename(card):
            continue  # a connector (card1-eDP-1), not a card
        dev = os.path.join(card, "device")
        try:
            vendor = open(os.path.join(dev, "vendor")).read().strip()
        except OSError:
            continue
        pci = os.path.basename(os.path.realpath(dev))
        try:
            boot = open(os.path.join(dev, "boot_vga")).read().strip() == "1"
        except OSError:
            boot = False
        driver = os.path.basename(os.path.realpath(os.path.join(dev, "driver"))) if os.path.exists(os.path.join(dev, "driver")) else ""
        # Intel's are built in; an AMD chip counts as built in when it shares the CPU's memory
        # (an APU has no VRAM of its own worth the name: under 1 GB).
        integrated = vendor == INTEL
        if vendor == AMD:
            try:
                integrated = int(open(os.path.join(dev, "mem_info_vram_total")).read()) < 1 << 30
            except (OSError, ValueError):
                integrated = False
        if pci not in [g["pci"] for g in out]:
            out.append({"pci": pci, "vendor": vendor, "driver": driver, "boot": boot, "integrated": integrated})
    return out


def pick(choice: str, cards=None):
    """The card for a choice (auto / discrete / integrated), or None to leave it to the system."""
    cards = gpus() if cards is None else cards
    if len(cards) < 2:
        return None
    discrete = [c for c in cards if not c["integrated"]]
    integrated = [c for c in cards if c["integrated"]]
    if choice in ("auto", "discrete"):
        want = discrete[0] if discrete else None
    elif choice == "integrated":
        want = integrated[0] if integrated else None
    else:
        return None
    if not want or want["boot"]:
        return None  # already the one the screen uses: nothing to change
    return want


def env(choice: str, cards=None) -> dict:
    card = pick(choice or "auto", cards)
    if not card:
        return {}
    if card["vendor"] == NVIDIA and card["driver"] == "nvidia":
        return {"__NV_PRIME_RENDER_OFFLOAD": "1", "__GLX_VENDOR_LIBRARY_NAME": "nvidia",
                "__VK_LAYER_NV_optimus": "NVIDIA_only"}
    tag = "pci-" + card["pci"].replace(":", "_").replace(".", "_")  # pci-0000_03_00_0
    return {"DRI_PRIME": tag}


def label(card) -> str:
    return {INTEL: "Intel", AMD: "AMD", NVIDIA: "NVIDIA"}.get(card["vendor"], "GPU") + (
        " (built in)" if card["integrated"] else " (dedicated)")
