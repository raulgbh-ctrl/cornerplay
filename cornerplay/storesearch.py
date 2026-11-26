"""The Store page's search and per-store shelves: every store asked at once.

search(query) asks Steam, Epic, GOG and the Xbox / Microsoft Store together (each in its own
thread, a few seconds at most) and groups what they find by game, so one row shows every store's
price for it. Humble, Amazon and Battle.net have no search Cornerplay may use (Humble's sits
behind a bot check), so they get a "search on their site" link instead (site_links).

shelves() gives each store's own shelf for browsing: Steam's specials, Epic's games on sale,
GOG's trending games, Xbox's most popular PC games. Kept for an hour.

Every result: {"store", "shop", "id", "title", "art" (tall first), "money", "price", "url"}; prices
are shown in one currency (currency.py: euros or dollars), converted where a store uses another.
Nothing here needs a sign-in; owned games are marked by the app, from the library.
"""
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote

from .config import CACHE_DIR, read_json, write_json
from .net import requests

SHELVES = CACHE_DIR / "store-shelves.json"
SHELF_TTL = 3600
LIMIT = 12          # results per store for a search
TIMEOUT = 12        # seconds per store


def _country():
    from .dlcfinder import country
    return country()


def _money(amount, cur, base=None):
    """A price kept as numbers; _priced() turns it into text in the one currency (currency.py)."""
    if amount is None:
        return None
    return {"amount": float(amount), "currency": (cur or "").upper(), "base": float(base) if base else None}


def _steam_money(p):
    if not p or p.get("final") is None:
        return None
    return _money(p["final"] / 100, p.get("currency", ""), (p.get("initial") or 0) / 100 or None)


def _priced(rows, table=None):
    """Each row's "price" in the one currency (from its "money"), converted where needed."""
    from . import currency
    to = currency.target()
    table = currency.rates() if table is None else table
    for r in rows:
        m = r.get("money")
        r["price"] = currency.text(m["amount"], m["currency"], m.get("base"), to, table) if m else r.get("price", "")
    return rows


def _steam_art(appid):
    return [f"https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/{appid}/library_600x900.jpg",
            f"https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/{appid}/header.jpg"]


# --- searching ----------------------------------------------------------------------------------
def steam(query):
    from .dlcfinder import UA
    r = requests.get("https://store.steampowered.com/api/storesearch/",
                     params={"term": query, "l": "english", "cc": _country()}, headers=UA, timeout=TIMEOUT)
    r.raise_for_status()
    return [{"store": "steam", "shop": "Steam", "id": str(it["id"]), "title": it.get("name", ""),
             "art": _steam_art(it["id"]) + ([it["tiny_image"]] if it.get("tiny_image") else []),
             "money": _steam_money(it.get("price")) or (_money(0, "") if "price" not in it else None),
             "url": f"https://store.steampowered.com/app/{it['id']}"}
            for it in (r.json().get("items") or [])[:LIMIT] if it.get("type") == "app" and it.get("id")]


EPIC_FIELDS = ("elements{title id productSlug urlSlug keyImages{type url} offerMappings{pageSlug} "
               "catalogNs{mappings(pageType:\"productHome\"){pageSlug}} "
               "price(country:$c){totalPrice{discountPrice originalPrice currencyCode currencyInfo{decimals}}}}")


def _epic_money(p):
    if not p or p.get("discountPrice") is None:
        return None
    div = 10 ** int((p.get("currencyInfo") or {}).get("decimals", 2) or 0)
    return _money(p["discountPrice"] / div, p.get("currencyCode"), (p.get("originalPrice") or 0) / div or None)


def _epic_rows(elements):
    out = []
    for e in elements or []:
        slug = (((e.get("catalogNs") or {}).get("mappings") or [{}])[0] or {}).get("pageSlug") \
            or ((e.get("offerMappings") or [{}])[0] or {}).get("pageSlug") or e.get("productSlug") or e.get("urlSlug") or ""
        imgs = {i.get("type"): i.get("url") for i in e.get("keyImages") or []}
        art = [u for u in (imgs.get("OfferImageTall"), imgs.get("DieselStoreFrontTall"), imgs.get("Thumbnail"),
                           imgs.get("OfferImageWide"), imgs.get("DieselStoreFrontWide")) if u]
        out.append({"store": "epic", "shop": "Epic Games", "id": e.get("id", ""), "title": e.get("title", ""), "art": art,
                    "money": _epic_money((e.get("price") or {}).get("totalPrice")),
                    "url": f"https://store.epicgames.com/p/{slug}" if slug else
                           "https://store.epicgames.com/browse?q=" + quote(e.get("title", ""))})
    return out


