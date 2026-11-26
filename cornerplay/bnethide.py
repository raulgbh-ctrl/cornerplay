"""Battle.net out of sight while its games start (Hyprland): launcherhide.py's Battle.net entry.

Blizzard's games only start through the Battle.net app (it hands them a sign-in token), but
nobody needs to look at it. Its windows go to a hidden workspace; when it needs you (the
sign-in window, an error) that window comes forward on the workspace you are on.
"""
from . import launcherhide as lh

SPEC = lh.LAUNCHERS["battlenet"]
CLASS = SPEC.classes[0]
PLACE = SPEC.place
NEEDS_YOU = SPEC.needs


def available() -> bool:
    return lh.available()


def windows() -> list:
    return lh.windows(SPEC)


def hidden(w) -> bool:
    return lh.hidden(SPEC, w)


def rule(on: bool) -> bool:
    return lh.rule(SPEC, on)


def park() -> int:
    return lh.park(SPEC)


def wants_you(w) -> bool:
    return lh.wants_you(SPEC, w)


def asking() -> dict:
    return lh.asking(SPEC)


def show(only=None) -> bool:
    return lh.show(SPEC, only)
