import pytest

from cornerplay.search import matches, words


@pytest.mark.parametrize("query,title", [
    ("witcher 3", "The Witcher 3: Wild Hunt"),
    ("baldurs gate", "Baldur's Gate 3"),
    ("baldur's gate iii", "Baldur's Gate 3"),
    ("gta 5", "Grand Theft Auto V"),
    ("gtav", "Grand Theft Auto V"),
    ("rdr2", "Red Dead Redemption 2"),
    ("hollowknight", "Hollow Knight"),
    ("knight hollow", "Hollow Knight"),
    ("pokemon", "Pokémon Legends: Arceus"),
    ("ds3", "Dark Souls III"),
    ("wow", "World of Warcraft"),
    ("2077", "Cyberpunk 2077"),
    ("cell", "Dead Cells"),
])
def test_finds(query, title):
    assert matches(query, title)


@pytest.mark.parametrize("query,title", [
    ("xyz", "Dead Cells"),
    ("ed", "Dead Cells"),          # not the initials, not the start of a word
    ("witcher 4", "The Witcher 3: Wild Hunt"),
])
def test_does_not_find(query, title):
    assert not matches(query, title)


def test_extra_texts():
    assert matches("metroid", "Hollow Knight", ["Team Cherry", "Metroidvania"])
    assert not matches("metroid", "Hollow Knight", ["Team Cherry"])


def test_words_fold():
    assert words("Baldur's Gate III") == ("baldurs", "gate", "3")
    assert words("I Am Bread") == ("i", "am", "bread")


def test_score_ranks_title_starts_first():
    from cornerplay.search import score
    assert score("dead cells", "Dead Cells") > score("dead", "Dead Cells") > score("dc", "Dead Cells") > score("cells", "Dead Cells") > 0
    assert score("xyz", "Dead Cells") == 0


def test_calm_softens_shouted_sentences_only():
    from cornerplay.details import calm
    assert calm("THE CRITICALLY ACCLAIMED FANTASY ACTION RPG. Rise, Tarnished.") == \
        "The critically acclaimed fantasy action RPG. Rise, Tarnished."
    assert calm("Play with friends. It is OK.") == "Play with friends. It is OK."


def test_titles_in_any_script_stay_apart():
    """Non-Latin titles used to fold to "" (all matched each other, shared one cover and one save entry)."""
    from cornerplay.search import compact, matches
    from cornerplay import covers, dlcfinder, savebackup
    assert not matches("Ω", "Grand Theft Auto V")
    assert matches("ведьмак", "Ведьмак 3")
    assert compact("ガンダム") != compact("カンダム")       # kana marks are not accents
    assert compact("Pokémon™") == compact("Pokemon") == "pokemon"
    for norm in (covers.norm, savebackup._norm, dlcfinder.norm):
        assert norm("ペルソナ5") and norm("ペルソナ5") != norm("Ведьмак 3")
    assert dlcfinder.norm("DOOM™ Eternal") == dlcfinder.norm("DOOM Eternal")


def test_old_save_index_is_not_trusted(monkeypatch):
    from cornerplay import savebackup
    from cornerplay.stores.base import Game
    old = {"t": 9e12, "games": {"": {"name": "ペルソナ", "files": []}}, "steam": {}}
    monkeypatch.setattr(savebackup, "_index", old)
    assert savebackup.index_is_old()
    assert savebackup.entry_for(Game(store="gog", id="1", title="Ведьмак")) is None
