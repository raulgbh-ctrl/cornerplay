"""Xbox and PC Game Pass.

On Linux through Nexus Launcher (cornerplay/nexus.py; built on Xodus, unofficial): Cornerplay
installs it by itself when you connect, then lists and starts the games it installed. On Windows
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
    external_installs = True  # Nexus Launcher / the Xbox app install; Cornerplay sees the result
    dlc_note = "Add-ons are installed from Nexus Launcher (Linux) or the Xbox app (Windows)."

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
        from .. import nexus
        return bool(nexus.appimage())

    def account(self):
        if WINDOWS:
            return "through the Xbox app"
        from .. import nexus
        tag = nexus.gamertag()
        return f"{tag} · Nexus Launcher" if tag else ("Nexus Launcher installed; sign in inside it" if nexus.appimage() else "")

    def login_begin(self):
        """Connect: on Linux install Nexus Launcher (when it is not there yet) and open it to sign
        in; on Windows open the Xbox app."""
        if WINDOWS:
            from .. import winxbox
            return {"command": winxbox.xbox_app_argv()}
        from .. import nexus
        why = nexus.unsupported()
        if why:
            raise StoreError(why)
        return {"command": python_argv("cornerplay.nexus", "open"), "env": nexus.env()}

    # --- library -----------------------------------------------------------------------------
    def _installed(self):
        if WINDOWS:
            from .. import winxbox
            return winxbox.games()
        from .. import nexus
        return nexus.games()

    def fetch(self):
        # The catalog only once Xbox is connected (Nexus Launcher there, or the Xbox app on Windows).
        catalog = gamepass.catalog() if settings.get("gamepass_catalog", True) and self.logged_in() else []
        by_store_id = {c["id"]: c for c in catalog}
        games, have = [], set()
        if not WINDOWS:
            from .. import nexus
            if nexus.appimage():
                games.append(Game(store=self.id, id=NEXUS_ID, title="Nexus Launcher", installed=True,
                                  extra={"launcher": True, "description": "Xbox and PC Game Pass games on Linux"}))
        for g in self._installed():
            c = by_store_id.get(g.get("storeId") or "") or {}
            title = c.get("title") or g["title"]
            extra = {"store_id": g.get("storeId", ""), "gamepass": bool(c)}
            if WINDOWS:
                extra.update(app_id=g.get("appId", ""), exe=g.get("exe", ""))
            elif not g.get("ready", True):
                extra["description"] = "Not finished installing: carry on in Nexus Launcher"
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
                                  cover=c["cover"], extra={"store_id": c["id"], "owned": True, "owned_only": True,
                                                           "gamepass": c["id"] in by_store_id, "hero": c["hero"],
                                                           "publisher": c["publisher"]}))
                have.add(c["id"])
        for c in catalog:  # PC Game Pass games not installed here: pick one, install it
            if c["id"] in have:
                continue
            games.append(Game(store=self.id, id="gp-" + c["id"], title=c["title"], installed=False, cover=c["cover"],
                              extra={"store_id": c["id"], "gamepass": True, "owned_only": True, "hero": c["hero"],
                                     "publisher": c["publisher"]}))
        return games

    # --- actions -----------------------------------------------------------------------------
    def install(self, game):
        if WINDOWS:
            from .. import winxbox
            store_id = game.extra.get("store_id") or ""
            return Command(winxbox.store_page_argv(store_id) if store_id else winxbox.xbox_app_argv())
        # Linux: Nexus Launcher (installed now if it is not there) has the Store and the install queue.
        from .. import nexus
        why = nexus.unsupported()
        if why:
            raise StoreError(why)
        return Command(python_argv("cornerplay.nexus", "open"), env=nexus.env())

    def uninstall(self, game):
        where = "the Xbox app (or Windows Settings > Apps)" if WINDOWS else "Nexus Launcher (right-click the game > Uninstall)"
        raise StoreError(f"Uninstall {game.title} from {where}, so its licence and saves are handled properly")

    def update(self, game):
        return self.install(game)  # both keep their games up to date themselves; this opens them

    def launch(self, game):
        if WINDOWS:
            from .. import winxbox
            if not game.extra.get("app_id"):
                raise StoreError("Cornerplay does not know how to start this game; start it from the Xbox app")
            return Command(winxbox.launch_argv(game.id, game.extra["app_id"]))
        from .. import nexus
        if not nexus.appimage():
            raise StoreError("Nexus Launcher is not installed: connect Xbox / Game Pass under Accounts")
        if game.id == NEXUS_ID:
            return Command(nexus.argv(), env=nexus.env())
        return Command(nexus.argv(game.id), env=nexus.env(), cwd=os.path.expanduser("~"))
