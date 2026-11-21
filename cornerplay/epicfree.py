"""Epic's free games: this week's and the next ones, from the store's public promotions feed.

Epic does not let other apps claim them (its checkout has a captcha, and its terms forbid
automated use of the store), so claiming stays one click of yours: for a game free right now,
"Get" opens Epic's checkout for that offer straight away (store.epicgames.com/purchase), where
"Place order" adds it to the account; it then shows up in Cornerplay on the next refresh.
Cornerplay reminds you once when a free game you have not claimed ends within a day.
"""
import time
from datetime import datetime

from .net import requests

from .config import CACHE_DIR, read_json, write_json

FEED = "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions"
FILE = CACHE_DIR / "epic_free.json"
HISTORY = CACHE_DIR / "epic_free_history.json"  # {title: [start, end]} of every giveaway seen
TTL = 3 * 3600


def _offers(promos, key):
    return [o for g in (promos.get(key) or []) for o in (g.get("promotionalOffers") or [])
            if (o.get("discountSetting") or {}).get("discountPercentage") == 0]


def _stamp(iso):
    try:
        return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp())
    except (AttributeError, ValueError):
        return 0


def _slug(e):
    slug = e.get("productSlug") or ""
    if not slug or slug == "[]":
        for m in (e.get("catalogNs") or {}).get("mappings") or []:
            if m.get("pageSlug"):
                slug = m["pageSlug"]
                break
    return slug.split("/")[0]


def fetch():
    """[{title, url, tall, wide, start, end, now}], free now first. Raises on network errors."""
    r = requests.get(FEED, params={"locale": "en-US", "country": "US", "allowCountries": "US"}, timeout=20)
    r.raise_for_status()
    out = []
    for e in r.json()["data"]["Catalog"]["searchStore"]["elements"]:
        promos = e.get("promotions") or {}
        now, soon = _offers(promos, "promotionalOffers"), _offers(promos, "upcomingPromotionalOffers")
        offer = (now or soon or [None])[0]
        if not offer:
            continue
        images = {i.get("type"): i.get("url") for i in e.get("keyImages") or []}
        slug = _slug(e)
        checkout = (f"https://store.epicgames.com/purchase?offers=1-{e['namespace']}-{e['id']}"
                    if now and e.get("namespace") and e.get("id") else "")
        out.append({
            "title": (e.get("title") or "").strip(),
            "url": f"https://store.epicgames.com/p/{slug}" if slug else "https://store.epicgames.com/free-games",
            "tall": images.get("OfferImageTall") or images.get("Thumbnail") or "",
            "wide": images.get("OfferImageWide") or images.get("featuredMedia") or "",
            "start": _stamp(offer.get("startDate")), "end": _stamp(offer.get("endDate")),
            "now": bool(now),
            "checkout": checkout,
        })
    out.sort(key=lambda g: (not g["now"], g["start"]))
    return out


def get(force=False):
    """The cached list while it is fresh, else a new one (falls back to the cache when offline)."""
    cached = read_json(FILE) or {}
    if not force and time.time() - cached.get("t", 0) < TTL:
        return cached.get("games") or []
    try:
        games = fetch()
    except Exception:
        return cached.get("games") or []
    write_json(FILE, {"t": time.time(), "games": games})
    remember(games)
    return games


def remember(games):
    """Keep each giveaway's window, so a game that arrives during it can be told apart from a purchase."""
    seen = read_json(HISTORY) or {}
    changed = False
    for g in games:
        if g.get("title") and g.get("start") and seen.get(g["title"]) != [g["start"], g["end"]]:
            seen[g["title"]] = [g["start"], g["end"]]
            changed = True
    if changed:
        write_json(HISTORY, seen)


def _norm(title):
    return "".join(ch for ch in title.lower() if ch.isalnum())


def giveaway(title, arrived):
    """True when the game came to the account (first seen at `arrived`) while Epic gave it away."""
    if not arrived:
        return False
    seen = {_norm(t): w for t, w in (read_json(HISTORY) or {}).items()}
    start, end = seen.get(_norm(title)) or (0, 0)
    return bool(start) and start - 86400 <= arrived <= end + 7 * 86400  # a refresh can come days later


REMINDED = CACHE_DIR / "epic_free_reminded.json"  # {title: end} already reminded about
SOON = 24 * 3600


def due_reminders(games, owned, now=None):
    """Free-now games not claimed yet that end within a day and were not reminded about.
    owned: normalised titles in the Epic library. Marks the returned ones as reminded."""
    now = now or time.time()
    done = read_json(REMINDED) or {}
    due = [g for g in games
           if g.get("now") and g.get("end") and now < g["end"] <= now + SOON
           and _norm(g["title"]) not in owned and done.get(g["title"]) != g["end"]]
    if due:
        done.update({g["title"]: g["end"] for g in due})
        write_json(REMINDED, {t: e for t, e in done.items() if e > now - 30 * 86400})
    return due
