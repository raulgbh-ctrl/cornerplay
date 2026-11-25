"""The PC Game Pass catalog: every PC game in the subscription, with its title and covers.

Microsoft publishes the list without a sign-in: catalog.gamepass.com gives the products' ids
(a "sigl", Microsoft's word for a curated list), displaycatalog.mp.microsoft.com their titles and
art. Kept for a day (the catalog changes a few times a month). The store page (stores/xbox.py)
shows the games not installed yet as tiles; installing one goes through Nexus Launcher on Linux
and the Xbox app on Windows.
"""
import locale
import os
import time

from .config import CACHE_DIR, read_json, settings, write_json
from .net import requests

ALL_PC_GAMES = "fdd9e2a7-0fee-49f6-ad69-4354098401ff"  # "All PC Games" in PC Game Pass
CACHE = CACHE_DIR / "gamepass.json"
TTL = 24 * 3600
BATCH = 100  # products asked for at once (the details service answers 100 in about a second)


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
            out.append({"id": p.get("ProductId", ""), "title": title,
                        "cover": _image(images, "Poster", "BoxArt"),
                        "hero": _image(images, "SuperHeroArt", "TitledHeroArt", "Screenshot"),
                        "publisher": (props.get("PublisherName") or "").strip()})
    return out


def catalog(force=False) -> list:
    """[{"id" (the Store's product id), "title", "cover", "hero", "publisher"}]; the cached copy
    when the network is down, [] when there never was one."""
    cached = read_json(CACHE) or {}
    mkt = market()
    if not force and cached.get("market") == mkt and time.time() - cached.get("t", 0) < TTL:
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
    write_json(CACHE, {"t": time.time(), "market": market(), "games": games})
    return games
