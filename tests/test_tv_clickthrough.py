"""TV mode: every full-screen page must stop clicks from reaching the covers on Home behind it
(the user hit games starting from clicks on Settings, a game's page, Downloads...)."""
from pathlib import Path

QML = Path(__file__).resolve().parent.parent / "cornerplay" / "qml"
PAGES = ["TvDownloads", "TvPhone", "TvGameNight", "TvStats", "TvRoulette", "TvPadTest", "TvWho",
         "TvPage", "TvLibrary"]


def test_every_tv_page_has_a_shield():
    for name in PAGES:
        assert "TvShield" in (QML / f"{name}.qml").read_text(), f"{name}.qml lets clicks through to Home"


def test_tv_pages_let_the_guide_through():
    # Pages that take every key must still pass F10 / F9 (Guide, quick access) up to TvView.
    for name in ["TvDownloads", "TvPhone", "TvGameNight", "TvStats", "TvRoulette", "TvPage"]:
        src = (QML / f"{name}.qml").read_text()
        assert "Qt.Key_F10 || event.key === Qt.Key_F9) { event.accepted = false" in src, name


def test_home_covers_are_guarded():
    src = (QML / "TvView.qml").read_text()
    assert "interactive: tv.homeLive" in src
    assert "onActivated: { if (!tv.pointerOk()) return" in src
    assert "function closePages(" in src
