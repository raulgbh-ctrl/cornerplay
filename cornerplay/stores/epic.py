"""Epic Games Store through the legendary CLI."""
import json
import os

import time
from pathlib import Path

from ..config import CACHE_DIR, XDG_CONFIG, find_tool, read_json, settings, write_json
from ..runner import StoreError, wine_env, wrapper_string
from .base import Command, Game, PartialResult, Store, run

LOGIN_URL = "https://legendary.gl/epiclogin"


class Epic(Store):
    id = "epic"
    name = "Epic Games"
    color = "#9aa0aa"
    tile = "#3b3b3f"  # its logo sits in white on a tile of this colour
    dlc_note = ""

    def tool(self):
        t = find_tool("legendary")
        if not t:
            raise StoreError(self.problem())
        return t

    def problem(self):
        return "" if find_tool("legendary") else "legendary not found (run: cornerplay --fetch-backends)"

    def _user(self):
        return read_json(XDG_CONFIG / "legendary/user.json") or {}

    def logged_in(self):
        return bool(self._user())

    def account(self):
        return self._user().get("displayName", "")

    def login_begin(self):
        self.tool()
        return {
            "url": LOGIN_URL,
            "prompt": "Sign in to Epic in your browser. The page then shows a short JSON "
                      "block: paste its authorizationCode value (or the whole block) here.",
        }

    def login_finish(self, text):
        text = text.strip()
        if text.startswith("{"):
            try:
                text = json.loads(text).get("authorizationCode") or ""
            except ValueError:
                pass
        code = text.strip().strip('"')
        if not code:
            raise StoreError("No authorization code found in what you pasted")
        r = run([self.tool(), "auth", "--code", code], timeout=90)
        if not self.logged_in():
            raise StoreError(_tail(r) or "Epic sign-in failed")

    def logout(self):
        run([self.tool(), "auth", "--delete"], timeout=30)

    def _installed(self):
        r = run([self.tool(), "list-installed", "--json"], timeout=60)
        try:
            return {g["app_name"]: g for g in json.loads(r.stdout or "[]")}
        except ValueError:
            return {}

    def fetch(self, force=False):
        installed = self._installed()
        games = {}
        error = ""
        if self.logged_in():
            argv = [self.tool(), "list", "--json"]
            stamp = CACHE_DIR / "epic_full_refresh.json"
            if force or time.time() - (read_json(stamp) or {}).get("t", 0) > 7 * 86400:
                argv.append("--force-refresh")  # Refresh button, else weekly: new games, art and details
            r = run(argv, timeout=300)
            if r.returncode == 0 and "--force-refresh" in argv:
                write_json(stamp, {"t": time.time()})
            try:
                listing = json.loads(r.stdout)
            except ValueError:
                listing, error = [], _tail(r) or "could not read the Epic library"
            for g in listing:
                if not g.get("asset_infos"):
                    continue  # third-party-store titles legendary cannot install
                cats = {c.get("path") for c in (g.get("metadata") or {}).get("categories") or [] if isinstance(c, dict)}
                if "digitalextras" in cats and not installed.get(g["app_name"]):
                    continue  # soundtracks, art books, wallpapers (Death Stranding Content)
                app = g["app_name"]
                tall, wide, hero, logo = _images(g.get("metadata") or {})
                inst = installed.get(app)
                games[app] = Game(
                    store=self.id, id=app, title=(g.get("app_title") or app).strip(),
                    cover=tall or wide, cover_fallback=wide,
                    installed=bool(inst), install_path=(inst or {}).get("install_path", ""),
                    extra={"dlcs": [{"id": d.get("app_name", ""), "title": (d.get("app_title") or "").strip(),
                                     "cid": (d.get("metadata") or {}).get("id", ""),
                                     "image": _images(d.get("metadata") or {})[1]}
                                    for d in g.get("dlcs") or []],
                           "store_heroes": [hero] if hero else [], "store_logos": [logo] if logo else [],
                           "description": ((g.get("metadata") or {}).get("description") or "")[:600],
                           "epic_ns": (g.get("metadata") or {}).get("namespace", ""),
                           "source": "account"},
                )
        for app, inst in installed.items():
            if app not in games and not inst.get("is_dlc"):
                games[app] = Game(store=self.id, id=app, title=inst.get("title", app),
                                  installed=True, install_path=inst.get("install_path", ""),
                                  extra={"source": "installed"})
        for app, inst in installed.items():
            if app in games:
                games[app].extra["size"] = int(inst.get("install_size", 0) or 0)
        for app in _updates(installed):
            if app in games:
                games[app].extra["update"] = True
        if error:
            raise PartialResult(list(games.values()), f"Epic: {error}")
        return list(games.values())

    _inst_cache = (0.0, {})

    def _installed_recent(self):
        """list-installed, kept for 30 s: the DLC list of every game page asks, and each call
        starts legendary (about a second)."""
        t, hit = self._inst_cache
        if time.time() - t > 30:
            hit = self._installed()
            self._inst_cache = (time.time(), hit)
        return hit

    def dlcs(self, game):
        """Every add-on the Epic store sells for the game, with the ones you own marked; owned DLC the
        store no longer sells are kept too."""
        installed = self._installed_recent()
        mine = game.extra.get("dlcs") or []
        rows, seen = [], set()
        from ..dlcfinder import epic_find, epic_rows, find
        from ..net import requests
        try:
            # the namespace comes with the library (from the next refresh on); else found by title
            ns = game.extra.get("epic_ns") or find("epic", game.title, epic_find)
            if ns:
                rows, seen = epic_rows(ns, {d["cid"]: d["id"] for d in mine if d.get("cid")},
                                       installed, game.installed)
        except (requests.RequestException, ValueError):
            rows, seen = [], set()  # the store is unreachable: the DLC you own still show
        if not any(d.get("cid") for d in mine):  # a library from before catalog ids were kept
            have = {d["title"].lower(): d for d in mine}
            for r in rows:
                d = have.get(r["title"].lower())
                if d and r["status"] == "available":
                    r.update(id=d["id"], price="", status="installed" if d["id"] in installed else "owned",
                             canInstall=d["id"] not in installed and game.installed)
                    seen.add(d.get("cid") or d["id"])
            seen |= {have[r["title"].lower()]["id"] for r in rows if r["title"].lower() in have}
        for d in mine:
            if d.get("cid") in seen or d["id"] in seen:
                continue
            status = "installed" if d["id"] in installed else "owned"
            rows.append({"id": d["id"], "title": d["title"] or d["id"], "status": status,
                         "image": d.get("image", ""), "price": "", "url": "",
                         "canInstall": status == "owned" and game.installed})
        return rows

    def changed(self):
        self._inst_cache = (0.0, {})

    def install_dlc(self, game, dlc_id):
        self._inst_cache = (0.0, {})  # it changes now
        if not game.installed:
            raise StoreError("Install the game first")
        return Command([self.tool(), "-y", "install", dlc_id])

    def install(self, game, base=None, dlcs=None):
        """base: the folder the game's own folder goes in (the Install window can pick another);
        dlcs: True/False to install the owned DLCs or not, None for legendary's own choice."""
        base = Path(base) if base else settings.games_dir / "epic"
        base.mkdir(parents=True, exist_ok=True)
        argv = [self.tool(), "-y", "install", game.id, "--base-path", str(base)]
        if dlcs is not None:
            argv.append("--with-dlcs" if dlcs else "--skip-dlcs")
        return Command(argv)

    def uninstall(self, game):
        return Command([self.tool(), "-y", "uninstall", game.id])

    def update(self, game):
        return Command([self.tool(), "-y", "update", game.id])

    def verify(self, game):
        return Command([self.tool(), "-y", "repair", game.id])

    def launch(self, game):
        """Blocking: asks legendary for the launch details so Cornerplay can run (and wait for) the game itself."""
        env = wine_env(self.id, game.id)
        base = [self.tool(), "launch", game.id, "--no-wine", "--wrapper", wrapper_string(), "--json"]
        r = run(base, timeout=90, env=env)
        if r.returncode != 0:  # offline, or Epic unreachable: legendary can still start most games
            r = run(base + ["--offline"], timeout=60, env=env)
        try:
            p = json.loads(r.stdout)
        except ValueError:
            raise StoreError(_tail(r) or "legendary could not prepare the launch")
        exe = os.path.join(p.get("game_directory", ""), p.get("game_executable", ""))
        argv = [*p.get("launch_command", []), exe, *p.get("game_parameters", []),
                *p.get("user_parameters", []), *p.get("egl_parameters", [])]
        env.update({k: str(v) for k, v in (p.get("environment") or {}).items()})
        return Command(argv, env=env, cwd=p.get("working_directory") or p.get("game_directory", ""))


