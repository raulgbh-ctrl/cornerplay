"""Every DLC for a game, from every store that sells it.

A game's own store lists its DLC first (with what you own and have installed); then Steam, GOG
and Epic are searched for the same game by title and their DLC is added, each row tagged with the
store it is sold on. Stores with no public DLC catalogue of their own (Amazon, Humble, Battle.net,
games you added yourself) get only the other stores' lists.

rows(game, own_rows, steam_appid) -> list of {"id", "title", "status", "url", "image", "price",
"canInstall", "store", "storeName"}. Everything here is blocking; it runs on a worker thread.
"""
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor

from .net import requests

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/130 Safari/537.36"}
EPIC_GQL = "https://store.epicgames.com/graphql"
NAMES = {"steam": "Steam", "gog": "GOG", "epic": "Epic Games"}

# Edition words that differ between stores for the same game ("GOTY", "Definitive Edition").
EDITION = re.compile(r"\b(game of the year|goty|definitive|complete|deluxe|standard|ultimate|enhanced|"
                     r"gold|premium|anniversary|digital|director'?s cut|remastered|edition)\b")


def norm(title):
    """A title reduced for matching: "The Witcher® 3: Wild Hunt - GOTY" -> "the witcher 3 wild hunt"."""
    t = unicodedata.normalize("NFKD", title or "").encode("ascii", "ignore").decode().lower()
    t = re.sub(r"[™®©]", "", t)
    t = EDITION.sub(" ", t)
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return " ".join(t.split())


def country():
    from PySide6.QtCore import QLocale
    name = QLocale.system().name()  # "en_AU"
    return name.split("_")[1] if "_" in name else "US"


# --- Steam -------------------------------------------------------------------
def steam_find(title):
    """The Steam app id of the game with this title, or ""."""
    want = norm(title)
    r = requests.get("https://store.steampowered.com/api/storesearch/",
                     params={"term": title, "l": "english", "cc": country()}, headers=UA, timeout=15)
    for it in (r.json().get("items") or []) if r.ok else []:
        if it.get("type") == "app" and norm(it.get("name")) == want:
            return str(it.get("id"))
    return ""


def steam_rows(appid, have=(), client=False):
    """Every DLC Steam sells for this app. Steam does not say which you own, only which are installed."""
    from .stores.steam import _price
    r = requests.get("https://store.steampowered.com/api/dlcforapp/",
                     params={"appid": appid, "l": "english"}, timeout=20)
    r.raise_for_status()
    rows = []
    for d in r.json().get("dlc") or []:
        did = str(d.get("id"))
        rows.append({"id": did, "title": d.get("name", did),
                     "status": "installed" if did in have else "missing",
                     "image": d.get("header_image", ""), "price": _price(d.get("price_overview")),
                     "url": f"steam://store/{did}" if client else f"https://store.steampowered.com/app/{did}",
                     "canInstall": False})
    return rows


# --- GOG ---------------------------------------------------------------------
def gog_base(pid):
    """GOG sells many games only as a pack (an edition); its DLC hang off the game inside it."""
    try:
        links = requests.get(f"https://api.gog.com/v2/games/{pid}", timeout=15).json().get("_links") or {}
        href = ((links.get("includesGames") or [{}])[0]).get("href", "")
    except (requests.RequestException, ValueError, AttributeError):
        return ""
    m = re.search(r"/games/(\d+)", href)
    return m.group(1) if m else ""


def gog_find(title):
    want = norm(title)
    r = requests.get("https://catalog.gog.com/v1/catalog",
                     params={"limit": 20, "query": "like:" + title, "productType": "in:game,pack",
                             "order": "desc:score"}, timeout=15)
    for p in (r.json().get("products") or []) if r.ok else []:
        if norm(p.get("title")) == want:
            return str(p.get("id"))
    return ""


def gog_items(pid):
    """GOG's DLC products for a game (or for the game inside a pack)."""
    r = requests.get(f"https://api.gog.com/products/{pid}", params={"expand": "expanded_dlcs"}, timeout=20)
    r.raise_for_status()
    d = r.json()
    items = d.get("expanded_dlcs") or []
    if not items and d.get("game_type") == "pack":
        base = gog_base(pid)
        if base and base != str(pid):
            return gog_items(base)
    return items


def gog_rows(pid, store):
    """GOG's DLC for a game found by title (not the GOG copy you own: stores/gog.py lists that)."""
    items = gog_items(pid)
    owned = set()
    if items and store.logged_in():
        try:
            o = requests.get("https://embed.gog.com/user/data/games", timeout=20,
                             headers={"Authorization": "Bearer " + store._token()})
            owned = {str(i) for i in o.json().get("owned", [])} if o.ok else set()
        except Exception:  # noqa: BLE001 - ownership is a nicety here
            owned = set()
    prices = store._prices([str(d.get("id")) for d in items])
    rows = []
    for d in items:
        did = str(d.get("id"))
        img = (d.get("images") or {}).get("logo2x") or (d.get("images") or {}).get("logo") or ""
        status = "owned" if did in owned else "available"
        rows.append({"id": did, "title": d.get("title", did), "status": status,
                     "image": ("https:" + img) if img.startswith("//") else img,
                     "price": "" if status == "owned" else prices.get(did, ""),
                     "url": (d.get("links") or {}).get("product_card", ""), "canInstall": False})
    return rows


