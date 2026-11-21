"""Game Mode: the helper that restarts Steam with Cornerplay's games added."""
import json

from cornerplay import steamgames
from cornerplay.stores.base import Game


def test_helper_runs_outside_steam(monkeypatch):
    monkeypatch.setattr(steamgames.shutil, "which", lambda n: "/usr/bin/" + n)
    monkeypatch.setattr(steamgames.host, "IN_FLATPAK", False)
    argv = steamgames.helper_argv("/home/u/.local/bin/cornerplay")
    assert argv[:4] == ["systemd-run", "--user", "--collect", "--quiet"]
    assert argv[-2:] == ["/home/u/.local/bin/cornerplay", "--steam-sync"]


def test_candidates_from_cache(tmp_path, monkeypatch):
    lib = [Game(store="epic", id="a", title="A", installed=True).to_dict(),
           Game(store="epic", id="b", title="B", installed=False).to_dict(),
           Game(store="steam", id="1", title="S", installed=True).to_dict()]
    monkeypatch.setattr("cornerplay.config.CACHE_DIR", tmp_path)
    (tmp_path / "library.json").write_text(json.dumps(lib))
    assert [g.key for g in steamgames.candidates_from_cache()] == ["epic:a"]


def test_helper_restarts_steam(monkeypatch):
    synced, started, log = [], [], []
    monkeypatch.setattr(steamgames, "candidates_from_cache", lambda: ["g"])
    monkeypatch.setattr(steamgames, "sync_games", lambda games: synced.append(games) or (1, 0))
    monkeypatch.setattr("time.sleep", lambda s: None)
    rc = steamgames.run_helper(log=log.append, wait_back=0, close=lambda timeout: True,
                               start=lambda: started.append(1), running=lambda: False)
    assert rc == 0 and synced == [["g"]] and started == [1] and "1 games" in log[0]
    rc = steamgames.run_helper(log=log.append, wait_back=0, close=lambda timeout: False,
                               start=lambda: started.append(1), running=lambda: False)
    assert rc == 1 and len(synced) == 1  # Steam did not close: shortcuts.vdf left alone
