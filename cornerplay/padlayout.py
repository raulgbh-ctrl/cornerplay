"""Controller layouts for games, like Steam Input's simplest ones: swap A and B, the Nintendo
layout, southpaw sticks, bumpers and triggers swapped.

SDL reads extra controller mappings from SDL_GAMECONTROLLERCONFIG. Cornerplay takes the
mapping SDL already uses for each connected controller, swaps the parts the layout names,
and hands the result to the game. Games that read controllers through SDL follow it: most
native Linux games and, through Wine's SDL backend, most Proton games. Steam games use
Steam Input instead (set their layout in Steam).
"""

LAYOUTS = {
    "": [],
    "swap_ab": [("a", "b")],
    "nintendo": [("a", "b"), ("x", "y")],
    "southpaw": [("leftx", "rightx"), ("lefty", "righty"), ("leftstick", "rightstick")],
    "shoulders": [("leftshoulder", "lefttrigger"), ("rightshoulder", "righttrigger")],
}
NAMES = {"": "Default", "swap_ab": "Swap A and B", "nintendo": "Nintendo (A/B and X/Y swapped)",
         "southpaw": "Southpaw (sticks swapped)", "shoulders": "Bumpers and triggers swapped"}

# Set by Cornerplay at start-up: the connected controllers' SDL mapping strings.
current_mappings = lambda: []  # noqa: E731


def remap(mapping: str, layout: str) -> str:
    """One SDL mapping string ("guid,name,a:b0,b:b1,...") with the layout's pairs swapped."""
    pairs = LAYOUTS.get(layout or "", [])
    parts = mapping.strip().split(",")
    if not pairs or len(parts) < 3:
        return mapping.strip()
    fields = {}
    for i, p in enumerate(parts[2:], 2):
        k, sep, v = p.partition(":")
        if sep:
            fields[k] = (i, v)
    for one, two in pairs:
        if one in fields and two in fields:
            (i, v1), (j, v2) = fields[one], fields[two]
            parts[i], parts[j] = f"{one}:{v2}", f"{two}:{v1}"
    return ",".join(parts)


def env(layout: str) -> dict:
    """SDL_GAMECONTROLLERCONFIG for the connected controllers in this layout, or {}."""
    if not LAYOUTS.get(layout or ""):
        return {}
    try:
        maps = [m for m in current_mappings() if m and m.count(",") >= 2]
    except Exception:
        maps = []
    if not maps:
        return {}
    return {"SDL_GAMECONTROLLERCONFIG": "\n".join(remap(m, layout) for m in maps)}
