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
