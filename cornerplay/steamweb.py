"""Your Steam account through its web sign-in, for when there is no Web API key.

Signing in to Steam in Cornerplay's sign-in window leaves the cookies of a normal Steam web
session (steampowered.com, steamcommunity.com, login.steampowered.com). Kept in
~/.config/cornerplay/steam_web.json, readable only by you; the password is never seen.

With them Cornerplay asks the Steam store for the same short-lived web API token its own
pages use (pointssummary/ajaxgetasyncconfig), and with that token reads:
  - the games the account owns (IPlayerService/GetOwnedGames, as with a key);
  - the games Steam Family lends it (IFamilyGroupsService/GetSharedLibraryApps).
When the token has run out, login.steampowered.com/jwt/refresh renews the store session from
the long-lived refresh cookie, like a browser does.
"""
import json
import re
import time
from urllib.parse import unquote

from .config import CACHE_DIR, CONFIG_DIR, read_json, write_json, write_private
from .net import requests

AUTH_FILE = CONFIG_DIR / "steam_web.json"
NAMES_FILE = CACHE_DIR / "steam_people.json"   # steamid -> profile name (the family members lending games)
LOGIN_URL = "https://store.steampowered.com/login/?redir=account%2F"
DOMAINS = ("steampowered.com", "steamcommunity.com")
API = "https://api.steampowered.com"
TOKEN_URL = "https://store.steampowered.com/pointssummary/ajaxgetasyncconfig"
REFRESH_URL = "https://login.steampowered.com/jwt/refresh?redir=https%3A%2F%2Fstore.steampowered.com%2F"


class NotSignedIn(Exception):
    """No Steam web session, or Steam no longer accepts it (sign in again)."""


def ours(domain: str) -> bool:
    return domain.lstrip(".").endswith(DOMAINS)


def _load():
    return read_json(AUTH_FILE) or {}


def signed_in() -> bool:
    return bool(_load().get("cookies"))


def account() -> str:
    return _load().get("account", "")


def steamid() -> str:
    """The account's 64-bit id, from the steamLoginSecure cookie ("<steamid>||<token>")."""
    for c in _load().get("cookies") or []:
        if c.get("name") == "steamLoginSecure":
            sid = unquote(c.get("value", "")).split("||")[0]
            if sid.isdigit():
                return sid
    return ""


def save(cookies: list, account_name: str = ""):
    """cookies: [{"name", "value", "domain", "path"}] collected by the sign-in window."""
    keep = [c for c in cookies if ours(c.get("domain", ""))]
    if not any(c.get("name") == "steamLoginSecure" for c in keep):
        raise NotSignedIn("Steam did not keep you signed in; try again")
    write_private(AUTH_FILE, json.dumps({"cookies": keep, "account": account_name, "t": time.time()}))


def forget():
    AUTH_FILE.unlink(missing_ok=True)


def _session(cookies):
    s = requests.Session()
    s.headers["User-Agent"] = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
    for c in cookies:
        s.cookies.set(c["name"], c["value"], domain=c.get("domain", ""), path=c.get("path") or "/")
    return s


def _ask_token(s):
    r = s.get(TOKEN_URL, timeout=20)
    r.raise_for_status()
    data = r.json().get("data")
    return data.get("webapi_token", "") if isinstance(data, dict) else ""


def token() -> str:
    """A web API access token for the signed-in account. Raises NotSignedIn."""
    auth = _load()
    if not auth.get("cookies"):
        raise NotSignedIn("Not signed in to Steam")
    s = _session(auth["cookies"])
    tok = _ask_token(s)
    if not tok:  # the store session ran out: renew it from the refresh cookie
        s.get(REFRESH_URL, timeout=20)
        tok = _ask_token(s)
        if not tok:
            raise NotSignedIn("Steam wants you to sign in again")
        auth["cookies"] = [{"name": c.name, "value": c.value, "domain": c.domain, "path": c.path}
                           for c in s.cookies if ours(c.domain)]
        write_private(AUTH_FILE, json.dumps(auth))
    return tok


def _get(path, params, timeout=20):
    r = requests.get(f"{API}/{path}", params=params, timeout=timeout)
    if r.status_code in (401, 403):
        raise NotSignedIn("Steam wants you to sign in again")
    r.raise_for_status()
    return r.json().get("response") or {}


def owned(tok: str, sid: str) -> list:
    """[{"appid", "name", "playtime_forever", "rtime_last_played"}] the account owns."""
    return _get("IPlayerService/GetOwnedGames/v1/", {
        "access_token": tok, "steamid": sid, "include_appinfo": 1, "include_played_free_games": 1,
    }).get("games") or []


def lent(tok: str, sid: str) -> list:
    """Games other members of the account's Steam Family share with it:
    [{"appid", "name", "owners": [steamid, ...]}]; [] when not in a family."""
    group = _get("IFamilyGroupsService/GetFamilyGroupForUser/v1/", {"access_token": tok, "steamid": sid})
    gid = group.get("family_groupid")
    if not gid or str(gid) == "0":
        return []
    apps = _get("IFamilyGroupsService/GetSharedLibraryApps/v1/", {
        "access_token": tok, "family_groupid": gid, "steamid": sid,
        "include_own": "false", "include_excluded": "false", "include_free": "false", "include_non_games": "false",
    }).get("apps") or []
    out = []
    for a in apps:
        owners = [str(o) for o in a.get("owner_steamids") or [] if str(o) != sid]
        if owners and a.get("appid") and a.get("name") and not a.get("exclude_reason"):
            out.append({"appid": str(a["appid"]), "name": a["name"], "owners": owners})
    return out


def person(sid: str) -> str:
    """A Steam profile's name (public profile XML, remembered), or ""."""
    names = read_json(NAMES_FILE) or {}
    if sid in names:
        return names[sid]
    name = ""
    try:
        r = requests.get(f"https://steamcommunity.com/profiles/{sid}/", params={"xml": 1}, timeout=10)
        m = re.search(r"<steamID><!\[CDATA\[(.*?)\]\]></steamID>", r.text or "")
        name = m.group(1).strip() if m else ""
    except requests.RequestException:
        return ""
    names[sid] = name
    write_json(NAMES_FILE, names)
    return name
