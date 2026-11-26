"""One currency for the Store page: each store prices in its own (Epic in lei, GOG in dollars, Steam
in euros for the same country), so prices are converted to the one you read in.

The rates are the European Central Bank's reference rates (published each working day, about
30 currencies against the euro), kept for 12 hours. A converted price is marked "≈": the store
charges its own price in its own currency.

Settings > Library > Store prices in: "auto" (euros in Europe, dollars elsewhere), "EUR" or "USD".
"""
import re
import time

from .config import CACHE_DIR, read_json, settings, write_json
from .net import requests

ECB = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
CACHE = CACHE_DIR / "ecb-rates.json"
TTL = 12 * 3600
EUROPE = set("AD AL AT BA BE BG BY CH CY CZ DE DK EE ES FI FO FR GB GI GR HR HU IE IS IT LI LT LU LV MC MD ME "
             "MK MT NL NO PL PT RO RS SE SI SK SM UA VA XK".split())


def target() -> str:
    chosen = str(settings.get("store_currency") or "auto").upper()
    if chosen in ("EUR", "USD"):
        return chosen
    from .dlcfinder import country
    return "EUR" if country().upper() in EUROPE else "USD"


def rates() -> dict:
    """{currency: units per euro}, "EUR" included; {} when never fetched and offline."""
    cached = read_json(CACHE) or {}
    if time.time() - cached.get("t", 0) < TTL and cached.get("rates"):
        return cached["rates"]
    try:
        r = requests.get(ECB, timeout=15)
        r.raise_for_status()
        found = {c: float(v) for c, v in re.findall(r"currency=['\"]([A-Z]{3})['\"]\s+rate=['\"]([0-9.]+)['\"]", r.text)}
    except (requests.RequestException, ValueError):
        found = {}
    if not found:
        return cached.get("rates") or {}
    found["EUR"] = 1.0
    write_json(CACHE, {"t": time.time(), "rates": found})
    return found


def convert(amount, cur: str, to: str, table=None):
    """amount in cur, in to; None when a rate is missing."""
    if amount is None:
        return None
    cur, to = (cur or "").upper(), (to or "").upper()
    if cur == to:
        return float(amount)
    table = rates() if table is None else table
    if cur not in table or to not in table:
        return None
    return float(amount) / table[cur] * table[to]


def text(amount, cur: str, base=None, to: str = "", table=None) -> str:
    """'$9.99 (-50%)', '≈ €9.12 (-50%)' when converted, 'Free', or the store's own price when it
    cannot be converted. base: the price before a discount (same currency)."""
    from .itad import money
    if amount is None:
        return ""
    if float(amount) == 0:
        return "Free"
    to = to or target()
    value = convert(amount, cur, to, table)
    shown = money({"amount": value, "currency": to}) if value is not None else money({"amount": float(amount), "currency": cur})
    if value is not None and (cur or "").upper() != to:
        shown = "≈ " + shown
    if base and float(base) > float(amount):
        shown += f" (-{round(100 - 100 * float(amount) / float(base))}%)"
    return shown