# --- Epic --------------------------------------------------------------------
def _epic(query, variables):
    r = requests.post(EPIC_GQL, json={"query": query, "variables": variables}, headers=UA, timeout=20)
    r.raise_for_status()
    data = r.json()
    if data.get("errors") and not data.get("data"):
        raise requests.RequestException(data["errors"][0].get("message", "Epic store error"))
    return ((data.get("data") or {}).get("Catalog") or {}).get("searchStore") or {}


def epic_find(title):
    """The Epic namespace of the game with this title, or ""."""
    want = norm(title)
    s = _epic("query($k:String,$c:String!){Catalog{searchStore(keywords:$k,category:\"games/edition/base\","
              "count:20,country:$c,locale:\"en-US\"){elements{title namespace}}}}",
              {"k": title, "c": country()})
    for e in s.get("elements") or []:
        if norm(e.get("title")) == want:
            return e.get("namespace", "")
    return ""


ADDONS = ("query($ns:String,$c:String!,$s:Int){Catalog{searchStore(namespace:$ns,category:\"addons\",count:100,"
          "start:$s,country:$c,locale:\"en-US\"){paging{total} elements{title id productSlug urlSlug "
          "keyImages{type url} offerMappings{pageSlug} catalogNs{mappings(pageType:\"productHome\"){pageSlug}} "
          "items{id} price(country:$c){totalPrice{discountPrice originalPrice fmtPrice(locale:\"en-US\")"
          "{discountPrice}}}}}}}")


def epic_catalog(namespace):
    """Every add-on the Epic store sells in a game's namespace."""
    out, start = [], 0
    while True:
        s = _epic(ADDONS, {"ns": namespace, "c": country(), "s": start})
        els = s.get("elements") or []
        out += els
        start += len(els)
        if not els or start >= ((s.get("paging") or {}).get("total") or 0) or start >= 500:
            return out


def epic_rows(namespace, owned=None, installed=(), game_installed=False):
    """owned: {catalog item id: legendary app name} for the DLC you own (only for your Epic copy)."""
    owned = owned or {}
    rows, seen = [], set()
    for e in epic_catalog(namespace):
        items = [i.get("id") for i in e.get("items") or []]
        app = next((owned[i] for i in items if i in owned), "")
        seen.update(i for i in items if i in owned)
        imgs = {k.get("type"): k.get("url") for k in e.get("keyImages") or []}
        slug = ((e.get("offerMappings") or [{}])[0] or {}).get("pageSlug") or e.get("productSlug") or ""
        if not slug:
            slug = ((((e.get("catalogNs") or {}).get("mappings")) or [{}])[0] or {}).get("pageSlug", "")
        price = (e.get("price") or {}).get("totalPrice") or {}
        fmt = (price.get("fmtPrice") or {}).get("discountPrice") or ""
        if price and not price.get("discountPrice"):
            fmt = "Free"
        elif price.get("originalPrice") and price["discountPrice"] < price["originalPrice"]:
            fmt += f" (-{round(100 - 100 * price['discountPrice'] / price['originalPrice'])}%)"
        status = "installed" if app and app in installed else "owned" if app else "available"
        rows.append({"id": app or e.get("id", ""), "title": (e.get("title") or "").strip(), "status": status,
                     "image": imgs.get("OfferImageWide") or imgs.get("DieselStoreFrontWide") or imgs.get("Thumbnail", ""),
                     "price": "" if app else fmt,
                     "url": f"https://store.epicgames.com/p/{slug}" if slug else "",
                     "canInstall": status == "owned" and game_installed})
    return rows, seen


# --- all of them -------------------------------------------------------------
def rows(game, stores, own_rows, steam_appid=""):
    """own_rows: the game's own store's list (already tagged); the other stores are searched here.
    A store that cannot be reached is left out quietly: the others still show."""
    jobs = {}
    title = game.title
    if game.store != "steam" and "steam" in stores:
        def steam():
            appid = steam_appid or steam_find(title)
            rows = steam_rows(appid, client=bool(stores["steam"].client())) if appid else []
            for r in rows:
                r["status"] = "available"  # sold on Steam; your copy of the game is elsewhere
            return rows
        jobs["steam"] = steam
    if game.store != "gog" and "gog" in stores:
        jobs["gog"] = lambda: (lambda pid: gog_rows(pid, stores["gog"]) if pid else [])(gog_find(title))
    if game.store != "epic":
        jobs["epic"] = lambda: (lambda ns: epic_rows(ns)[0] if ns else [])(epic_find(title))
    found = {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        futs = {sid: pool.submit(fn) for sid, fn in jobs.items()}
        for sid, f in futs.items():
            try:
                found[sid] = f.result(timeout=60)
            except Exception:  # noqa: BLE001 - one store failing must not hide the others
                found[sid] = []
    out = list(own_rows)
    for sid in ("steam", "gog", "epic"):
        for r in found.get(sid) or []:
            r.update(store=sid, storeName=NAMES[sid])
            out.append(r)
    return out
