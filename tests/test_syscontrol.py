"""syscontrol: what TV mode's quick access sends to gamescope, and how nmcli's fields are read."""
from cornerplay import syscontrol as s


def test_gamescope_values():
    assert s.gs_value("gs_filter", "fsr") == 2
    assert s.gs_value("gs_filter", "linear") is None       # the default clears the atom
    assert s.gs_value("gs_scaler", "integer") == 1
    assert s.gs_value("gs_sharpness", 20) == 0              # sharpest is gamescope's 0
    assert s.gs_value("gs_sharpness", 18) == 2
    assert s.gs_value("gs_fps_limit", 0) is None
    assert s.gs_value("gs_fps_limit", 40) == 40
    assert s.gs_value("gs_tearing", True) == 1 and s.gs_value("gs_tearing", False) is None


def test_nmcli_split_keeps_escaped_colons():
    assert s._split(r"*:My\:Net:70:WPA2") == ["*", "My:Net", "70", "WPA2"]
