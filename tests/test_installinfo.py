from cornerplay import installinfo
from cornerplay.stores.base import Game


def test_gog_size_adds_the_shared_files():
    d = {"sizes": {"*": (100, 200), "en-US": (10, 20), "de-DE": (11, 22)}}
    assert installinfo.gog_size(d, "de-DE") == (111, 222)
    assert installinfo.gog_size(d, "xx") in ((110, 220), (111, 222))  # unknown: the first language listed
    assert installinfo.gog_size({}, "en-US") == (0, 0)


def test_pick_language():
    langs = ["de-DE", "en-US", "ro-RO"]
    assert installinfo.pick_language(langs, "ro_RO") == "ro-RO"
    assert installinfo.pick_language(langs, "fr") == "en-US"
    assert installinfo.pick_language(["de-DE"], "fr") == "de-DE"
    assert installinfo.pick_language([], "ro") == ""


def _game(store, gid="123"):
    return Game(store=store, id=gid, title="T")


def test_epic_install_options(tmp_path, monkeypatch):
    from cornerplay.stores.epic import Epic
    s = Epic()
    monkeypatch.setattr(s, "tool", lambda: "legendary")
    argv = s.install(_game("epic"), base=str(tmp_path / "x"), dlcs=False).argv
    assert argv[argv.index("--base-path") + 1] == str(tmp_path / "x") and "--skip-dlcs" in argv
    assert "--with-dlcs" in s.install(_game("epic"), base=str(tmp_path), dlcs=True).argv
    assert not {"--with-dlcs", "--skip-dlcs"} & set(s.install(_game("epic"), base=str(tmp_path)).argv)


def test_gog_install_options(tmp_path, monkeypatch):
    from cornerplay.stores import gog
    monkeypatch.setattr(gog, "find_tool", lambda name: "gogdl")
    s = gog.Gog()
    monkeypatch.setattr(s, "_token", lambda: None)
    argv = s.install(_game("gog"), base=str(tmp_path / "g"), dlcs=False, lang="de-DE").argv
    assert argv[argv.index("--path") + 1] == str(tmp_path / "g")
    assert "--with-dlcs" not in argv and argv[argv.index("--lang") + 1] == "de-DE"
    assert "--with-dlcs" in s.install(_game("gog"), base=str(tmp_path)).argv


def test_gog_update_keeps_the_language(tmp_path, monkeypatch):
    from cornerplay.config import game_options
    from cornerplay.stores import gog
    s = gog.Gog()
    g = _game("gog", "9")
    game_options.set(g.key, "gog_lang", "fr-FR")
    assert s.lang_of(g) == "fr-FR"
    game_options.set(g.key, "gog_lang", None)
    assert s.lang_of(g) == "en-US"
