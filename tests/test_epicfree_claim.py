"""Free Epic games: a one-click checkout link and one reminder before an unclaimed one ends."""
from cornerplay import epicfree


def test_reminder_once_and_only_unclaimed(tmp_path, monkeypatch):
    monkeypatch.setattr(epicfree, "REMINDED", tmp_path / "r.json")
    now = 1_000_000
    games = [{"title": "Mark of the Deep", "now": True, "end": now + 3600},
             {"title": "Owned Already", "now": True, "end": now + 3600},
             {"title": "Days Left", "now": True, "end": now + 5 * 86400},
             {"title": "Next Week", "now": False, "start": now + 86400, "end": now + 8 * 86400}]
    due = epicfree.due_reminders(games, {epicfree._norm("Owned Already")}, now)
    assert [g["title"] for g in due] == ["Mark of the Deep"]
    assert epicfree.due_reminders(games, set(), now + 60) == [g for g in games if g["title"] == "Owned Already"]
    assert epicfree.due_reminders(games, set(), now + 120) == []  # each one once
