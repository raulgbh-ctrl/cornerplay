"""The library lists only what the accounts own: no store pages from Steam's cache, no test
servers, betas or soundtracks next to the real game."""
from cornerplay.stores.base import Game, drop_side_builds, side_build_of
from cornerplay.stores import steam as steam_mod


def test_side_builds_dropped_only_next_to_the_real_game():
    titles = ["PUBG: BATTLEGROUNDS", "PUBG: Test Server", "Fallout 76", "Fallout 76 Public Test Server",
              "Killing Floor 2", "KillingFloor2Beta", "Chivalry 2", "Chivalry 2 - Public Testing",
              "Galactic Civilizations III", "Galactic Civilizations III (Test branch)",
              "Check In, Please Playtest", "Torque Drift 2 - Demo", "Beta Decay", "Nightingale - Legacy Mode",
              "Q.U.B.E. 2 Soundtrack", "Stardew Valley"]
    games = {t: Game(store="steam", id=t, title=t) for t in titles}
    games["Installed Beta"] = Game(store="steam", id="x", title="Stardew Valley Beta", installed=True)
    drop_side_builds(games)
    assert sorted(games) == sorted(["PUBG: BATTLEGROUNDS", "Fallout 76", "Killing Floor 2", "Chivalry 2",
                                    "Galactic Civilizations III", "Check In, Please Playtest",
                                    "Torque Drift 2 - Demo", "Beta Decay", "Nightingale - Legacy Mode",
                                    "Stardew Valley", "Installed Beta"])
    assert not side_build_of("Alpha Protocol", titles)


def test_steam_without_key_lists_only_installed(monkeypatch, tmp_path):
    """Steam's appinfo.vdf names store pages and friends' games too: never list from it."""
    monkeypatch.setattr(steam_mod.Steam, "library_dirs", lambda self: [])
    monkeypatch.setattr(steam_mod.Steam, "root", lambda self: tmp_path)
    monkeypatch.setattr(steam_mod.Steam, "_recent_user", lambda self: ("76561198000000000", {}))
    monkeypatch.setitem(steam_mod.settings.data, "steam_api_key", "")
    called = []
    monkeypatch.setattr(steam_mod.requests, "get", lambda *a, **k: called.append(a) or None)
    assert steam_mod.Steam().fetch() == []
    assert not called
