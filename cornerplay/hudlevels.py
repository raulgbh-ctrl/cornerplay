"""Performance overlay levels you switch while playing (quick access), like the Steam Deck's.

With Settings > Games > "Performance overlay levels" on, the games Cornerplay starts run with
MangoHud reading Cornerplay's own config file; quick access rewrites that file and MangoHud
picks it up while the game runs: off, FPS only, basic (FPS, frame time, CPU/GPU load and
temperatures, memory) or full. A game set to show the FPS counter, a frame cap or a performance
log keeps those (MangoHud then takes its settings from the environment, not this file).
"""
from .config import CACHE_DIR

FILE = CACHE_DIR / "mangohud" / "cornerplay.conf"
LEVELS = {
    "off": "no_display",
    "fps": "fps_only",
    "basic": "fps\nframetime\nframe_timing\ncpu_stats\ncpu_temp\ngpu_stats\ngpu_temp\nram\nvram\nposition=top-left",
    "full": "full\nposition=top-left",
}


def level() -> str:
    try:
        first = FILE.read_text().splitlines()[0]
    except (OSError, IndexError):
        return "off"
    return next((k for k, v in LEVELS.items() if v.splitlines()[0] == first.strip()), "off")


def set_level(name: str) -> bool:
    if name not in LEVELS:
        return False
    FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = FILE.with_suffix(".tmp")
    tmp.write_text(LEVELS[name] + "\n")  # the level's own line first: level() reads it back
    tmp.replace(FILE)
    return True


def env() -> dict:
    if not FILE.exists():
        set_level("off")
    return {"MANGOHUD_CONFIGFILE": str(FILE)}
