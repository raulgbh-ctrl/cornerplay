"""Xbox / PC Game Pass: Nexus Launcher on Linux, the Xbox app on Windows, the Game Pass catalog."""
import json
import os
import shutil
import subprocess
import sys
import time

import pytest

from cornerplay import gamepass, nexus, session, winxbox
from cornerplay.stores import xbox as X
from cornerplay.stores.base import Game

CATALOG = [{"id": "9NFORZA", "title": "Forza Horizon 6", "cover": "https://img/forza.jpg", "hero": "https://img/fh.jpg",
            "publisher": "Xbox Game Studios"},
           {"id": "9NPAL", "title": "Palworld", "cover": "https://img/pal.jpg", "hero": "", "publisher": "Pocketpair"}]


@pytest.fixture
def nexus_home(tmp_path, monkeypatch):
    """A Nexus Launcher install and profile in a temp folder, with one installed game."""
    app = tmp_path / "opt"
    app.mkdir()
    exe = app / "Nexus-Launcher.AppImage"
    exe.write_text("#!/bin/sh\n")
    exe.chmod(0o755)
    profile = tmp_path / "profile"
    profile.mkdir()
    game_dir = tmp_path / "Games" / "Forza"
    game_dir.mkdir(parents=True)
    (profile / "launcher-state.json").write_text(json.dumps({"games": [
        {"id": "fh6", "title": "Forza Horizon 6 (local name)", "path": str(game_dir), "storeId": "9NFORZA",
         "coverUrl": "https://img/local.jpg", "installState": "ready"},
        {"id": "half", "title": "Half Installed", "path": str(tmp_path / "Games" / "Half"), "installState": "incomplete"},
        {"title": "no id: skipped"}], "settings": {}}))
    (profile / "xbox-profile.json").write_text(json.dumps({"schema": 1, "gamertag": "Raul GBH"}))
    monkeypatch.setattr(nexus, "APP_DIR", app)
    monkeypatch.setattr(nexus, "PROFILE", profile)
    monkeypatch.setattr(nexus.shutil, "which", lambda n: None)
    monkeypatch.setattr(gamepass, "catalog", lambda force=False: CATALOG)
    monkeypatch.setattr(X, "WINDOWS", False)
    monkeypatch.setattr(nexus, "unsupported", lambda: "")  # pretend to be a Linux PC Nexus runs on (also in Windows CI)
    return tmp_path


def test_nexus_games_and_account(nexus_home):
    games = nexus.games()
    assert [g["id"] for g in games] == ["fh6", "half"]
    assert games[0]["ready"] and not games[1]["ready"]
    assert nexus.gamertag() == "Raul GBH"
    assert nexus.argv("fh6") == [str(nexus_home / "opt" / "Nexus-Launcher.AppImage"), "--launch-game", "fh6"]


def test_store_lists_installed_games_and_the_catalog(nexus_home, monkeypatch):
    monkeypatch.setattr(X.Xbox, "gamepass_tier", lambda self: "full")
    s = X.Xbox()
    assert s.logged_in() and "Raul GBH" in s.account()
    games = {g.id: g for g in s.fetch()}
    assert X.NEXUS_ID not in games  # signed in: Nexus Launcher's tile is not needed any more
    fh = games["fh6"]
    assert fh.installed and fh.title == "Forza Horizon 6" and fh.cover == "https://img/forza.jpg"  # the catalog's
    assert fh.extra["gamepass"] and fh.extra["store_id"] == "9NFORZA"
    assert not games["half"].installed
    assert "gp-9NFORZA" not in games  # installed already: no catalog tile for it
    pal = games["gp-9NPAL"]
    assert not pal.installed and not pal.extra["owned_only"] and pal.extra["store_id"] == "9NPAL"  # Linux: Cornerplay installs it


def test_store_launch_and_install_commands(nexus_home):
    s = X.Xbox()
    g = Game(store="xbox", id="fh6", title="Forza", installed=True, install_path="/x")
    assert s.launch(g).argv[-2:] == ["--launch-game", "fh6"]
    assert s.launch(Game(store="xbox", id=X.NEXUS_ID, title="Nexus")).argv[-1].endswith(".AppImage")
    cmd = s.install(Game(store="xbox", id="gp-9NPAL", title="Palworld", extra={"store_id": "9NPAL"}))
    assert cmd.argv[-4:-2] == ["install", "9NPAL"]  # Cornerplay downloads it itself
    with pytest.raises(X.StoreError):
        s.uninstall(g)  # Nexus Launcher installed that one: it uninstalls it


