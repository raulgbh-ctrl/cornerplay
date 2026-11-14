"""Why did that game close straight away? Read its log and say it in plain words.

explain(log_text) -> {"cause", "fix", "detail", "base", "needs", "line"} or {} when nothing
recognisable is in the log. fix: "repair" | "vcrun" | "dotnet" | "proton" | "vulkan" | "native" | "storage"
| "userns" | "steam" | "winetricks:<verb>" | "". "line" is the log line that gave it away;
"base" is the detail without the "It needs X." part (for translating), "needs" that X.
"""
import re

# (pattern, cause, fix, detail) — first match wins, most specific first.
RULES = [
    # Ubuntu 23.10+ refuses Proton's container (pressure-vessel's bwrap) a user namespace.
    (r"bwrap: (?:setting up uid map|Creating new namespace failed|No permissions to create (?:a )?new namespace)"
     r"|pressure-vessel.*(?:userns|user namespace)", "Ubuntu blocked Proton's container", "userns",
     "Ubuntu stops the container Proton runs games in. Allowing it once fixes every game."),
    (r"error while loading shared libraries: (\S+?):", "A Linux library is missing", "native",
     "This Linux version needs a library your system does not have. Install it, or use the game's "
     "Windows version instead (Options > Version), which runs through Proton."),
    (r"No space left on device", "The drive is full", "storage",
     "The game could not write its files. Free some space and try again."),
    (r"VK_ERROR_INITIALIZATION_FAILED|vkEnumeratePhysicalDevices|No Vulkan|DXVK: No adapters|"
     r"Failed to create Vulkan instance|vulkan.*not supported", "No working Vulkan graphics", "vulkan",
     "Proton draws Windows games with Vulkan, and it found no GPU to use."),
    (r"(?i)easyanticheat|EasyAntiCheat_EOS|battleye|BEService", "Anti-cheat blocked it", "",
     "This game's anti-cheat does not allow Linux (the publisher has to turn that on). "
     "Single-player modes sometimes still work; check its ProtonDB page."),
    (r"(?i)(PhysXLoader|PhysXCore|PhysXCooking|NxCooking|PhysXUpdateLoader)\.dll", "Missing NVIDIA PhysX", "winetricks:physx",
     "Older games (Mafia II, Borderlands, Mirror's Edge) need the PhysX runtime in their Proton prefix."),
    (r"(?i)(d3dx9_\d+|d3dx10_\d+|d3dx11_\d+)\.dll", "Missing DirectX 9-11 libraries", "winetricks:d3dx9",
     "The game uses the old DirectX helper libraries (d3dx), which are not part of Proton."),
    (r"(?i)(xactengine\d_\d|xaudio2_[0-7]|x3daudio1_\d)\.dll", "Missing DirectX audio (XACT)", "winetricks:xact",
     "The game plays its sound through the old DirectX audio libraries."),
    (r"(?i)SteamAPI_Init\(\) failed|Steam must be running|\[S_API FAIL\] SteamAPI_Init", "The game wants Steam running", "steam",
     "This game checks for Steam when it starts. Start Steam, sign in, then play again."),
    (r"VK_ERROR_DEVICE_LOST|DXGI_ERROR_DEVICE_(?:REMOVED|HUNG|RESET)", "The graphics driver stopped", "proton",
     "The GPU driver gave up while drawing. Turning off the FPS counter and gamescope for this game, "
     "updating the graphics driver, or another Proton version usually helps."),
    (r"(?i)out of memory|Cannot allocate memory|std::bad_alloc|OOM-killer", "The PC ran out of memory", "",
     "Close other programs (browsers above all) and try again; a bigger swap file helps on PCs with 8 GB or less."),
    (r"Exec format error", "Not a program this PC can run", "native",
     "The game's file is for another kind of computer. Use its Windows version instead (Options > Version)."),
    (r"(?i)(MSVCP1\d0|VCRUNTIME1\d0|vcruntime140_1|msvcr1\d0)\.dll", "Missing Visual C++ runtime", "vcrun",
     "The game needs Microsoft's Visual C++ runtime in its Proton prefix."),
    (r"(?i)mscoree\.dll|\.NET Framework|clr\.dll|mono.*not (found|installed)", "Missing .NET Framework", "dotnet",
     "The game (or its launcher) needs .NET in its Proton prefix."),
    (r"(?i)d3dcompiler_4[37]\.dll.*not found|Library d3dcompiler", "Missing DirectX shader compiler", "winetricks:d3dcompiler_47",
     "The game needs d3dcompiler from DirectX in its prefix."),
    (r"(?i)could not find .*\.exe|no such file or directory.*\.exe|File not found|Executable not found",
     "The game's files are missing or broken", "repair", "Checking and repairing the files usually fixes it."),
    (r"(?i)wine: Unhandled page fault|Unhandled exception: page fault|wine: Unhandled (illegal|privileged)",
     "The game crashed inside Proton", "proton",
     "Another Proton version often helps (a game's Options > Proton version); ProtonDB lists what works."),
    (r"(?i)err:module:import_dll Library (\S+\.dll)", "A Windows library is missing", "proton",
     "The log names a .dll the game needs; another Proton version, or ProtonDB's tips, usually help."),
]


# When a game closes within seconds and its log names no cause.
FALLBACK = {"cause": "It closed right away", "fix": "proton",
            "detail": "Nothing in its log says why. Another Proton version, or Repair files, often helps."}

# The button for each "winetricks:<verb>" fix.
WINETRICKS = {"physx": "Install PhysX", "d3dx9": "Install DirectX 9-11", "xact": "Install DirectX audio",
              "d3dcompiler_47": "Install the shader compiler", "vcrun2022": "Install Visual C++", "dotnet48": "Install .NET"}


def _line(text, m):
    """The whole log line the match is on, shortened."""
    start = text.rfind("\n", 0, m.start()) + 1
    end = text.find("\n", m.end())
    line = text[start:end if end != -1 else len(text)].strip()
    return line if len(line) <= 220 else line[:217] + "..."


def explain(text):
    if not text:
        return {}
    for pattern, cause, fix, detail in RULES:
        m = re.search(pattern, text)
        if m:
            needs = m.group(1) if fix in ("proton", "native") and m.groups() and m.group(1) else ""
            out = {"cause": cause, "fix": fix, "base": detail, "needs": needs,
                   "detail": (f"It needs {needs}. " if needs else "") + detail, "line": _line(text, m)}
            if fix.startswith("winetricks:"):
                out["fixLabel"] = WINETRICKS.get(fix.split(":", 1)[1], "Install it")
            return out
    return {}
