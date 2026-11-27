"""Every preset keeps its text readable (WCAG 4.5:1) on the surfaces it sits on."""
import pytest

from cornerplay import theme


@pytest.mark.parametrize("name", sorted(theme.PRESETS))
def test_preset_text_reads(name):
    t = theme.build(*theme.PRESETS[name])
    assert theme.contrast(t["outline"], t["surfaceContainerHigh"]) >= 4.5
    assert theme.contrast(t["onSurfaceVariant"], t["surfaceContainer"]) >= 4.5
    assert theme.contrast(t["primary"], t["background"]) >= 4.5
    assert theme.contrast(t["onPrimary"], t["primary"]) >= 4.5


def test_contrast_known_values():
    assert round(theme.contrast("#000000", "#ffffff"), 1) == 21.0
    assert theme.contrast("#777777", "#777777") == 1.0


def test_packs_use_real_settings():
    from cornerplay.config import DEFAULTS
    for name, pack in theme.PACKS.items():
        assert pack["theme_mode"] in theme.PRESETS, name
        for key, value in pack.items():
            assert key in DEFAULTS, (name, key)
            assert type(value) is type(DEFAULTS[key]), (name, key)


def test_seasons_and_tint_stay_readable():
    assert theme.season(12, 24) == "winter" and theme.season(10, 31) == "halloween"
    assert theme.season(10, 20) == "autumn" and theme.season(7, 1, 21) == "summer" and theme.season(7, 1, 12) == ""
    for bg, acc in theme.PRESETS.values():
        for kind in theme.SEASON_TINT:
            t = theme.seasonal(theme.build(bg, acc), kind)
            assert theme.contrast(t["primary"], t["background"]) >= 4.5
            assert theme.contrast(t["onPrimary"], t["primary"]) >= 4.5
