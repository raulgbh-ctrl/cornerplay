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
    steam_ost, gog_ost, epic_pass, steam_pass = rows
    dlcfinder.group(rows, "Game")
    assert steam_ost["group"] == gog_ost["group"] == "soundtrack"
    assert gog_ost["cheapest"] and not steam_ost["cheapest"]
    assert gog_ost["primary"] and len(gog_ost["offers"]) == 2
    assert epic_pass["primary"] and steam_pass["ownedOn"] == ["Epic Games"]  # don't buy it twice
    assert rows[0] is epic_pass  # yours first


def test_dlc_names_match_across_stores():
    g = "Sid Meier's Civilization VI"
    assert dlcfinder.dlc_key("Sid Meier’s Civilization® VI: Rise and Fall", g) == \
        dlcfinder.dlc_key("Civilization VI : Rise and Fall", g) == "rise and fall"
    assert dlcfinder.dlc_key("Game OST", "Game") == dlcfinder.dlc_key("Game: Original Soundtrack", "Game")
    assert dlcfinder.dlc_key("Game: Expansion Pass", "Game") != dlcfinder.dlc_key("Game: Season Pass", "Game")


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
    one = [{"title": "G: A", "status": "available", "group": "a", "primary": True, "store": "steam"}]
    assert dlcfinder.remember("k", one) == []  # first look: nothing is "new"
    two = one + [{"title": "G: B", "status": "available", "group": "b", "primary": True, "store": "steam"}]
    assert dlcfinder.remember("k", two) == ["G: B"]
    assert dlcfinder.summary("k")["toBuy"] == 2 and dlcfinder.summary("k")["new"] == ["G: B"]
    assert dlcfinder.seen("k") and dlcfinder.summary("k")["new"] == []


def test_a_store_that_was_down_brings_no_false_new_dlc():
    steam = [{"title": "G: A", "status": "available", "group": "a", "primary": True, "store": "steam"}]
    dlcfinder.remember("k", steam)  # GOG did not answer this time
    gog = [{"title": "G: Art", "status": "available", "group": "art", "primary": True, "store": "gog"}]
    assert dlcfinder.remember("k", steam + gog) == []  # GOG's whole list is not "new"
    assert dlcfinder.remember("k", gog) == []          # Steam down for a day
    assert dlcfinder.remember("k", steam + gog) == []  # and back: A is not new either


def test_unknown_steam_ownership_is_not_dlc_to_get():
    rows = [{"title": "G: A", "status": "missing", "group": "a", "primary": True, "store": "steam"}]
    dlcfinder.remember("k", rows)
    assert dlcfinder.summary("k")["toBuy"] == 0


def test_titles_keep_edition_words_inside_the_name():
    assert dlcfinder.norm("Gold Rush: The Game") == "gold rush the game"
    assert dlcfinder.norm("Fallout 4: Game of the Year Edition") == "fallout 4"


def test_a_failed_search_is_not_remembered_as_a_miss(monkeypatch):
    def boom(t):
        raise dlcfinder.requests.RequestException("429")
    with pytest.raises(dlcfinder.requests.RequestException):
        dlcfinder.find("steam", "Game", boom)
    assert dlcfinder.find("steam", "Game", lambda t: "7") == "7"


def test_epic_price_in_its_currency():
    assert dlcfinder.epic_price({"discountPrice": 3149, "originalPrice": 4499, "currencyCode": "AUD",
                                 "currencyInfo": {"decimals": 2}}) == "A$31.49 (-30%)"


def test_amazon_lists_the_add_ons_you_hold(monkeypatch, tmp_path):
    import json
    from types import SimpleNamespace as NS
    from cornerplay.stores import amazon
    (tmp_path / "library.json").write_text(json.dumps([
        {"product": {"id": "g1", "title": "Besiege", "productLine": "Sonic:Game"}},
        {"product": {"id": "d1", "title": "Besiege: The Splintered Sea", "productLine": "Twitch:FuelEntitlement"}},
        {"product": {"id": "x1", "title": "Besieged Castle", "productLine": "Twitch:FuelEntitlement"}},
    ]))
    monkeypatch.setattr(amazon, "NILE_DIR", tmp_path)
    store = amazon.Amazon.__new__(amazon.Amazon)
    rows = store.dlcs(NS(id="g1", title="Besiege"))
    assert [(r["id"], r["status"]) for r in rows] == [("d1", "owned")]


def test_a_short_and_a_long_name_of_one_dlc_are_one_row():
    rows = [
        {"title": "Commander Lilith DLC", "status": "owned", "price": "", "store": "epic", "storeName": "Epic Games", "url": ""},
        {"title": "Borderlands 2: Commander Lilith & the Fight for Sanctuary", "status": "available", "price": "€9.99",
         "store": "steam", "storeName": "Steam", "url": ""},
        {"title": "Borderlands 2 Season Pass", "status": "available", "price": "€29.99", "store": "steam", "storeName": "Steam", "url": ""},
        {"title": "Borderlands 2 Season Pass 2", "status": "available", "price": "€29.99", "store": "steam", "storeName": "Steam", "url": ""},
    ]
    dlcfinder.group(rows, "Borderlands 2")
    lilith = [r for r in rows if "Lilith" in r["title"]]
    assert lilith[0]["group"] == lilith[1]["group"]
    assert next(r for r in lilith if r["store"] == "steam")["ownedOn"] == ["Epic Games"]  # don't buy it twice
    passes = [r for r in rows if "Season" in r["title"]]
    assert passes[0]["group"] != passes[1]["group"]  # a numbered sequel is another DLC
