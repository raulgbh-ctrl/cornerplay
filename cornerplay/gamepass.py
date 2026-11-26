"""The PC Game Pass catalog: every PC game in the subscription, with its title and covers.

Microsoft publishes the list without a sign-in: catalog.gamepass.com gives the products' ids
(a "sigl", Microsoft's word for a curated list), displaycatalog.mp.microsoft.com their titles and
art. Kept for a day (the catalog changes a few times a month). The store page (stores/xbox.py)
shows the games not installed yet as tiles; installing one goes through Nexus Launcher on Linux
and the Xbox app on Windows.
"""
import json
import locale
import os
import re
import time

from .config import CACHE_DIR, read_json, settings, write_json
from .net import requests

ALL_PC_GAMES = "fdd9e2a7-0fee-49f6-ad69-4354098401ff"  # "All PC Games" in PC Game Pass
CACHE = CACHE_DIR / "gamepass.json"
TTL = 24 * 3600
BATCH = 100  # products asked for at once (the details service answers 100 in about a second)
CACHE_VERSION = 3  # 2: each game keeps "passes" (the Game Pass tiers that include it); 3: "title_id"

# Microsoft's Game Pass products (the ids xbox.com itself uses). Each game's Store listing names the
# passes that include it, so a tier's games are the catalog's games that name its pass.
PASSES = {
    "CFQ7TTC0KHS0": "full",       # Game Pass Ultimate: every PC game
    "CFQ7TTC0HXBN": "full",       # Game Pass Ultimate (older offer)
    "CFQ7TTC0KGQ8": "full",       # PC Game Pass: every PC game
    "CFQ7TTC0P85B": "premium",    # Game Pass Premium: a smaller PC selection
    "CFQ7TTC0K5DJ": "essential",  # Game Pass Essential: a small PC selection
    "CFQ7TTC10QFD": "starter",    # Game Pass Starter Edition
    "CFQ7TTC0K6L8": "console",    # Game Pass for Console: no PC games
}
TIER_RANK = {"": 0, "console": 1, "starter": 2, "essential": 3, "premium": 4, "full": 5}
# Which passes' games a tier gets: Premium also has everything in Essential.
TIER_PASSES = {"premium": {"CFQ7TTC0P85B", "CFQ7TTC0K5DJ"}, "essential": {"CFQ7TTC0K5DJ"},
               "starter": {"CFQ7TTC10QFD"}}
_PASS_RE = re.compile(r"CFQ7TTC[0-9A-Z]{5}")


def tier_of(pass_ids) -> str:
    """The best tier among some pass product ids: "full", "premium", "essential", "starter",
    "console", or "" when none is a Game Pass."""
    best = ""
    for pid in pass_ids or ():
        t = PASSES.get(str(pid).strip().upper(), "")
        if TIER_RANK[t] > TIER_RANK[best]:
            best = t
    return best


def for_tier(games, tier: str) -> list:
    """The catalog's games a tier can play: all of them for Ultimate / PC Game Pass (and for a pass
    Cornerplay does not know yet), the ones naming the tier's passes for the smaller ones."""
    if tier in ("", "console"):
        return []
    wanted = TIER_PASSES.get(tier)
    if not wanted:
        return list(games)
    return [g for g in games if wanted & set(g.get("passes") or ())]


def market() -> str:
    """Two letters, like "RO": Settings first, then the system's locale; "US" when unsure."""
    chosen = str(settings.get("gamepass_market") or "").strip().upper()
    if len(chosen) == 2 and chosen.isalpha():
        return chosen
    for value in (os.environ.get("LC_ALL"), os.environ.get("LANG"), (locale.getlocale()[0] or "")):
        if value and "_" in value:
            country = value.split("_", 1)[1][:2].upper()
            if country.isalpha() and len(country) == 2:
                return country
    return "US"


def _image(images, *purposes):
    for purpose in purposes:
        for img in images:
            if img.get("ImagePurpose") == purpose and img.get("Uri"):
                uri = img["Uri"]
                return ("https:" + uri) if uri.startswith("//") else uri
    return ""


def _ids(mkt):
    r = requests.get("https://catalog.gamepass.com/sigls/v2",
                     params={"id": ALL_PC_GAMES, "language": "en-us", "market": mkt}, timeout=20)
    r.raise_for_status()
    return [x["id"] for x in r.json() if isinstance(x, dict) and x.get("id")]


def _details(ids, mkt):
    out = []
    for i in range(0, len(ids), BATCH):
        r = requests.get("https://displaycatalog.mp.microsoft.com/v7.0/products",
                         params={"bigIds": ",".join(ids[i:i + BATCH]), "market": mkt, "languages": "en-us"}, timeout=30)
        r.raise_for_status()
        for p in r.json().get("Products") or []:
            props = (p.get("LocalizedProperties") or [{}])[0]
            images = props.get("Images") or []
            title = (props.get("ProductTitle") or "").strip()
            if not title:
                continue
            title_id = next((str(a.get("Value") or "") for a in p.get("AlternateIds") or []
                             if a.get("IdType") == "XboxTitleId"), "")
            out.append({"id": p.get("ProductId", ""), "title": title, "title_id": title_id,
                        "cover": _image(images, "Poster", "BoxArt"),
                        "hero": _image(images, "SuperHeroArt", "TitledHeroArt", "Screenshot"),
                        "publisher": (props.get("PublisherName") or "").strip(),
                        "passes": sorted(set(_PASS_RE.findall(json.dumps(p.get("DisplaySkuAvailabilities") or [])))
                                         & set(PASSES))})
    return out


def products(ids) -> list:
    """Titles and art for some Store product ids (the games an account owns), cached like the
    catalog; ids Microsoft does not know are left out."""
    ids = [i for i in ids if i]
    if not ids:
        return []
    cache = CACHE_DIR / "xbox-products.json"
    cached = read_json(cache) or {}
    mkt = market()
    known = cached.get("games") or {}
    if (cached.get("market") == mkt and cached.get("v") == CACHE_VERSION and time.time() - cached.get("t", 0) < TTL
            and all(i in known for i in ids)):
        return [known[i] for i in ids if known[i]]
    try:
        found = {g["id"]: g for g in _details(ids, mkt)}
    except (requests.RequestException, ValueError):
        return [known[i] for i in ids if known.get(i)]
    known = {i: found.get(i) or {} for i in ids}
    write_json(cache, {"t": time.time(), "market": mkt, "v": CACHE_VERSION, "games": known})
    return [known[i] for i in ids if known[i]]


def catalog(force=False) -> list:
    """[{"id" (the Store's product id), "title", "cover", "hero", "publisher"}]; the cached copy
    when the network is down, [] when there never was one."""
    cached = read_json(CACHE) or {}
    mkt = market()
    if (not force and cached.get("market") == mkt and cached.get("v") == CACHE_VERSION
            and time.time() - cached.get("t", 0) < TTL):
        return cached.get("games") or []
    try:
        try:
            ids = _ids(mkt)
        except requests.RequestException:
            ids = []
        if not ids and mkt != "US":  # Game Pass is not sold in every country: the US list then
            mkt = "US"
            ids = _ids(mkt)
        games = _details(ids, mkt) if ids else []
    except (requests.RequestException, ValueError):
        return cached.get("games") or []
    if not games:  # offline, or Microsoft answered with nothing: keep what was there
        return cached.get("games") or []
    write_json(CACHE, {"t": time.time(), "market": market(), "v": CACHE_VERSION, "games": games})
    return games
