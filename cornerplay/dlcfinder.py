"""Every DLC for a game, from every store that sells it.

A game's own store lists its DLC first (with what you own and have installed); then Steam, GOG
and Epic are searched for the same game by title and their DLC is added, each row tagged with the
store it is sold on. Stores with no public DLC catalogue of their own (Amazon, Humble, Battle.net,
games you added yourself) get only the other stores' lists.

rows(game, own_rows, steam_appid) -> list of {"id", "title", "status", "url", "image", "price",
"canInstall", "store", "storeName"}. Everything here is blocking; it runs on a worker thread.
"""
import re
import threading
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor

from .config import CACHE_DIR, read_json, write_json
from .net import requests

MATCH_FILE = CACHE_DIR / "dlc_match.json"      # "steam:<title>" -> [store id or "", time]: a game's page on each store
SUMMARY_FILE = CACHE_DIR / "dlc_summary.json"  # game key -> {"t", "total", "toBuy", "ids", "new"}
MISS_TTL = 7 * 86400   # a game a store did not have is looked for again after a week
_lock = threading.Lock()
_match = None
_summary = None
_gog_owned = (0.0, set())  # (time, ids): your GOG games and DLC, for 10 minutes

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/130 Safari/537.36"}
EPIC_GQL = "https://store.epicgames.com/graphql"
NAMES = {"steam": "Steam", "gog": "GOG", "epic": "Epic Games"}

# Edition words that differ between stores for the same game ("GOTY", "Definitive Edition"); only
# taken off the end, so "Gold Rush" or "Digital Combat Simulator" keep their names.
EDITION = re.compile(r"(\s+(game of the year|goty|definitive|complete|deluxe|standard|ultimate|enhanced|"
                     r"gold|premium|anniversary|digital|directors cut|remastered|edition))+$")
SUMMARY_VERSION = 3  # bump when dlc_key changes: old ids would all look like new DLC


def norm(title):
    """A title reduced for matching: "The Witcher® 3: Wild Hunt - GOTY" -> "the witcher 3 wild hunt"."""
    t = re.sub(r"['’‘`´]", "", (title or "").replace("&", " and "))  # Meier's = Meier’s, & = and
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()
    t = " ".join(re.sub(r"[^a-z0-9]+", " ", t).split())
    return EDITION.sub("", t).strip() or t


def country():
    """Two letters: Settings > Country for store prices, else the GOG account's, else the system's."""
    from .wishlist import country as c
    return c()


def variants(title):
    """The title, then its head before " + " or " - " ("Besiege + The Splintered Sea DLC" -> "Besiege")."""
    out = [title]
    for sep in (" + ", " - ", " – "):
        if sep in title:
            out.append(title.split(sep)[0].strip())
    return [v for i, v in enumerate(out) if v and v not in out[:i]]


def find(store, title, finder):
    """A game's id on a store by title, remembered on disk: a found page never changes, a miss is
    asked again after a week. finder(title) -> id or ""."""
    global _match
    with _lock:
        if _match is None:
            _match = read_json(MATCH_FILE) or {}
        hit = _match.get(f"{store}:{title}")
    if hit and (hit[0] or time.time() - hit[1] < MISS_TTL):
        return hit[0]
    found = ""
    for t in variants(title):
        found = finder(t)
        if found:
            break
    with _lock:
        _match[f"{store}:{title}"] = [found, time.time()]
        write_json(MATCH_FILE, _match)
    return found


# --- Steam -------------------------------------------------------------------
def steam_owned():
    """Your Steam app ids (games and DLC) when signed in to Steam in Cornerplay, else None."""
    from . import steamweb
    return steamweb.owned_apps() if steamweb.signed_in() else None