def _updates(installed):
    """Installed games whose version differs from Epic's latest build.

    `legendary list` (run by fetch) refreshes assets.json with each game's newest
    build_version; this is the same comparison `legendary list-installed --check-updates` makes.
    """
    latest = {}
    for platform, items in (read_json(XDG_CONFIG / "legendary/assets.json") or {}).items():
        for a in items or []:
            latest[(platform, a.get("app_name"))] = a.get("build_version")
    out = set()
    for app, inst in installed.items():
        newest = latest.get((inst.get("platform") or "Windows", app))
        if newest and inst.get("version") and newest != inst["version"]:
            out.add(app)
    return out


def _images(meta):
    """(portrait cover, wide fallback, wide banner, logo) from Epic's key images."""
    tall = wide = hero = logo = ""
    for img in meta.get("keyImages") or []:
        kind, url = img.get("type"), img.get("url", "")
        if kind == "DieselGameBoxTall":
            tall = url + ("&" if "?" in url else "?") + "h=600&resize=1&w=400"
        elif kind in ("DieselGameBox", "Thumbnail") and not wide:
            wide = url
        if kind == "DieselGameBox":
            hero = url + ("&" if "?" in url else "?") + "w=1920&resize=1"  # 16:9 key art
        elif kind == "DieselGameBoxLogo":
            logo = url
    return tall, wide, hero, logo


def _tail(r, n=3):
    lines = [l for l in ((r.stderr or "") + (r.stdout or "")).splitlines() if l.strip()]
    return " ".join(lines[-n:])[-300:]
