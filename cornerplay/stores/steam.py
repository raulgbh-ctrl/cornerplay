"""Steam: reads the local client's libraries; installs and launches via steam:// URLs."""
import glob
import os
from pathlib import Path

from ..net import redact, requests

from .. import host, pkgs
from .. import vdf
import json

from ..config import HOME, settings
from ..runner import StoreError
from .base import Command, Game, PartialResult, Store

FLATPAK_ID = "com.valvesoftware.Steam"
ROOTS = [
    HOME / ".local/share/Steam",
    HOME / ".steam/steam",
    HOME / ".steam/root",
    HOME / f".var/app/{FLATPAK_ID}/.local/share/Steam",
    HOME / "snap/steam/common/.local/share/Steam",  # Ubuntu's Snap Steam
    HOME / f".var/app/{FLATPAK_ID}/data/Steam",
]
# Runtimes and tools that live in steamapps but are not games.
TOOL_IDS = {"228980", "1070560", "1391110", "1628350", "1493710"}
TOOL_PREFIXES = ("Proton ", "Steam Linux Runtime", "Steamworks Common", "Steam Controller Configs")
CDN = "https://cdn.cloudflare.steamstatic.com/steam/apps"


class Steam(Store):
    id = "steam"
    name = "Steam"
    color = "#66c0f4"
    tile = "#2a5d8a"  # its logo sits in white on a tile of this colour
    dlc_note = ("Steam installs the DLC you own by itself. Cornerplay can only see which DLC is installed; "
                "open the others in Steam to buy or install them.")
    external_installs = True
    login_kind = "external"

    _root = (0.0, None)  # (when, path): asked hundreds of times at start-up, the disk once a minute

    def root(self):
        import time
        when, path = Steam._root
        if time.time() - when < 60:
            return path
        path = next((r.resolve() for r in ROOTS if (r / "steamapps").is_dir() or (r / "config").is_dir()), None)
        Steam._root = (time.time(), path)
        return path

    def client(self):
        exe = host.which("steam")
        if not exe and not host.IN_FLATPAK and os.access("/usr/games/steam", os.X_OK):
            exe = "/usr/games/steam"  # Debian/Ubuntu's place, not always on PATH from a menu
        if exe:
            return host.argv([exe])
        # Flathub's Steam: run once (its data folder), or installed but not started yet
        # (a finished install has a "current" link; a failed one leaves an empty folder)
        installed = [HOME / f".var/app/{FLATPAK_ID}", HOME / f".local/share/flatpak/app/{FLATPAK_ID}/current",
                     Path(f"/var/lib/flatpak/app/{FLATPAK_ID}/current")]
        if host.which("flatpak") and any(p.exists() for p in installed):
            return host.argv(["flatpak", "run", FLATPAK_ID])
        return None

    def problem(self):
        return "" if self.client() else f"Steam is not installed ({pkgs.hint('steam')})"

    def _users(self) -> dict:
        root = self.root()
        if not root:
            return {}
        return vdf.load(root / "config/loginusers.vdf").get("users", {})

    def _recent_user(self):
        users = self._users()
        for sid, u in users.items():
            if u.get("MostRecent") == "1" or u.get("mostrecent") == "1":
                return sid, u
        return next(iter(users.items()), (None, {}))

    def logged_in(self):
        return bool(self._users())

    def account(self):
        return self._recent_user()[1].get("PersonaName", "")

    def login_begin(self):
        client = self.client()
        if not client:
            raise StoreError(self.problem())
        return {"command": client}

    def library_dirs(self):
        root = self.root()
        if not root:
            return []
        dirs = {str(root)}
        folders = vdf.load(root / "steamapps/libraryfolders.vdf").get("libraryfolders", {})
        for entry in folders.values():
            if isinstance(entry, dict) and entry.get("path"):
                dirs.add(os.path.realpath(entry["path"]))
        return sorted(dirs)

    def _local_cover(self, appid):
        root = self.root()
        if not root:
            return ""
        cache = root / "appcache/librarycache"
        for cand in (cache / f"{appid}_library_600x900.jpg", cache / appid / "library_600x900.jpg"):
            if cand.is_file():
                return cand.as_uri()
        hits = glob.glob(str(cache / appid / "*" / "library_600x900.jpg"))
        return "file://" + hits[0] if hits else ""

    def _local_hero(self, appid):
        """Steam's own cached banner for a game, if the client has downloaded it."""
        root = self.root()
        if not root:
            return ""
        cache = root / "appcache/librarycache"
        for cand in (cache / f"{appid}_library_hero.jpg", cache / appid / "library_hero.jpg"):
            if cand.is_file():
                return cand.as_uri()
        hits = glob.glob(str(cache / appid / "*" / "library_hero.jpg"))
        return "file://" + hits[0] if hits else ""

    def _game(self, appid, title, installed=False, path=""):
        hero = self._local_hero(appid)
        return Game(
            store=self.id, id=appid, title=title, installed=installed, install_path=path,
            cover=self._local_cover(appid) or f"{CDN}/{appid}/library_600x900.jpg",
            cover_fallback=f"{CDN}/{appid}/header.jpg",
            extra={"store_heroes": [hero]} if hero else {},
        )

    def fetch(self):
        games = {}
        for lib in self.library_dirs():
            for acf in glob.glob(os.path.join(lib, "steamapps", "appmanifest_*.acf")):
                st = vdf.load(acf).get("AppState", {})
                appid, name = st.get("appid"), st.get("name", "")
                if not appid or appid in TOOL_IDS or name.startswith(TOOL_PREFIXES):
                    continue
                try:
                    done = int(st.get("StateFlags", "0")) & 4 != 0
                except ValueError:
                    done = False
                path = os.path.join(lib, "steamapps", "common", st.get("installdir", ""))
                games[appid] = self._game(appid, name or f"App {appid}", done, path)
                games[appid].extra["source"] = "installed"  # "account" once the Web API lists it
                try:
                    games[appid].extra["size"] = int(st.get("SizeOnDisk", 0) or 0)
                except ValueError:
                    pass
                depots = st.get("InstalledDepots", {})
                games[appid].extra["dlc_installed"] = sorted(
                    {d["dlcappid"] for d in depots.values() if isinstance(d, dict) and d.get("dlcappid")})

        # Owned-but-not-installed games come only from the account itself, through the Web
        # API (optional key in Settings). Steam's local caches are not used for this: appinfo.vdf
        # also names every store page, wishlisted or friend's game the client has looked at,
        # and packageinfo.vdf keeps giveaways that were never claimed, so they listed games
        # the account does not own.
        # Two ways in: the Web API key in Settings, or signing in to Steam in Cornerplay
        # (steamweb.py: the web session's own token, which also reads Steam Family's games).
        from .. import steamweb
        key = settings.get("steam_api_key").strip()
        steamid = settings.get("steam_id").strip() or steamweb.steamid() or self._recent_user()[0]

        def add_owned(rows):
            for g in rows:
                appid = str(g.get("appid", ""))
                if appid in games:
                    games[appid].extra["source"] = "account"
                elif appid and appid not in TOOL_IDS and g.get("name"):
                    games[appid] = self._game(appid, g["name"])
                    games[appid].extra["source"] = "account"

        problem = ""
        try:
            if key and steamid:
                r = requests.get(
                    "https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/",
                    params={"key": key, "steamid": steamid, "include_appinfo": 1,
                            "include_played_free_games": 1, "format": "json"},
                    timeout=20,
                )
                r.raise_for_status()
                add_owned(r.json().get("response", {}).get("games", []))
            if steamweb.signed_in():
                tok, sid = steamweb.token(), steamweb.steamid() or steamid
                if not (key and steamid):
                    add_owned(steamweb.owned(tok, sid))
                self._add_lent(games, steamweb.lent(tok, sid), steamweb.person)
        except steamweb.NotSignedIn as e:
            problem = f"Steam: {e}"
        except (requests.RequestException, ValueError) as e:
            problem = f"Steam Web API: {redact(e)}"
        if problem:
            self._add_playtime(games)
            self._mark_hidden(games, steamid)
            raise PartialResult(list(games.values()), problem)
        self._add_playtime(games)
        self._mark_hidden(games, steamid)
        return list(games.values())

    def _add_lent(self, games, rows, name_of):
        """Steam Family's games: listed as lent, with who lends them (extra["lender"])."""
        for a in rows:
            appid = a["appid"]
            g = games.get(appid)
            if g is not None and g.extra.get("source") == "account":
                continue  # owned as well: yours
            if g is None:
                if appid in TOOL_IDS:
                    continue
                g = games[appid] = self._game(appid, a["name"])
            g.extra["source"] = "lent"
            g.extra["lender"] = ", ".join(n for n in (name_of(o) for o in a["owners"][:2]) if n)

    def _mark_hidden(self, games, steamid):
        """Games hidden in Steam's library get extra["steam_hidden"]; Cornerplay then keeps
        them under "Hidden games" too. Steam syncs its collections through the cloud into
        userdata/<id>/config/cloudstorage/cloud-storage-namespace-1.json."""
        root = self.root()
        try:
            account = int(steamid) - 76561197960265728
        except (TypeError, ValueError):
            return
        path = root / "userdata" / str(account) / "config" / "cloudstorage" / "cloud-storage-namespace-1.json" if root else None
        try:
            entries = json.loads(path.read_text()) if path else []
        except (OSError, ValueError):
            return
        hidden = set()
        for key, entry in entries:
            if key == "user-collections.hidden" and isinstance(entry, dict) and not entry.get("is_deleted"):
                try:
                    hidden = {str(a) for a in json.loads(entry.get("value") or "{}").get("added", [])}
                except ValueError:
                    pass
        for appid, g in games.items():
            if appid in hidden:
                g.extra["steam_hidden"] = True

    def _add_playtime(self, games):
        """Steam's own playtime record (localconfig.vdf of the signed-in account)."""
        root, steamid = self.root(), settings.get("steam_id").strip() or self._recent_user()[0]
        if not root or not steamid:
            return
        try:
            account = int(steamid) - 76561197960265728
        except ValueError:
            return
        conf = vdf.load(root / "userdata" / str(account) / "config" / "localconfig.vdf")
        node = conf
        for name in ("UserLocalConfigStore", "Software", "Valve", "Steam", "apps"):
            node = next((v for k, v in node.items() if k.lower() == name.lower() and isinstance(v, dict)), {})
        for appid, app in node.items():
            g = games.get(appid)
            if g is None or not isinstance(app, dict):
                continue
            try:
                g.extra["steam_playtime"] = int(app.get("Playtime", 0)) * 60
                g.extra["steam_last_played"] = int(app.get("LastPlayed", 0))
            except ValueError:
                pass

    def dlcs(self, game):
        try:  # no country given: Steam answers in the player's own currency
            r = requests.get("https://store.steampowered.com/api/dlcforapp/",
                             params={"appid": game.id, "l": "english"}, timeout=20)
            r.raise_for_status()
            items = r.json().get("dlc") or []
        except (requests.RequestException, ValueError) as e:
            raise StoreError(f"Could not reach the Steam store ({type(e).__name__})")
        have = set(game.extra.get("dlc_installed") or [])
        client = bool(self.client())
        rows = []
        for d in items:
            did = str(d.get("id"))
            rows.append({"id": did, "title": d.get("name", did),
                         "status": "installed" if did in have else "missing",  # owned or not: Steam does not say
                         "image": d.get("header_image", ""), "price": _price(d.get("price_overview")),
                         # the Steam client opens on the DLC's page, where it can be bought or installed
                         "url": f"steam://store/{did}" if client else f"https://store.steampowered.com/app/{did}",
                         "canInstall": False})
        return rows

    def _url(self, url):
        client = self.client()
        if not client:
            raise StoreError(self.problem())
        return Command([*client, url])

    def install(self, game):
        return self._url(f"steam://install/{game.id}")

    def uninstall(self, game):
        return self._url(f"steam://uninstall/{game.id}")

    def launch(self, game):
        return self._url(f"steam://rungameid/{game.id}")


CURRENCY = {"USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥", "BRL": "R$", "AUD": "A$", "CAD": "C$", "RUB": "₽"}


def _price(p):
    """ "€39.99", "€9.99 (-50%)", "Free", or "" when there is no price."""
    if not p:
        return ""
    final = p.get("final", 0) / 100
    if not final:
        return "Free"
    cur = p.get("currency", "")
    text = f"{CURRENCY.get(cur, '')}{final:.2f}" + ("" if cur in CURRENCY else f" {cur}")
    return text + (f" (-{p['discount_percent']}%)" if p.get("discount_percent") else "")
