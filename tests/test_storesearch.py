"""Store page: every store searched at once, grouped by game, prices in one currency."""
from cornerplay import currency, storesearch as S


def test_one_currency():
    table = {"EUR": 1.0, "USD": 1.1, "RON": 5.0}
    assert currency.text(11, "USD", None, "EUR", table) == "≈ €10.00"
    assert currency.text(10, "EUR", 20, "EUR", table) == "€10.00 (-50%)"
    assert currency.text(0, "RON", None, "EUR", table) == "Free"
    assert currency.text(5, "XYZ", None, "EUR", table) == "5.00 XYZ"  # no rate: the store's own price


def test_search_groups_stores(monkeypatch):
    monkeypatch.setattr(currency, "rates", lambda: {"EUR": 1.0, "USD": 1.25})
    monkeypatch.setattr(currency, "target", lambda: "EUR")
    row = lambda store, title, amount, cur: {"store": store, "shop": store, "id": title, "title": title, "art": [],
                                            "money": S._money(amount, cur), "url": "u"}
    monkeypatch.setattr(S, "SEARCHERS", {
        "steam": lambda q: [row("steam", "Hades II", 20, "EUR")],
        "gog": lambda q: [row("gog", "HADES II", 25, "USD"), row("gog", "Hades", 5, "USD")],
        "epic": lambda q: (_ for _ in ()).throw(OSError("down"))})
    res = S.search("hades ii")
    first = res["groups"][0]
    assert first["title"] == "Hades II" and [o["store"] for o in first["offers"]] == ["steam", "gog"]
    assert [o["price"] for o in first["offers"]] == ["€20.00", "≈ €20.00"]
    assert res["failed"] == ["epic"] and {l["store"] for l in res["links"]} == {"humble", "amazon", "battlenet"}
