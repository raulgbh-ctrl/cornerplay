"""Runtimes that Steam installs for a game behind the scenes (its "first time setup") but that a
copy added by hand, or from GOG/Humble, never gets in its own fresh Proton prefix.

NVIDIA PhysX: older games (Mafia II, Mirror's Edge, Borderlands, Batman: Arkham ...) load
PhysXLoader.dll from Windows and stop at once with "PhysXLoader.dll was not found" without it.
When the game's .exe asks for it and neither the game folder nor the prefix has it, the PhysX
runtime goes into the prefix once (winetricks physx, through umu or Wine) before the game starts.
"""
import os

MARK = ".cornerplay-physx"  # in the prefix: installed (or tried) once, never again on every start


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


def needs_physx(exe: str, prefix: str) -> bool:
    if not exe.lower().endswith(".exe") or not _mentions(exe, b"PhysXLoader.dll"):
        return False
    if _has_file(os.path.dirname(exe), "PhysXLoader.dll"):
        return False  # the game brought its own
    if os.path.exists(os.path.join(prefix, MARK)):
        return False
    c = os.path.join(prefix, "drive_c")
    # NVIDIA's installer puts it in Program Files and adds that folder to the PATH; some copies sit in Windows
    places = [os.path.join(c, "Program Files (x86)", "NVIDIA Corporation", "PhysX", "Common"),
              os.path.join(c, "windows", "syswow64"), os.path.join(c, "windows", "system32")]
    return not any(_has_file(d, "PhysXLoader.dll") for d in places)


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
              'eval "$CP_SETUP"; touch "$CP_PREFIX/' + MARK + '"; exec "$@"')
    return ["env", f"CP_PREFIX={prefix}", f"CP_SETUP={shlex.join(setup)}", "sh", "-c", script, "sh", *argv]
