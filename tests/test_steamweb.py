"""Steam through its web sign-in: owned games and Steam Family's, no Web API key."""
import json

from cornerplay import steamweb
from cornerplay.stores import steam as steam_mod


def _signed_in(tmp_path, monkeypatch, sid="76561198000000001"):
    monkeypatch.setattr(steamweb, "AUTH_FILE", tmp_path / "steam_web.json")
    steamweb.save([{"name": "steamLoginSecure", "value": f"{sid}%7C%7Ceyjwt", "domain": "store.steampowered.com", "path": "/"},
                   {"name": "other", "value": "x", "domain": "example.com", "path": "/"}], "Raul")
    return sid


def test_save_keeps_only_steam_cookies(tmp_path, monkeypatch):
    sid = _signed_in(tmp_path, monkeypatch)
    saved = json.loads((tmp_path / "steam_web.json").read_text())
    assert [c["domain"] for c in saved["cookies"]] == ["store.steampowered.com"]
    assert steamweb.steamid() == sid and steamweb.account() == "Raul" and steamweb.signed_in()
    steamweb.forget()
    assert not steamweb.signed_in()


def test_save_refuses_without_session(tmp_path, monkeypatch):
    monkeypatch.setattr(steamweb, "AUTH_FILE", tmp_path / "steam_web.json")
    try:
        steamweb.save([{"name": "sessionid", "value": "x", "domain": "steamcommunity.com"}])
    except steamweb.NotSignedIn:
        pass
    else:
        raise AssertionError("saved a session Steam never signed in")


def test_fetch_lists_owned_and_lent(tmp_path, monkeypatch):
    sid = _signed_in(tmp_path, monkeypatch)
    monkeypatch.setattr(steam_mod.Steam, "library_dirs", lambda self: [])
    monkeypatch.setattr(steam_mod.Steam, "root", lambda self: None)
    monkeypatch.setattr(steam_mod.Steam, "_recent_user", lambda self: ("", {}))
    monkeypatch.setitem(steam_mod.settings.data, "steam_api_key", "")
    monkeypatch.setitem(steam_mod.settings.data, "steam_id", "")
    monkeypatch.setattr(steamweb, "token", lambda: "tok")
    monkeypatch.setattr(steamweb, "owned", lambda tok, s: [{"appid": 413150, "name": "Stardew Valley"}])
    monkeypatch.setattr(steamweb, "lent", lambda tok, s: [
        {"appid": "413150", "name": "Stardew Valley", "owners": ["2"]},   # owned too: stays yours
        {"appid": "1145360", "name": "Hades", "owners": ["2"]}])
    monkeypatch.setattr(steamweb, "person", lambda s: {"2": "Ana"}.get(s, ""))
    games = {g.id: g for g in steam_mod.Steam().fetch()}
    assert games["413150"].extra["source"] == "account"
    assert games["1145360"].extra["source"] == "lent" and games["1145360"].extra["lender"] == "Ana"
    assert sid


def test_lent_parsing(monkeypatch):
    calls = []

    def fake_get(path, params, timeout=20):
        calls.append(path)
        if "GetFamilyGroupForUser" in path:
            return {"family_groupid": "123"}
        return {"apps": [{"appid": 1, "name": "Mine", "owner_steamids": ["9"]},
                         {"appid": 2, "name": "Theirs", "owner_steamids": ["5", "9"]},
                         {"appid": 3, "name": "Blocked", "owner_steamids": ["5"], "exclude_reason": 2}]}
    monkeypatch.setattr(steamweb, "_get", fake_get)
    assert steamweb.lent("tok", "9") == [{"appid": "2", "name": "Theirs", "owners": ["5"]}]