def test_catalog_only_once_connected(nexus_home, monkeypatch):
    shutil.rmtree(nexus_home / "opt")
    monkeypatch.setattr(nexus, "APP_DIR", nexus_home / "missing")
    s = X.Xbox()
    assert not s.logged_in()
    assert not any(g.id.startswith("gp-") for g in s.fetch())


def test_connect_installs_nexus_through_a_helper(nexus_home, monkeypatch):
    monkeypatch.setattr(nexus, "unsupported", lambda: "")
    info = X.Xbox().login_begin()
    assert info["command"][-2:] == ["cornerplay.nexus", "open"]


def test_store_on_windows(monkeypatch):
    monkeypatch.setattr(X, "WINDOWS", True)
    monkeypatch.setattr(X.Xbox, "gamepass_tier", lambda self: "full")
    monkeypatch.setattr(gamepass, "catalog", lambda force=False: CATALOG)
    monkeypatch.setattr(winxbox, "xbox_app_installed", lambda: True)
    monkeypatch.setattr(winxbox, "games", lambda: [
        {"id": "Microsoft.ForzaHorizon6_8wekyb3d8bbwe", "title": "ms-resource:Title", "path": "C:/XboxGames/Forza/Content",
         "storeId": "9NFORZA", "appId": "Game", "exe": "ForzaHorizon6.exe"}])
    s = X.Xbox()
    games = {g.id: g for g in s.fetch()}
    fh = games["Microsoft.ForzaHorizon6_8wekyb3d8bbwe"]
    assert fh.title == "Forza Horizon 6" and fh.installed
    assert s.launch(fh).argv == ["explorer.exe", r"shell:AppsFolder\Microsoft.ForzaHorizon6_8wekyb3d8bbwe!Game"]
    assert s.install(games["gp-9NPAL"]).argv == ["explorer.exe", "ms-windows-store://pdp/?ProductId=9NPAL"]
    assert X.NEXUS_ID not in games


def test_windows_game_manifest(tmp_path):
    cfg = tmp_path / "MicrosoftGame.config"
    cfg.write_text('<?xml version="1.0"?><Game configVersion="1">'
                   '<Identity Name="Microsoft.Forza" Publisher="CN=Microsoft" Version="1.0.0.0"/>'
                   '<StoreId>9NFORZA</StoreId>'
                   '<ExecutableList><Executable Name="Forza.exe" Id="Game" TargetDeviceFamily="PC"/></ExecutableList>'
                   '<ShellVisuals DefaultDisplayName="Forza Horizon 6" PublisherDisplayName="Xbox"/></Game>')
    assert winxbox.parse_config(str(cfg)) == {"title": "Forza Horizon 6", "storeId": "9NFORZA", "appId": "Game",
                                              "exe": "Forza.exe", "name": "Microsoft.Forza"}
    assert winxbox.parse_config(str(tmp_path / "missing")) == {}


def test_catalog_market(monkeypatch):
    from cornerplay.config import settings
    monkeypatch.setitem(settings.data, "gamepass_market", "ro")
    assert gamepass.market() == "RO"
    monkeypatch.setitem(settings.data, "gamepass_market", "")
    monkeypatch.setenv("LC_ALL", "de_DE.UTF-8")
    assert gamepass.market() == "DE"


def test_catalog_falls_back_to_the_cached_copy(monkeypatch, tmp_path):
    monkeypatch.setattr(gamepass, "CACHE", tmp_path / "gp.json")
    (tmp_path / "gp.json").write_text(json.dumps({"t": 0, "market": "XX", "games": CATALOG}))

    def offline(*a, **k):
        raise gamepass.requests.ConnectionError("offline")
    monkeypatch.setattr(gamepass, "_ids", offline)
    assert gamepass.catalog() == CATALOG


@pytest.mark.skipif(not shutil.which("sleep"), reason="needs a sleep program")
def test_session_follows_the_game_folder(tmp_path, monkeypatch):
    """The launcher returns at once; the session lasts as long as a program from the game's folder runs."""
    folder = tmp_path / "Game"
    folder.mkdir()
    prog = folder / "game"  # a real program in the game's folder (a script would show as /bin/sh)
    shutil.copy(shutil.which("sleep"), prog)
    launcher = subprocess.Popen([sys.executable, "-c", "pass"])
    game_proc = subprocess.Popen([str(prog), "3"])
    g = Game(store="xbox", id="x", title="X", installed=True, install_path=str(folder))
    t = time.time()
    code, started, ended = session._follow_folder(g, launcher, tmp_path / "s.json", t, wait_start=20, poll=0.3, grace=0.5)
    game_proc.wait()
    assert code == 0 and started and ended - started >= 2