def steam_find(title):
    """The Steam app id of the game with this title, or ""."""
    want = norm(title)
    r = requests.get("https://store.steampowered.com/api/storesearch/",
                     params={"term": title, "l": "english", "cc": country()}, headers=UA, timeout=15)
    r.raise_for_status()  # rate limited or down: an error, never remembered as "not on Steam"
    for it in r.json().get("items") or []:
        if it.get("type") == "app" and norm(it.get("name")) == want:
            return str(it.get("id"))
    return ""


def steam_rows(appid, have=(), client=False):
    """Every DLC Steam sells for this app: installed, owned (when signed in to Steam in Cornerplay),
    else "missing" (Steam did not say whether you own it)."""
    from .stores.steam import _price
    r = requests.get("https://store.steampowered.com/api/dlcforapp/",
                     params={"appid": appid, "l": "english", "cc": country()}, timeout=20)  # one currency on every store
    r.raise_for_status()
    try:
        mine = steam_owned()
    except Exception:  # noqa: BLE001 - ownership is a nicety: the list still shows
        mine = None
    rows = []
    for d in r.json().get("dlc") or []:
        did = str(d.get("id"))
        status = ("installed" if did in have else "owned" if mine and did in mine
                  else "available" if mine is not None else "missing")
        rows.append({"id": did, "title": d.get("name", did), "status": status,
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
    r.raise_for_status()
    for p in r.json().get("products") or []:
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


def gog_owned(store):
    """Your GOG product ids (games and DLC), asked for at most every 10 minutes."""
    global _gog_owned
    if time.time() - _gog_owned[0] < 600:
        return _gog_owned[1]
    owned = set()
    if store.logged_in():
        try:
            o = requests.get("https://embed.gog.com/user/data/games", timeout=20,
                             headers={"Authorization": "Bearer " + store._token()})
            owned = {str(i) for i in o.json().get("owned", [])} if o.ok else set()
        except Exception:  # noqa: BLE001 - ownership is a nicety here
            return owned
    _gog_owned = (time.time(), owned)
    return owned


def gog_rows(pid, store):
    """GOG's DLC for a game found by title (not the GOG copy you own: stores/gog.py lists that)."""
    items = gog_items(pid)
    owned = gog_owned(store) if items else set()
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
          "items{id} price(country:$c){totalPrice{discountPrice originalPrice currencyCode "
          "currencyInfo{decimals}}}}}}}")


def epic_price(p):
    """{"discountPrice": 4499, "originalPrice": 4499, "currencyCode": "AUD", ...} -> "A$44.99" (-30%)."""
    from .itad import money
    if not p or p.get("discountPrice") is None:
        return ""
    if not p["discountPrice"]:
        return "Free"
    div = 10 ** int((p.get("currencyInfo") or {}).get("decimals", 2) or 0)
    text = money({"amount": p["discountPrice"] / div, "currency": p.get("currencyCode") or ""})
    if p.get("originalPrice") and p["discountPrice"] < p["originalPrice"]:
        text += f" (-{round(100 - 100 * p['discountPrice'] / p['originalPrice'])}%)"
    return text


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
        fmt = epic_price((e.get("price") or {}).get("totalPrice") or {})
        status = "installed" if app and app in installed else "owned" if app else "available"
        rows.append({"id": app or e.get("id", ""), "title": (e.get("title") or "").strip(), "status": status,
                     "image": imgs.get("OfferImageWide") or imgs.get("DieselStoreFrontWide") or imgs.get("Thumbnail", ""),
                     "price": "" if app else fmt,
                     "url": f"https://store.epicgames.com/p/{slug}" if slug else "",
                     "canInstall": status == "owned" and game_installed})
    return rows, seen


# --- all of them -------------------------------------------------------------
def rows(game, stores, own_rows, steam_appid="", skip=()):
    """own_rows: the lists you already have (the game's own store and your copies of it on other
    stores, tagged); the other stores are searched here, except those in skip. A store that
    cannot be reached is left out quietly: the others still show."""
    jobs = {}
    title = game.title
    if not norm(title):
        return list(own_rows)
    skip = set(skip) | {game.store}
    if "steam" not in skip and "steam" in stores:
        def steam():
            appid = steam_appid or find("steam", title, steam_find)
            rows = steam_rows(appid, client=bool(stores["steam"].client())) if appid else []
            for r in rows:
                if r["status"] == "missing":
                    r["status"] = "available"  # sold on Steam; your copy of the game is elsewhere
            return rows
        jobs["steam"] = steam
    if "gog" not in skip and "gog" in stores:
        jobs["gog"] = lambda: (lambda pid: gog_rows(pid, stores["gog"]) if pid else [])(find("gog", title, gog_find))
    if "epic" not in skip:
        jobs["epic"] = lambda: (lambda ns: epic_rows(ns)[0] if ns else [])(find("epic", title, epic_find))
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


# --- one DLC on several stores ------------------------------------------------
HAVE = ("installed", "owned")


def dlc_key(title, game_title):
    """What makes two stores' rows the same DLC: the title without the game's name in front."""
    t = norm(title)
    words = t.split()
    cut = 0
    for v in variants(game_title):
        g = norm(v).split()
        # the game's name in front, whole or its tail: Epic's "Civilization VI : Gathering Storm"
        # and Steam's "Sid Meier's Civilization VI: Gathering Storm" are the same DLC
        for start in range(len(g)):
            tail = g[start:]
            if len(tail) < len(words) and words[:len(tail)] == tail and (len(tail) > 1 or len(tail[0]) > 3):
                cut = max(cut, len(tail))
                break
    t = " ".join(words[cut:])
    t = re.sub(r"^(dlc|add on)\s+", "", t)
    t = re.sub(r"\s+(dlc|add on|pack|content)$", "", t)
    t = re.sub(r"\b(original (game )?soundtrack|ost)\b", "soundtrack", t)
    return t or norm(title)


def amount(price):
    """("€", 9.99) from "€9.99 (-30%)"; None when there is no number (blank, Free counts as 0)."""
    if price == "Free":
        return ("", 0.0)
    m = re.search(r"(\d+(?:[.,]\d{1,2})?)", price or "")
    if not m:
        return None
    sign = re.sub(r"[\d.,\s()%-]", "", price.split("(")[0])
    return (sign, float(m.group(1).replace(",", ".")))


def group(rows, game_title):
    """Mark which rows are the same DLC on several stores, in place, and return them.
    Each row gets "group"; the first row of a group ("primary": True, the one you own, else the
    cheapest, else the game's own store) carries "offers": every store's row of it, and each row
    gets "ownedOn" (the stores where you own that DLC) and "cheapest"."""
    groups = {}
    for i, r in enumerate(rows):
        r["group"] = dlc_key(r["title"], game_title)
        groups.setdefault(r["group"], []).append(i)
    for members in groups.values():
        rs = [rows[i] for i in members]
        owned_on = sorted({r.get("storeName", "") for r in rs if r["status"] in HAVE} - {""})
        priced = [(amount(r.get("price", "")), r) for r in rs if r["status"] not in HAVE]
        priced = [(a, r) for a, r in priced if a is not None]
        cheapest = None
        signs = {a[0] for a, _ in priced if a[1] > 0}
        if len(priced) > 1 and len(signs) <= 1:  # comparable only in one currency (Free beats any)
            cheapest = min(priced, key=lambda x: x[0][1])[1]
        for r in rs:
            r["ownedOn"] = [n for n in owned_on if n != r.get("storeName")] if r["status"] not in HAVE else []
            r["cheapest"] = r is cheapest
            r["primary"] = False
        lead = (next((r for r in rs if r["status"] in HAVE), None) or cheapest or rs[0])
        lead["primary"] = True
        lead["offers"] = [{"store": r.get("store", ""), "storeName": r.get("storeName", ""), "price": r.get("price", ""),
                           "url": r.get("url", ""), "status": r["status"], "cheapest": r["cheapest"]}
                          for r in sorted(rs, key=lambda r: (r["status"] not in HAVE, not r["cheapest"],
                                                             (amount(r.get("price", "")) or ("", 1e9))[1]))]
    # installed, then owned, then the rest; alphabetical within each (owned elsewhere counts as owned)
    rank = {"installed": 0, "owned": 1}
    rows.sort(key=lambda r: (rank.get(r["status"], 1 if r.get("ownedOn") else 2), r["group"]))
    return rows


def deals(rows, key, country_code):
    """With an IsThereAnyDeal key: the best deal on any shop it follows (Humble, Fanatical, GMG, ...)
    and the lowest price ever, on each DLC you do not own. In place."""
    from . import itad
    want = [r for r in rows if r.get("primary") and r["status"] not in HAVE and not r.get("ownedOn")]
    if not key or not want:
        return ""
    best, err = itad.prices(sorted({r["title"] for r in want}), key, country_code)
    for r in want:
        b = best.get(r["title"])
        if b:
            r["deal"] = {"shop": b["shop"], "price": b["price"], "url": b["url"], "cut": b["cut"], "low": b["lowPrice"]}
    return err


# --- what the library shows: DLC counts and new DLC ----------------------------
def _load_summary():
    global _summary
    if _summary is None:
        _summary = read_json(SUMMARY_FILE) or {}
    return _summary


def summary(key):
    """{"total", "toBuy", "new", "t"} for a game whose DLC were looked up, else {}. Read-only and
    lock-free: the library grid asks for every card."""
    return (_summary if _summary is not None else _load_summary()).get(key) or {}


def counts(keys):
    """(DLC to get, new DLC) over a game's copies on several stores."""
    hits = [summary(k) for k in keys]
    return (max((h.get("toBuy", 0) for h in hits), default=0),
            max((len(h.get("new") or []) for h in hits), default=0))


def remember(key, rows):
    """Keep a game's DLC counts, and return the titles that are new since its last lookup.
    Only a store that answered last time can have "new" DLC: a store that was down, or a game
    found on a store for the first time, does not make its whole list look new. Known DLC are
    never forgotten, so one that a store stops listing for a day is not new when it is back."""
    global _summary
    lead = [r for r in rows if r.get("primary", True)]
    gid = lambda r: r.get("group") or norm(r["title"])  # noqa: E731
    stores = sorted({r.get("store", "") for r in rows} - {""})
    with _lock:
        _summary = dict(_load_summary())  # a new dict: the grid reads the old one meanwhile
        old = _summary.get(key)
        if old and old.get("v") != SUMMARY_VERSION:
            old = None  # ids made another way: start again rather than call everything new
        known = set((old or {}).get("ids") or [])
        before = set((old or {}).get("stores") or [])
        fresh = {}  # one title per new DLC, though several stores sell it
        for r in rows if old is not None else []:
            if r.get("store") in before and gid(r) not in known and r["status"] not in HAVE:
                fresh.setdefault(gid(r), r["title"])
        fresh = sorted(fresh.values())
        _summary[key] = {
            "v": SUMMARY_VERSION, "t": time.time(), "total": len(lead),
            "ids": sorted(known | {gid(r) for r in rows}), "stores": sorted(before | set(stores)),
            "new": sorted(set((old or {}).get("new") or []) | set(fresh)),
            # unknown ("missing": Steam without sign-in) is not counted as DLC to get
            "toBuy": sum(1 for r in lead if r["status"] == "available" and not r.get("ownedOn"))}
        write_json(SUMMARY_FILE, _summary)
    return fresh


def seen(key):
    """The DLC window was opened: the game's new DLC are not new any more."""
    global _summary
    with _lock:
        hit = _load_summary().get(key)
        if hit and hit.get("new"):
            _summary = dict(_summary)
            _summary[key] = dict(hit, new=[])
            write_json(SUMMARY_FILE, _summary)
            return True
    return False