def epic(query):
    from .dlcfinder import _epic
    s = _epic("query($k:String,$c:String!){Catalog{searchStore(keywords:$k,category:\"games/edition/base\","
              f"count:{LIMIT},country:$c,locale:\"en-US\"){{{EPIC_FIELDS}}}}}}}", {"k": query, "c": _country()})
    return _epic_rows(s.get("elements"))


def _gog_rows(products):
    out = []
    for p in products or []:
        price = p.get("price") or {}
        final, base = price.get("finalMoney") or {}, price.get("baseMoney") or {}
        try:
            money = _money(float(final["amount"]), final.get("currency"), float(base.get("amount") or 0) or None)
        except (KeyError, TypeError, ValueError):
            money = None
        out.append({"store": "gog", "shop": "GOG", "id": str(p.get("id", "")), "title": p.get("title", ""),
                    "art": [u for u in (p.get("coverVertical"), p.get("coverHorizontal")) if u],
                    "money": money, "url": p.get("storeLink") or f"https://www.gog.com/en/game/{p.get('slug', '')}"})
    return out


def _gog(params):
    r = requests.get("https://catalog.gog.com/v1/catalog", timeout=TIMEOUT,
                     params={"limit": LIMIT, "productType": "in:game,pack", "countryCode": _country(), **params})
    r.raise_for_status()
    return _gog_rows(r.json().get("products"))


def gog(query):
    return _gog({"query": "like:" + query, "order": "desc:score"})


def _xbox_money(p):
    from .gamepass import price_parts
    amount, msrp, cur = price_parts(p)
    return _money(amount, cur, msrp) if amount is not None else None


def _xbox_rows(ids):
    from .gamepass import _image, market
    if not ids:
        return []
    r = requests.get("https://displaycatalog.mp.microsoft.com/v7.0/products", timeout=TIMEOUT,
                     params={"bigIds": ",".join(ids), "market": market(), "languages": "en-us"})
    r.raise_for_status()
    found = {}
    for p in r.json().get("Products") or []:
        props = (p.get("LocalizedProperties") or [{}])[0]
        if not props.get("ProductTitle"):
            continue
        images = props.get("Images") or []
        found[p["ProductId"]] = {"store": "xbox", "shop": "Xbox", "id": p["ProductId"], "title": props["ProductTitle"].strip(),
                                 "art": [u for u in (_image(images, "Poster", "BoxArt"), _image(images, "SuperHeroArt")) if u],
                                 "money": _xbox_money(p),
                                 "url": f"https://www.xbox.com/games/store/x/{p['ProductId']}"}
    return [found[i] for i in ids if i in found]


def xbox(query):
    from .gamepass import market
    r = requests.get("https://displaycatalog.mp.microsoft.com/v7.0/productFamilies/autosuggest", timeout=TIMEOUT,
                     params={"market": market(), "languages": "en-us", "query": query, "productFamilyNames": "Games",
                             "platformDependencyName": "Windows.Desktop"})
    r.raise_for_status()
    ids = [p["ProductId"] for fam in r.json().get("Results") or [] for p in fam.get("Products") or []
           if p.get("Type") == "Game" and p.get("ProductId")][:LIMIT]
    return _xbox_rows(ids)


SEARCHERS = {"steam": steam, "epic": epic, "gog": gog, "xbox": xbox}


def site_links(query):
    """Stores without a search Cornerplay can use: their own search page, for the browser."""
    q = quote(query)
    return [{"store": "humble", "shop": "Humble", "url": f"https://www.humblebundle.com/store/search?search={q}"},
            {"store": "amazon", "shop": "Amazon", "url": f"https://www.amazon.com/s?k={q}&i=videogames"},
            {"store": "battlenet", "shop": "Battle.net", "url": f"https://shop.battle.net/search?q={q}"}]


def search(query, stores=None) -> dict:
    """{"groups": [{"title", "art", "offers": [result, ...]}], "failed": [store ids that did not
    answer], "links": site_links}. Groups are ordered by how well the title matches, then by how
    many stores sell the game."""
    from .dlcfinder import norm
    from .search import score
    query = (query or "").strip()
    if not query:
        return {"groups": [], "failed": [], "links": []}
    wanted = [s for s in (stores or SEARCHERS) if s in SEARCHERS]
    found, failed = [], []
    with ThreadPoolExecutor(max_workers=len(wanted)) as pool:
        jobs = {pool.submit(SEARCHERS[s], query): s for s in wanted}
        for job in as_completed(jobs):
            try:
                found += job.result()
            except Exception:  # noqa: BLE001 - one store down: the others still show
                failed.append(jobs[job])
    groups = {}
    for r in found:
        if not r.get("title"):
            continue
        g = groups.setdefault(norm(r["title"]), {"title": r["title"], "art": [], "offers": []})
        if all(o["store"] != r["store"] for o in g["offers"]):
            g["offers"].append(r)
        g["art"] += [u for u in r["art"] if u not in g["art"]]
    order = {"steam": 0, "epic": 1, "gog": 2, "xbox": 3}
    for g in groups.values():
        g["offers"].sort(key=lambda o: order.get(o["store"], 9))
    _priced(found)
    out = sorted(groups.values(), key=lambda g: (-score(query, g["title"]), -len(g["offers"]), g["title"].lower()))
    return {"groups": out[:40], "failed": sorted(failed), "links": site_links(query)}


