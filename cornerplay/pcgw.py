"""Known fixes for a game, from PCGamingWiki (the "Known fixes" card on a game's page).

PCGamingWiki's page for the game is found with its search (matched on the exact title), then the
sections "Essential improvements" and "Issues fixed" are read: each fix there becomes a row with
its title, a one-line summary, a link to that spot on the wiki, and, when the fix is a command-line
argument ("-NoLauncher"), that argument so it can be added to the game's launch arguments.
Linux fixes come first. Cached for two weeks per game (~/.cache/cornerplay/pcgw.json).
"""
import html
import re
import time
from urllib.parse import quote

from .config import CACHE_DIR, read_json, write_json
from .net import requests

API = "https://www.pcgamingwiki.com/w/api.php"
WIKI = "https://www.pcgamingwiki.com/wiki/"
HEADERS = {"User-Agent": "Cornerplay (game launcher)"}
FILE = CACHE_DIR / "pcgw.json"
TTL = 14 * 86400
SECTIONS = ("Essential improvements", "Issues fixed")


def _get(params):
    r = requests.get(API, params=dict(params, format="json"), headers=HEADERS, timeout=20)
    r.raise_for_status()
    return r.json()


def page_for(title: str) -> str:
    from .dlcfinder import norm
    want = norm(title)
    hits = (_get({"action": "query", "list": "search", "srsearch": title, "srlimit": 8}).get("query") or {}).get("search") or []
    return next((h["title"] for h in hits if norm(h.get("title")) == want), "")


def clean(text: str) -> str:
    """Wiki markup to plain text: {{Code|-x}} -> -x, [[a|b]] -> b, [url label] -> label."""
    t = re.sub(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", "", text or "", flags=re.S)
    t = re.sub(r"\{\{P\|(\w+)\}\}", lambda m: f"<{m.group(1)}>", t)
    for _ in range(4):  # nested templates: innermost first
        t = re.sub(r"\{\{(?:Code|code|file|File|key|Key|term|Term)\|([^{}|]*)\}\}", r"\1", t)
        t = re.sub(r"\{\{[^{}]*\}\}", "", t)
    t = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", t)
    t = re.sub(r"\[https?://\S+ ([^\]]*)\]", r"\1", t)
    t = re.sub(r"<li>", " · ", t)
    t = re.sub(r"<[^>]+>", " ", t)
    t = html.unescape(t).replace("{{", "").replace("}}", "")
    return re.sub(r"\s+", " ", t).strip(" ·")


def _fixes_in(wikitext: str, page: str, group: str) -> list:
    """The fixes under one section. A "Linux" sub-heading's fixes are Linux ones; a "Windows"
    sub-heading's are left out (they do not apply under Proton)."""
    out = []
    parts = re.split(r"^(={3,4})\s*(.+?)\s*\1\s*$", wikitext, flags=re.M)
    # parts: [intro, "===", title, body, "====", title, body, ...]
    parent = ""
    for i in range(1, len(parts) - 2, 3):
        level, title, body = len(parts[i]), parts[i + 1].strip(), parts[i + 2]
        if level == 3:
            parent = title.lower()
        under = parent if level == 4 else title.lower()
        if under in ("windows", "mac os", "macos", "os x"):
            continue
        desc = re.search(r"\|description=(.*)", body, flags=re.S)
        first = desc.group(1).split("{{Fixbox")[0] if desc else body
        first = re.split(r"\|ref=|\|fix=", first)[0]
        summary = clean(first)[:220]
        if not summary or (level == 3 and title.lower() == "linux"):
            continue
        args = ""
        if desc and re.search(r"command line argument|launch option|launch argument", first, re.I):
            code = re.search(r"\{\{Code\|(-[^{}|]+)\}\}", first)
            args = code.group(1).strip() if code else ""
        anchor = quote(title.replace(" ", "_"), safe="_-.")
        out.append({"title": clean(title), "summary": summary, "args": args, "group": group,
                    "linux": under == "linux" or "linux" in title.lower() or "proton" in summary.lower(),
                    "url": f"{WIKI}{quote(page.replace(' ', '_'))}#{anchor}"})
    return out


def fixes(key: str, title: str, force=False) -> dict:
    """{"page", "url", "fixes": [...]} ({} when the wiki has no page for it). Blocking."""
    cache = read_json(FILE) or {}
    hit = cache.get(key)
    if hit and not force and time.time() - hit.get("t", 0) < TTL:
        return hit.get("data") or {}
    data = {}
    page = page_for(title)
    if page:
        secs = (_get({"action": "parse", "page": page, "prop": "sections"}).get("parse") or {}).get("sections") or []
        found = []
        for name in SECTIONS:
            idx = next((s["index"] for s in secs if s.get("line") == name and s.get("index")), "")
            if not idx:
                continue
            text = ((_get({"action": "parse", "page": page, "prop": "wikitext", "section": idx}).get("parse") or {})
                    .get("wikitext") or {}).get("*", "")
            found += _fixes_in(text, page, "essential" if name == SECTIONS[0] else "fixed")
        found.sort(key=lambda f: (not f["linux"], f["group"] != "essential"))
        data = {"page": page, "url": WIKI + quote(page.replace(" ", "_")), "fixes": found[:12]}
    cache[key] = {"t": time.time(), "data": data}
    write_json(FILE, cache)
    return data
