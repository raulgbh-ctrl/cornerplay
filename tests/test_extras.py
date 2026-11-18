from cornerplay import app as appmod



def test_dupes_tag_needs_two_stores():
    p = appmod.LibraryProxy.__new__(appmod.LibraryProxy)
    a = type("G", (), {"store": "steam"})()
    b = type("G", (), {"store": "gog"})()
    c = type("G", (), {"store": "steam"})()
    assert p._has_tag(None, [a, b], "dupes") is True
    assert p._has_tag(None, [a, c], "dupes") is False


def test_because_row_is_empty_without_a_game():
    assert appmod._BECAUSE["test"]([]) is False
