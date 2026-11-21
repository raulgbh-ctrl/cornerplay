from types import SimpleNamespace as NS

import pytest

from cornerplay import dlcfinder


@pytest.fixture(autouse=True)
def _own_cache(monkeypatch, tmp_path):
    """Keep lookups out of the real ~/.cache/cornerplay."""
    monkeypatch.setattr(dlcfinder, "MATCH_FILE", tmp_path / "match.json")
    monkeypatch.setattr(dlcfinder, "SUMMARY_FILE", tmp_path / "summary.json")
    monkeypatch.setattr(dlcfinder, "_match", None)
    monkeypatch.setattr(dlcfinder, "_summary", None)


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


def test_same_dlc_on_two_stores_is_one_group_cheapest_marked():
    rows = [
        {"title": "Game: Soundtrack", "status": "available", "price": "€7.99", "store": "steam", "storeName": "Steam", "url": "s"},
        {"title": "Game - Soundtrack", "status": "available", "price": "€6.49", "store": "gog", "storeName": "GOG", "url": "g"},
        {"title": "Game: Pass", "status": "owned", "price": "", "store": "epic", "storeName": "Epic Games", "url": ""},
        {"title": "Game Pass", "status": "available", "price": "€24.99", "store": "steam", "storeName": "Steam", "url": "s2"},
    ]
    dlcfinder.group(rows, "Game")
    assert rows[0]["group"] == rows[1]["group"] == "soundtrack"
    assert rows[1]["cheapest"] and not rows[0]["cheapest"]
    assert rows[1]["primary"] and len(rows[1]["offers"]) == 2
    assert rows[2]["primary"] and rows[3]["ownedOn"] == ["Epic Games"]  # don't buy it twice


def test_amount_and_variants():
    assert dlcfinder.amount("€9.99 (-30%)") == ("€", 9.99)
    assert dlcfinder.amount("Free") == ("", 0.0)
    assert dlcfinder.variants("Besiege + The Splintered Sea DLC") == ["Besiege + The Splintered Sea DLC", "Besiege"]


def test_find_remembers_hits_and_misses(monkeypatch, tmp_path):
    monkeypatch.setattr(dlcfinder, "MATCH_FILE", tmp_path / "m.json")
    monkeypatch.setattr(dlcfinder, "_match", None)
    calls = []
    assert dlcfinder.find("steam", "Game", lambda t: calls.append(t) or "42") == "42"
    assert dlcfinder.find("steam", "Game", lambda t: calls.append(t) or "x") == "42"
    assert calls == ["Game"]


def test_remember_reports_new_dlc_once(monkeypatch, tmp_path):
    monkeypatch.setattr(dlcfinder, "SUMMARY_FILE", tmp_path / "s.json")
    monkeypatch.setattr(dlcfinder, "_summary", None)
    one = [{"title": "G: A", "status": "available", "group": "a", "primary": True}]
    assert dlcfinder.remember("k", one) == []  # first look: nothing is "new"
    two = one + [{"title": "G: B", "status": "available", "group": "b", "primary": True}]
    assert dlcfinder.remember("k", two) == ["G: B"]
    assert dlcfinder.summary("k")["toBuy"] == 2 and dlcfinder.summary("k")["new"] == ["G: B"]
    assert dlcfinder.seen("k") and dlcfinder.summary("k")["new"] == []


def test_epic_price_in_its_currency():
    assert dlcfinder.epic_price({"discountPrice": 3149, "originalPrice": 4499, "currencyCode": "AUD",
                                 "currencyInfo": {"decimals": 2}}) == "A$31.49 (-30%)"
