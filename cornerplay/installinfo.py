"""What an install will take, before it starts (the Install window, as Heroic has it).

info(store_id, store, game) -> {"download": bytes, "disk": bytes, "dlcs": [titles], "languages": [codes]}
Sizes are 0 when the store's tool does not say; nothing here downloads the game.
"""
import json

from .config import find_tool
from .stores.base import run

# The stores whose tool Cornerplay drives itself (the others install in their own app).
STORES = ("epic", "gog", "amazon")


def _json(argv, timeout=90):
    try:
        r = run(argv, timeout=timeout)
        return json.loads((r.stdout or "").strip() or "{}")
    except Exception:  # offline, signed out, an old tool: the window still opens, without sizes
        return {}


def epic(tool, game_id):
    d = _json([tool, "info", game_id, "--json"])
    m = d.get("manifest") or {}
    g = d.get("game") or {}
    return {"download": int(m.get("download_size") or 0), "disk": int(m.get("disk_size") or 0),
            "dlcs": [x.get("title") or x.get("app_name") for x in g.get("owned_dlc") or [] if isinstance(x, dict)],
            "languages": []}


def gog(tool, auth, game_id, platform="windows"):
    d = _json([tool, "--auth-config-path", str(auth), "info", game_id, "--platform", platform])
    sizes = d.get("size") or {}
    langs = [x for x in d.get("languages") or [] if isinstance(x, str)]
    return {"sizes": {k: (int(v.get("download_size") or 0), int(v.get("disk_size") or 0))
                      for k, v in sizes.items() if isinstance(v, dict)},
            "dlcs": [x.get("title") or str(x.get("id")) for x in d.get("dlcs") or [] if isinstance(x, dict)],
            "languages": langs}


def gog_size(data, lang):
    """GOG lists sizes per language, plus "*" for the files every language shares."""
    sizes = data.get("sizes") or {}
    base = sizes.get("*", (0, 0))
    own = sizes.get(lang) or (next(iter(v for k, v in sizes.items() if k != "*"), (0, 0)))
    return base[0] + own[0], base[1] + own[1]


def amazon(tool, game_id):
    d = _json([tool, "install", "--info", "--json", game_id])
    size = int(d.get("download_size") or 0)
    return {"download": size, "disk": size, "dlcs": [], "languages": []}


def pick_language(languages, ui_locale="en"):
    """The game language to preselect: the interface's, else English, else the first."""
    if not languages:
        return ""
    want = (ui_locale or "en").replace("_", "-").lower()
    for lang in languages:
        if lang.lower() == want or lang.lower().split("-")[0] == want.split("-")[0]:
            return lang
    for lang in languages:
        if lang.lower().startswith("en"):
            return lang
    return languages[0]


def info(store_id, store, game, platform="windows", ui_locale="en"):
    if store_id == "epic":
        tool = find_tool("legendary")
        return epic(tool, game.id) if tool else {}
    if store_id == "gog":
        from .stores.gog import AUTH_FILE
        tool = find_tool("gogdl")
        if not tool:
            return {}
        try:
            store._token()  # a fresh token for gogdl
        except Exception:
            pass
        d = gog(tool, AUTH_FILE, game.id, platform)
        lang = pick_language(d["languages"], ui_locale)
        d["download"], d["disk"] = gog_size(d, lang)
        d["language"] = lang
        return d
    if store_id == "amazon":
        tool = find_tool("nile")
        return amazon(tool, game.id) if tool else {}
    return {}
