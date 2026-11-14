"""Runtimes that Steam installs for a game behind the scenes (its "first time setup") but that a
copy added by hand, or from GOG/Humble, never gets in its own fresh Proton prefix.

NVIDIA PhysX: older games (Mafia II, Mirror's Edge, Borderlands, Batman: Arkham ...) load
PhysXLoader.dll from Windows and stop at once with "PhysXLoader.dll was not found" without it.
When the game's .exe asks for it and neither the game folder nor the prefix has it, the PhysX
runtime goes into the prefix (winetricks physx, through umu or Wine) before the game starts,
until it is there.
"""
import os



def _mentions(path, needle: bytes) -> bool:
    """The file contains this ASCII name (any case): DLL imports are stored as plain names."""
    needle = needle.lower()
    tail = b""
    try:
        with open(path, "rb") as f:
            while True:
                chunk = f.read(1 << 20)
                if not chunk:
                    return False
                block = (tail + chunk).lower()
                if needle in block:
                    return True
                tail = block[-len(needle):]
    except OSError:
        return False


def _has_file(folder, name) -> bool:
    try:
        return any(n.lower() == name.lower() for n in os.listdir(folder))
    except OSError:
        return False


def _physx_places(prefix):
    c = os.path.join(prefix, "drive_c")
    # NVIDIA's installer puts it in Program Files and adds that folder to the PATH; some copies sit in Windows
    return [os.path.join(c, "Program Files (x86)", "NVIDIA Corporation", "PhysX", "Common"),
            os.path.join(c, "windows", "syswow64"), os.path.join(c, "windows", "system32")]


def asks_for_physx(exe: str) -> bool:
    """The game loads PhysXLoader.dll: from its .exe, or from one of its own DLLs beside it
    (Mafia II loads it through its APEX/PhysX DLLs)."""
    if _mentions(exe, b"PhysXLoader.dll"):
        return True
    folder = os.path.dirname(exe)
    try:
        dlls = [n for n in os.listdir(folder) if n.lower().endswith(".dll")][:200]
    except OSError:
        return False
    for n in dlls:
        p = os.path.join(folder, n)
        try:
            if os.path.getsize(p) > 64 << 20:
                continue
        except OSError:
            continue
        if n.lower() != "physxloader.dll" and _mentions(p, b"PhysXLoader.dll"):
            return True
    return False


def needs_physx(exe: str, prefix: str) -> bool:
    """Installed until it is really there: a failed try (no internet then) is tried again next time."""
    if not exe.lower().endswith(".exe"):
        return False
    if _has_file(os.path.dirname(exe), "PhysXLoader.dll"):
        return False  # the game brought its own
    if any(_has_file(d, "PhysXLoader.dll") for d in _physx_places(prefix)):
        return False
    return asks_for_physx(exe)


def wrap(argv: list, exe: str, prefix: str) -> list:
    """argv, preceded by the PhysX install when this game needs it and the prefix lacks it."""
    if not needs_physx(exe, prefix):
        return argv
    from .runner import compat
    kind, tool = compat()
    if kind == "umu":
        setup = [tool, "winetricks", "-q", "physx"]
    else:
        import shutil
        wt = shutil.which("winetricks")
        if not wt:
            return argv  # plain Wine and no winetricks: nothing to install it with
        setup = [wt, "-q", "physx"]
    import shlex
    script = ('echo "Cornerplay: installing NVIDIA PhysX into this game\'s prefix (once)"; '
              'eval "$CP_SETUP"; exec "$@"')
    return ["env", f"CP_SETUP={shlex.join(setup)}", "sh", "-c", script, "sh", *argv]
