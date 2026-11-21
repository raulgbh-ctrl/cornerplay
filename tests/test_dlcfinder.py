from types import SimpleNamespace as NS

from cornerplay import dlcfinder


def test_norm_drops_marks_and_edition_words():
    assert dlcfinder.norm("The Witcher® 3: Wild Hunt - Game of the Year Edition") == "the witcher 3 wild hunt"
    assert dlcfinder.norm("CONTROL Ultimate Edition") == dlcfinder.norm("Control")


def test_rows_add_every_other_store_and_skip_a_failing_one(monkeypatch):
    monkeypatch.setattr(dlcfinder, "steam_find", lambda t: "10")
    monkeypatch.setattr(dlcfinder, "steam_rows", lambda appid, client=False: [
        {"id": "11", "title": "Pass", "status": "missing", "price": "€9.99", "image": "", "url": "", "canInstall": False}])
    monkeypatch.setattr(dlcfinder, "gog_find", lambda t: (_ for _ in ()).throw(OSError("down")))
    monkeypatch.setattr(dlcfinder, "epic_find", lambda t: "ns")
    monkeypatch.setattr(dlcfinder, "epic_rows", lambda ns: ([
        {"id": "e1", "title": "Skins", "status": "available", "price": "$1", "image": "", "url": "", "canInstall": False}], set()))
    stores = {"steam": NS(client=lambda: None), "gog": NS()}
    own = [{"id": "a", "title": "Own", "status": "owned", "store": "amazon", "storeName": "Amazon"}]
    rows = dlcfinder.rows(NS(title="Game", store="amazon"), stores, own)
    assert [r["store"] for r in rows] == ["amazon", "steam", "epic"]
    assert rows[1]["status"] == "available"  # Steam's list, but the copy you own is elsewhere


def test_own_store_is_not_searched_again(monkeypatch):
    monkeypatch.setattr(dlcfinder, "epic_find", lambda t: (_ for _ in ()).throw(AssertionError("searched")))
    monkeypatch.setattr(dlcfinder, "steam_find", lambda t: "")
    rows = dlcfinder.rows(NS(title="Game", store="epic"), {"steam": NS(client=lambda: None)}, [])
    assert rows == []
