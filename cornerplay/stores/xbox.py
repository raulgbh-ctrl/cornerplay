"""Xbox and PC Game Pass.

On Linux Cornerplay does it itself (cornerplay/xodus.py): signing in (xboxauth.py), the games your
Microsoft account owns, downloads with progress, pause and resume, and playing them, through the
Xodus backend and the Nexus Runtime (both downloaded and checked on first use). Games Nexus
Launcher (cornerplay/nexus.py) installed still show and start. On Windows
through the Xbox app (cornerplay/winxbox.py). On both, the PC Game Pass catalog (gamepass.py) is
shown too, so a game can be picked here and installed: Nexus Launcher installs it on Linux, the
Microsoft Store / Xbox app on Windows. Nothing is streamed: games are installed and run locally.
"""
import os

from .. import gamepass
from ..config import settings
from ..osinfo import WINDOWS, python_argv
from ..runner import StoreError
from .base import Command, Game, Store

NEXUS_ID = "nexus-launcher"  # Linux: Nexus Launcher's own tile (open it to sign in, browse, install)


class Xbox(Store):
    id = "xbox"
    name = "Xbox / Game Pass"
    color = "#107c10"
    tile = "#107c10"  # its logo sits in white on a tile of this colour
    login_kind = "external"
    external_installs = WINDOWS  # Windows: the Xbox app installs; Linux: Cornerplay itself (xodus.py)
    dlc_note = ""

    # --- state -------------------------------------------------------------------------------
    def problem(self):
        if WINDOWS:
            return ""
        from .. import nexus
        why = nexus.unsupported()
        if why:
            return why
        missing = nexus.missing_libs()
        if missing and nexus.appimage():
            from .. import pkgs
            return "Nexus Launcher needs a few system libraries: " + "; ".join(pkgs.hint(m) for m in missing)
        return ""

    def logged_in(self):
        if WINDOWS:
            from .. import winxbox
            return winxbox.xbox_app_installed()
        from .. import nexus, xodus
        return bool(xodus.backend() and nexus.gamertag()) or bool(nexus.appimage())

    def account(self):
        if WINDOWS:
            return "through the Xbox app"
        from .. import nexus
        tag = nexus.gamertag()
        return tag if tag else ("Not signed in: press Connect" if nexus.appimage() else "")

    def login_begin(self):
        """Connect: on Linux Cornerplay signs in itself (xboxauth.py: Microsoft's page in its own
        window, "xbox_signin"); where Qt's web engine is missing it falls back to Nexus Launcher
        ("command"). On Windows open the Xbox app."""
        if WINDOWS:
            from .. import winxbox
            return {"command": winxbox.xbox_app_argv()}
        from .. import nexus
        why = nexus.unsupported()
        if why:
            raise StoreError(why)
        return {"xbox_signin": True, "command": python_argv("cornerplay.nexus", "open"), "env": nexus.env()}

    def logout(self):
        if WINDOWS:
            return
        from .. import xodus
        xodus.logout()

    def gamepass_tier(self):
        """Which Game Pass is bought ("full", "premium", "essential", "starter", "console" or ""):
        Settings > Game Pass says so, else (Linux) Nexus's answer from Microsoft. Windows has no
        way to tell Cornerplay, so there it is none until you pick one."""
        chosen = str(settings.get("gamepass_member") or "auto").lower()
        if chosen == "yes":
            return "full"
        if chosen == "no":
            return ""
        if chosen in ("premium", "essential", "starter", "full"):
            return chosen
        if WINDOWS:
            return ""
        from .. import nexus
        nexus.owned()  # refreshes the passes in the library now and then
        return nexus.gamepass_tier()

    def has_gamepass(self):
        return self.gamepass_tier() not in ("", "console")

    # --- library -----------------------------------------------------------------------------
    def _installed(self):
        if WINDOWS:
            from .. import winxbox
            return winxbox.games()
        from .. import nexus, xodus
        return xodus.games() + nexus.games()  # Cornerplay's own installs, then Nexus Launcher's

    def fetch(self):
        if not WINDOWS:
            from .. import xodus
            xodus.read_profile()  # gamertag and Game Pass, from the backend now and then
        # The catalog only once Xbox is connected (Nexus Launcher there, or the Xbox app on Windows).
        # ...and only with Game Pass bought: without it those games cannot be played.
        # ...and only the games in the tier bought (Premium and Essential have fewer PC games).
        tier = self.gamepass_tier() if settings.get("gamepass_catalog", True) and self.logged_in() else ""
        catalog = gamepass.for_tier(gamepass.catalog(), tier) if tier not in ("", "console") else []
        by_store_id = {c["id"]: c for c in catalog}
        games, have = [], set()
        if not WINDOWS:
            from .. import nexus
            if nexus.appimage() and not nexus.gamertag():  # only needed to sign in
                games.append(Game(store=self.id, id=NEXUS_ID, title="Nexus Launcher", installed=True,
                                  extra={"launcher": True, "description": "Xbox and PC Game Pass games on Linux"}))
        for g in self._installed():
            c = by_store_id.get(g.get("storeId") or "") or {}
            title = c.get("title") or g["title"]
            extra = {"store_id": g.get("storeId", ""), "gamepass": bool(c)}
            if WINDOWS:
                extra.update(app_id=g.get("appId", ""), exe=g.get("exe", ""))
            elif not g.get("ready", True):
                extra["description"] = ("Not finished downloading: press Install to carry on" if g["id"].startswith("xb-")
                                        else "Not finished installing: carry on in Nexus Launcher")
            games.append(Game(store=self.id, id=g["id"], title=title, installed=g.get("ready", True),
                              install_path=g["path"], cover=c.get("cover") or g.get("cover", ""),
                              cover_fallback=g.get("cover", ""), extra={**extra, "hero": c.get("hero") or g.get("hero", "")}))
            have.add(g.get("storeId") or "")
        if not WINDOWS:  # games this account owns but has not installed (Nexus reads them)
            from .. import nexus
            for c in gamepass.products(nexus.owned()):
                if c["id"] in have:
                    continue
                games.append(Game(store=self.id, id="own-" + c["id"], title=c["title"], installed=False,
                                  cover=c["cover"], extra={"store_id": c["id"], "owned": True, "owned_only": WINDOWS,
                                                           "gamepass": c["id"] in by_store_id, "hero": c["hero"],
                                                           "publisher": c["publisher"]}))
                have.add(c["id"])
        for c in catalog:  # PC Game Pass games not installed here: pick one, install it
            if c["id"] in have:
                continue
            games.append(Game(store=self.id, id="gp-" + c["id"], title=c["title"], installed=False, cover=c["cover"],
                              extra={"store_id": c["id"], "gamepass": True, "owned_only": WINDOWS, "hero": c["hero"],
                                     "publisher": c["publisher"], "title_id": c.get("title_id", "")}))
        if not WINDOWS:
            self._xbox_records(games)
        return games

    @staticmethod
    def _xbox_records(games):
        """Xbox title ids (for achievements) and play time from Xbox's own records, for the games
        installed or owned (not every catalog tile: one backend call per game)."""
        from .. import xodus
        mine = [g for g in games if not g.id.startswith("gp-") and g.extra.get("store_id")]
        tids = {c["id"]: c.get("title_id", "") for c in gamepass.products([g.extra["store_id"] for g in mine])}
        for g in mine:
            g.extra["title_id"] = tids.get(g.extra["store_id"], "")
        played = xodus.activity([g.extra["title_id"] for g in mine if g.extra["title_id"]]) if xodus.backend() else {}
        for g in mine:
            secs, last = played.get(g.extra["title_id"], (0, 0))
            if secs or last:  # shown like Steam's own play time (playtime.of takes the larger)
                g.extra["steam_playtime"], g.extra["steam_last_played"] = secs, last

    # --- add-ons -----------------------------------------------------------------------------
    def dlcs(self, game):
        """The game's add-ons from the Xbox store, the ones the account owns marked; on Linux an
        owned one can be downloaded for a game Cornerplay installed (xodus.install_dlc)."""
        store_id = game.extra.get("store_id") or ""
        if not store_id:
            return []
        owned, here = set(), {}
        if WINDOWS:
            pass  # the Xbox app installs add-ons; owned ones show as "owned" once Windows says so
        else:
            from .. import nexus, xodus
            owned = set(nexus.owned())
            here = ((xodus.state().get(store_id) or {}).get("dlcs") or {}) if game.id.startswith("xb-") else {}
        mine = game.id.startswith("xb-") and game.installed and not WINDOWS
        rows = []
        for a in gamepass.addons(store_id):
            status = "installed" if a["id"] in here else "owned" if a["id"] in owned else "available"
            rows.append({**a, "price": "" if status != "available" else a["price"], "status": status,
                         "canInstall": status == "owned" and mine})
        return rows

    def install_dlc(self, game, dlc_id):
        if WINDOWS:
            from .. import winxbox
            return Command(winxbox.store_page_argv(dlc_id))
        if not game.id.startswith("xb-") or not game.installed:
            raise StoreError("Install the game with Cornerplay first")
        return Command(python_argv("cornerplay.xodus", "install-dlc", game.id[3:], dlc_id))

    # --- actions -----------------------------------------------------------------------------
    def install(self, game):
        if WINDOWS:
            from .. import winxbox
            store_id = game.extra.get("store_id") or ""
            return Command(winxbox.store_page_argv(store_id) if store_id else winxbox.xbox_app_argv())
        # Linux: Cornerplay downloads it (xodus.py), with the backend and runtime on first use.
        from .. import xodus
        store_id = game.extra.get("store_id") or ""
        if not store_id:
            raise StoreError("Cornerplay does not know this game's Store id")
        folder = game.install_path or os.path.join(str(settings.games_dir), "Xbox", _folder_name(game.title))
        return Command(python_argv("cornerplay.xodus", "install", store_id, folder, game.title))

    def uninstall(self, game):
        if WINDOWS:
            raise StoreError(f"Uninstall {game.title} from the Xbox app (or Windows Settings > Apps)")
        if not game.id.startswith("xb-"):
            raise StoreError(f"Uninstall {game.title} from Nexus Launcher, which installed it")
        from .. import xodus
        return Command(python_argv("cornerplay.xodus", "uninstall", game.id[3:]))

    def update(self, game):
        if WINDOWS or not game.id.startswith("xb-"):
            return self.install(game)  # the Xbox app / Nexus keep their games up to date themselves
        return self.install(game)  # streaming carries on and updates the files in place

    def launch(self, game):
        if WINDOWS:
            from .. import winxbox
            if not game.extra.get("app_id"):
                raise StoreError("Cornerplay does not know how to start this game; start it from the Xbox app")
            return Command(winxbox.launch_argv(game.id, game.extra["app_id"]))
        if game.id.startswith("xb-"):  # installed by Cornerplay: it starts it too
            return Command(python_argv("cornerplay.xodus", "play", game.id[3:]), cwd=os.path.expanduser("~"))
        from .. import nexus
        if not nexus.appimage():
            raise StoreError("Nexus Launcher is not installed: connect Xbox / Game Pass under Accounts")
        if game.id == NEXUS_ID:
            return Command(nexus.argv(), env=nexus.env())
        return Command(nexus.argv(game.id), env=nexus.env(), cwd=os.path.expanduser("~"))


def _folder_name(title: str) -> str:
    import re
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", title).strip(" .") or "Game"
