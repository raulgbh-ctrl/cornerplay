"""Battle.net out of sight while its games start (Hyprland).

Blizzard's games only start through the Battle.net app (it hands them a sign-in token), but
nobody needs to look at it. While Cornerplay starts a Battle.net game, its windows go to a
hidden workspace (special:cornerplay-battlenet); when it needs you (the sign-in window, an
error) that window comes forward on the workspace you are on. Lua-configured Hyprland (Ryoku)
gets a window rule, so a window never flashes; classic Hyprland has its windows moved as they
appear. Elsewhere Battle.net simply shows, as before.
"""
from . import hypr

CLASS = "steam_app_battlenet"
PLACE = "special:cornerplay-battlenet"
RULE = "cornerplay-battlenet-hidden"
# Windows that want you: Blizzard's sign-in, its error reporter, a question before an update.
NEEDS_YOU = ("battle.net login", "login", "sign in", "blizzard error", "error", "update required")


def available() -> bool:
    return hypr.running()


def windows() -> list:
    return [c for c in hypr.clients() if c.get("class") == CLASS]


def hidden(w) -> bool:
    return ((w.get("workspace") or {}).get("name") or "") == PLACE


def rule(on: bool) -> bool:
    """New Battle.net windows open hidden (Lua Hyprland); off replaces the rule with one that
    matches nothing. Classic Hyprland: False (park() does it instead)."""
    if not hypr.lua():
        return False
    match = {"class": f"^({CLASS})$"} if on else {"class": "^(cornerplay-matches-nothing)$"}
    return hypr.window_rule(RULE, match, workspace=PLACE + " silent")


def park() -> int:
    """Hide every Battle.net window not already hidden; how many moved."""
    n = 0
    for w in windows():
        if not hidden(w) and not wants_you(w):
            n += hypr.move_window(w["address"], PLACE)
    return n


def wants_you(w) -> bool:
    title = (w.get("title") or "").strip().lower()
    return any(t in title for t in NEEDS_YOU)


def asking() -> dict:
    """The Battle.net window that needs you ({} when none): its sign-in, an error."""
    return next((w for w in windows() if wants_you(w)), {})


def show(only=None) -> bool:
    """Bring Battle.net's windows (or just `only`) to the workspace you are on, focused."""
    here = hypr.workspace()
    if not here or here.startswith("special:"):
        here = "1"
    ws = [only] if only else [w for w in windows() if hidden(w)] or windows()
    for w in ws:
        hypr.move_window(w["address"], here, silent=False)
    if ws:
        hypr.focus_window(ws[0]["address"])
    return bool(ws)