# --- browsing: one shelf per store --------------------------------------------------------------
def _steam_shelf():
    from .dlcfinder import UA
    r = requests.get("https://store.steampowered.com/api/featuredcategories",
                     params={"cc": _country(), "l": "english"}, headers=UA, timeout=TIMEOUT)
    r.raise_for_status()
    out = []
    for it in (r.json().get("specials") or {}).get("items") or []:
        p = {"final": it.get("final_price", 0), "initial": it.get("original_price") or 0, "currency": it.get("currency", "")}
        out.append({"store": "steam", "shop": "Steam", "id": str(it["id"]), "title": it.get("name", ""),
                    "art": _steam_art(it["id"]) + [u for u in (it.get("large_capsule_image"),) if u],
                    "money": _steam_money(p), "url": f"https://store.steampowered.com/app/{it['id']}"})
    return out


def _epic_shelf():
    from .dlcfinder import _epic
    s = _epic("query($c:String!){Catalog{searchStore(category:\"games/edition/base\",onSale:true,"
              f"count:{LIMIT},sortBy:\"currentPrice\",sortDir:\"DESC\",country:$c,locale:\"en-US\"){{{EPIC_FIELDS}}}}}}}",
              {"c": _country()})
    return _epic_rows(s.get("elements"))


def _gog_shelf():
    return _gog({"order": "desc:trending"})


XBOX_POPULAR = "a884932a-f02b-40c8-a903-a008c23b1df1"  # "Most popular", catalog.gamepass.com


def _xbox_shelf():
    from .gamepass import ALL_PC_GAMES, market
    def sigl(sid):
        r = requests.get("https://catalog.gamepass.com/sigls/v2", timeout=TIMEOUT,
                         params={"id": sid, "language": "en-us", "market": market()})
        r.raise_for_status()
        return [x["id"] for x in r.json() if isinstance(x, dict) and x.get("id")]
    pc = sigl(ALL_PC_GAMES)
    popular = [i for i in sigl(XBOX_POPULAR) if i in set(pc)] or pc
    return _xbox_rows(popular[:LIMIT])


SHELF_SOURCES = (("steam", "Steam", "On sale on Steam", _steam_shelf),
                 ("epic", "Epic Games", "On sale on Epic", _epic_shelf),
                 ("gog", "GOG", "Trending on GOG", _gog_shelf),
                 ("xbox", "Xbox", "Popular on Xbox for PC", _xbox_shelf))
HOMEPAGES = {"steam": "https://store.steampowered.com/", "epic": "https://store.epicgames.com/",
             "gog": "https://www.gog.com/", "xbox": "https://www.xbox.com/games/all-games/pc",
             "humble": "https://www.humblebundle.com/store", "amazon": "https://gaming.amazon.com/",
             "battlenet": "https://shop.battle.net/"}


def shelves(force=False) -> list:
    """[{"store", "shop", "title", "home", "items": [result, ...]}] for every store; a store that
    did not answer keeps its last shelf (or has none)."""
    cached = read_json(SHELVES) or {}
    if not force and time.time() - cached.get("t", 0) < SHELF_TTL and cached.get("shelves"):
        return [dict(sh, items=_priced(sh["items"])) for sh in cached["shelves"]]
    old = {s["store"]: s for s in cached.get("shelves") or []}
    out = []
    with ThreadPoolExecutor(max_workers=len(SHELF_SOURCES)) as pool:
        jobs = [(sid, shop, title, pool.submit(fn)) for sid, shop, title, fn in SHELF_SOURCES]
        for sid, shop, title, job in jobs:
            try:
                items = job.result()
            except Exception:  # noqa: BLE001
                items = (old.get(sid) or {}).get("items") or []
            out.append({"store": sid, "shop": shop, "title": title, "home": HOMEPAGES[sid], "items": items})
    write_json(SHELVES, {"t": time.time(), "shelves": out})
    return [dict(sh, items=_priced(sh["items"])) for sh in out]
