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


XBOX = ("030000005e0400008e02000014010000,Xbox 360 Controller,a:b0,b:b1,back:b6,dpdown:h0.4,dpleft:h0.8,"
        "dpright:h0.2,dpup:h0.1,guide:b8,leftshoulder:b4,leftstick:b9,lefttrigger:a2,leftx:a0,lefty:a1,"
        "rightshoulder:b5,rightstick:b10,righttrigger:a5,rightx:a3,righty:a4,start:b7,x:b2,y:b3,platform:Linux")


def test_pad_layouts():
    from cornerplay import padlayout as p
    assert p.remap(XBOX, "") == XBOX
    swapped = dict(f.split(":", 1) for f in p.remap(XBOX, "nintendo").split(",")[2:])
    assert (swapped["a"], swapped["b"], swapped["x"], swapped["y"]) == ("b1", "b0", "b3", "b2")
    south = dict(f.split(":", 1) for f in p.remap(XBOX, "southpaw").split(",")[2:])
    assert (south["leftx"], south["rightx"], south["leftstick"]) == ("a3", "a0", "b10")
    assert p.remap(XBOX, "nintendo").startswith("030000005e0400008e02000014010000,Xbox 360 Controller,")
    p.current_mappings = lambda: [XBOX]
    assert p.env("swap_ab")["SDL_GAMECONTROLLERCONFIG"].count("a:b1") == 1
    assert p.env("none") == {} and p.env("") == {}
