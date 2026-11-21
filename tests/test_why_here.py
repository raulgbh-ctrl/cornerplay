"""Where a game came from: Epic giveaways told apart from purchases by the giveaway's window."""
from cornerplay import epicfree


def test_giveaway_window(tmp_path, monkeypatch):
    monkeypatch.setattr(epicfree, "HISTORY", tmp_path / "h.json")
    epicfree.remember([{"title": "Mark of the Deep", "start": 1_000_000, "end": 1_600_000}])
    assert epicfree.giveaway("MARK OF THE DEEP", 1_300_000)
    assert epicfree.giveaway("Mark of the Deep", 1_600_000 + 3 * 86400)  # Cornerplay refreshed a few days later
    assert not epicfree.giveaway("Mark of the Deep", 5_000_000)           # bought long after
    assert not epicfree.giveaway("Mark of the Deep", 0)                   # owned before Cornerplay knew Epic
    assert not epicfree.giveaway("Other Game", 1_300_000)