def test_wine_paths_match_linux_folders():
    assert session._norm(r"Z:\home\raul\Games\Forza\Content\Forza.exe").startswith("/home/raul/games/forza/content")
    assert session._norm("C:/XboxGames/Forza") == "c:/xboxgames/forza"


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Nexus Launcher is Linux only")
def test_nexus_needs_x86_and_new_glibc(monkeypatch):
    import platform
    monkeypatch.setattr(platform, "machine", lambda: "aarch64")
    assert "x86_64" in nexus.unsupported()
    monkeypatch.setattr(platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(nexus, "glibc", lambda: (2, 35))
    assert "glibc" in nexus.unsupported()
    monkeypatch.setattr(nexus, "glibc", lambda: (2, 41))
    assert nexus.unsupported() == ""


def test_appimage_runs_without_fuse(monkeypatch):
    monkeypatch.setattr(nexus.ctypes.util, "find_library", lambda n: None)
    assert nexus.env() == {"APPIMAGE_EXTRACT_AND_RUN": "1"}
    monkeypatch.setattr(nexus.ctypes.util, "find_library", lambda n: "libfuse.so.2")
    assert nexus.env() == {}
    assert os.environ.get("APPIMAGE_EXTRACT_AND_RUN") is None


@pytest.mark.skipif(os.name != "nt", reason="the Xbox app is Windows only")
def test_windows_package_listing_runs():
    """On a real Windows (CI): PowerShell lists the app packages and nothing breaks on them."""
    winxbox._cache = (0.0, [])
    packages = winxbox._packages()
    assert packages and all(isinstance(p, dict) for p in packages)
    assert isinstance(winxbox.games(), list)
    assert isinstance(winxbox.xbox_app_installed(), bool)


def test_owned_games_come_from_nexus_backend(nexus_home, monkeypatch, tmp_path):
    """Games the account bought show in the library before they are installed: Nexus's backend
    (xodus-cli library --json) lists them, the Store's catalog names them."""
    backends = nexus.PROFILE / "xodus-backends"
    backends.mkdir()
    cli = tmp_path / "xodus-cli"
    cli.write_text("#!/bin/sh\n[ \"$1 $2\" = \"library --json\" ] || exit 2\ncat <<'J'\n" + json.dumps({"schema": 1, "entitlements": [
        {"productId": "9NFALLOUT", "status": "Active", "isTrial": False},
        {"productId": "9NFORZA", "status": "Active", "isTrial": False},   # installed already
        {"productId": "9NTRIAL", "status": "Active", "isTrial": True},    # a trial: not a game you own
        {"productId": "9NGONE", "status": "Expired", "isTrial": False}]}) + "\nJ\n")
    cli.chmod(0o755)
    (backends / "current.json").write_text(json.dumps({"binaryPath": str(cli)}))
    monkeypatch.setattr(gamepass, "catalog", lambda force=False: CATALOG)
    monkeypatch.setattr(X.Xbox, "gamepass_tier", lambda self: "full")
    asked = []
    monkeypatch.setattr(gamepass, "_details", lambda ids, mkt: asked.extend(ids) or [
        {"id": i, "title": {"9NFALLOUT": "Fallout 76 (PC)", "9NFORZA": "Forza Horizon 6"}[i], "cover": "c", "hero": "",
         "publisher": "Bethesda"} for i in ids])
    assert nexus.owned(force=True) == ["9NFALLOUT", "9NFORZA"]
    games = {g.id: g for g in X.Xbox().fetch()}
    fo = games["own-9NFALLOUT"]
    assert fo.title == "Fallout 76 (PC)" and not fo.installed and fo.extra["owned"] and not fo.extra["owned_only"]
    assert "own-9NFORZA" not in games and games["fh6"].installed  # installed: one tile, not two
    assert "gp-9NPAL" in games


def test_owned_keeps_the_last_list_when_nexus_cannot_answer(nexus_home):
    from cornerplay.config import CACHE_DIR, write_json
    write_json(CACHE_DIR / "xbox-owned.json", {"t": 0, "ids": ["9NKEPT"]})
    assert nexus.owned(force=True) == ["9NKEPT"]  # no backend to ask: the last list stays
    (CACHE_DIR / "xbox-owned.json").unlink()
    assert nexus.owned(force=True) == []



def test_no_game_pass_games_without_game_pass(nexus_home, monkeypatch):
    """Nexus saves "unknown" and no pass products when the account has no Game Pass: then the
    catalog's games are left out (they could not be played), installed and owned games stay."""
    from cornerplay.config import CACHE_DIR, settings
    (CACHE_DIR / "xbox-owned.json").unlink(missing_ok=True)
    monkeypatch.setattr(gamepass, "catalog", lambda force=False: CATALOG)
    monkeypatch.setattr(settings, "get", lambda k, d=None: {"gamepass_member": "auto"}.get(k, d))
    prof = nexus.PROFILE / "xbox-profile.json"
    prof.write_text(json.dumps({"gamertag": "Raul GBH", "subscription": {"status": "unknown", "productIds": []}}))
    assert not nexus.gamepass_member()
    games = {g.id: g for g in X.Xbox().fetch()}
    assert "gp-9NPAL" not in games and "fh6" in games
    prof.write_text(json.dumps({"gamertag": "Raul GBH", "subscription": {"status": "active", "productIds": ["CFQ7TTC0KGQ8"]}}))
    assert nexus.gamepass_member()
    assert "gp-9NPAL" in {g.id for g in X.Xbox().fetch()}
    prof.write_text(json.dumps({"subscription": {"status": "active", "productIds": ["CFQ7TTC0KGQ8"],
                                                 "validUntil": "2020-01-01T00:00:00Z"}}))
    assert not nexus.gamepass_member()  # ran out


def test_game_pass_choice_wins(monkeypatch):
    from cornerplay.config import settings
    for chosen, want in (("yes", True), ("no", False)):
        monkeypatch.setattr(settings, "get", lambda k, d=None, c=chosen: {"gamepass_member": c}.get(k, d))
        assert X.Xbox().has_gamepass() is want
    monkeypatch.setattr(X, "WINDOWS", True)
    monkeypatch.setattr(settings, "get", lambda k, d=None: {"gamepass_member": "auto"}.get(k, d))
    assert X.Xbox().has_gamepass() is False  # Windows cannot tell: hidden until you say yes


def test_linux_installs_and_plays_through_cornerplay(nexus_home, monkeypatch, tmp_path):
    """Linux: Install is a Cornerplay download (xodus.py, with progress), not Nexus Launcher;
    a game Cornerplay installed starts through it, and uninstalls through it."""
    from cornerplay import xodus
    from cornerplay.config import settings
    monkeypatch.setattr(xodus, "STATE", tmp_path / "games.json")
    real_get = settings.get
    monkeypatch.setattr(settings, "get", lambda k, d=None: "no" if k == "gamepass_member" else real_get(k, d))
    monkeypatch.setattr(type(settings), "games_dir", property(lambda self: tmp_path / "Games"), raising=False)
    s = X.Xbox()
    assert not s.external_installs
    g = Game(store="xbox", id="own-9NFALLOUT", title="Fallout 76: PC?", installed=False, extra={"store_id": "9NFALLOUT"})
    argv = s.install(g).argv
    assert argv[-4:] == ["install", "9NFALLOUT", str(tmp_path / "Games" / "Xbox" / "Fallout 76 PC"), "Fallout 76: PC?"]
    game_dir = tmp_path / "Games" / "Xbox" / "Fallout 76 PC"
    game_dir.mkdir(parents=True)
    xodus._save_state({"9NFALLOUT": {"title": "Fallout 76", "path": str(game_dir), "installed": 1, "exe": "Fallout76.exe"}})
    games = {g.id: g for g in s.fetch()}
    fo = games["xb-9NFALLOUT"]
    assert fo.installed and fo.install_path == str(game_dir) and "own-9NFALLOUT" not in games
    assert s.launch(fo).argv[-2:] == ["play", "9NFALLOUT"]
    assert s.uninstall(fo).argv[-2:] == ["uninstall", "9NFALLOUT"]
    xodus.uninstall("9NFALLOUT")
    assert not game_dir.exists() and xodus.state() == {}


def test_progress_lines_cornerplay_reads(monkeypatch, tmp_path, capsys):
    """The backend's NEXUS_PROGRESS events become the Progress:/ETA: lines the download bar reads."""
    from cornerplay import xodus
    monkeypatch.setattr(xodus, "STATE", tmp_path / "games.json")
    cli = tmp_path / "xodus-cli"
    cli.write_text("#!/bin/sh\necho 'NEXUS_PROGRESS {\"completedBytes\":50,\"totalBytes\":200,\"bytesPerSecond\":10,\"phase\":\"downloading\"}'\n"
                   "echo 'NEXUS_PROGRESS {\"completedBytes\":200,\"totalBytes\":200,\"bytesPerSecond\":0,\"phase\":\"complete\"}'\n")
    cli.chmod(0o755)
    monkeypatch.setattr(xodus, "backend", lambda: str(cli))
    monkeypatch.setattr(xodus, "runtime", lambda: tmp_path)
    monkeypatch.setattr(xodus, "resolve", lambda pid: {"contentId": "c1", "title": "T"})
    monkeypatch.setattr(xodus, "_market", lambda: "US")
    assert xodus.install("9NX", str(tmp_path / "g"), "T") == 0
    out = capsys.readouterr().out
    assert "Progress: 25.0% 0.0 MiB/s ETA: 00:00:15" in out
    assert xodus.state()["9NX"]["installed"] > 0


def test_game_pass_tier_shows_only_its_games(nexus_home, monkeypatch):
    """Premium and Essential have fewer PC games than Ultimate / PC Game Pass: each game's Store
    listing names the passes that include it, and only the tier's games show."""
    from cornerplay.config import CACHE_DIR, settings
    (CACHE_DIR / "xbox-owned.json").unlink(missing_ok=True)
    cat = [{**CATALOG[0], "id": "9NPREM", "passes": ["CFQ7TTC0KGQ8", "CFQ7TTC0P85B"]},
           {**CATALOG[1], "passes": ["CFQ7TTC0KGQ8", "CFQ7TTC0P85B", "CFQ7TTC0K5DJ"]},
           {"id": "9NPCONLY", "title": "PC only", "cover": "", "hero": "", "publisher": "", "passes": ["CFQ7TTC0KGQ8"]}]
    monkeypatch.setattr(gamepass, "catalog", lambda force=False: cat)
    monkeypatch.setattr(settings, "get", lambda k, d=None: {"gamepass_member": "auto"}.get(k, d))
    prof = nexus.PROFILE / "xbox-profile.json"

    def shown(pass_ids):
        prof.write_text(json.dumps({"gamertag": "Raul GBH", "subscription": {"status": "active", "productIds": pass_ids}}))
        return {g.id for g in X.Xbox().fetch() if g.id.startswith("gp-")}

    assert shown(["CFQ7TTC0KHS0"]) == {"gp-9NPREM", "gp-9NPAL", "gp-9NPCONLY"}  # Ultimate
    assert shown(["CFQ7TTC0KGQ8"]) == {"gp-9NPREM", "gp-9NPAL", "gp-9NPCONLY"}  # PC Game Pass
    assert shown(["CFQ7TTC0P85B"]) == {"gp-9NPREM", "gp-9NPAL"}                 # Premium
    assert shown(["CFQ7TTC0K5DJ"]) == {"gp-9NPAL"}                               # Essential
    assert shown(["CFQ7TTC0K6L8"]) == set()                                      # Console: no PC games
    assert shown(["CFQ7TTC0P85B", "CFQ7TTC0KHS0"]) == {"gp-9NPREM", "gp-9NPAL", "gp-9NPCONLY"}  # best one wins
    assert nexus.gamepass_tier() == "full"
    for chosen, want in (("premium", {"gp-9NPREM", "gp-9NPAL"}), ("essential", {"gp-9NPAL"}), ("no", set())):
        monkeypatch.setattr(settings, "get", lambda k, d=None, c=chosen: {"gamepass_member": c}.get(k, d))
        assert {g.id for g in X.Xbox().fetch() if g.id.startswith("gp-")} == want


def test_catalog_games_keep_their_passes(monkeypatch):
    from cornerplay import gamepass as G

    class R:
        def raise_for_status(self): pass
        def json(self):
            return {"Products": [{"ProductId": "9NX", "LocalizedProperties": [{"ProductTitle": "X", "Images": []}],
                                  "DisplaySkuAvailabilities": [{"Availabilities": [{"Properties": {"SatisfyingEntitlementKeys": [
                                      {"EntitlementKeys": ["big:CFQ7TTC0P85B:0010", "big:CFQ7TTC0K5DJ:0010", "big:CFQ7TTC0ZZZZ:1"]}]}}]}]}]}
    monkeypatch.setattr(G.requests, "get", lambda *a, **k: R())
    assert G._details(["9NX"], "US")[0]["passes"] == ["CFQ7TTC0K5DJ", "CFQ7TTC0P85B"]
    assert G.tier_of(["CFQ7TTC0K5DJ", "CFQ7TTC0P85B"]) == "premium" and G.tier_of(["x"]) == ""
