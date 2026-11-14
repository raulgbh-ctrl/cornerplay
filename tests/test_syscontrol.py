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


def test_keyboard_layouts():
    from cornerplay import padkeys, kbdmouse

    class Dev:
        def __init__(self):
            self.log, self.down = [], set()

        def key(self, code, down):
            self.log.append(("key", code, down)); (self.down.add if down else self.down.discard)(code)

        def move(self, dx, dy):
            self.log.append(("move", dx, dy))

        def wheel(self, n, horizontal=False):
            self.log.append(("wheel", n))

        def release_all(self):
            self.down.clear()

        def close(self):
            pass
    m = padkeys.Mapper(padkeys.template("wasd"), Dev())
    m.button(0, True)
    assert m.dev.log[-1] == ("key", kbdmouse.KEYS["Space"], True)
    m.axis(1, -32000); m.tick()
    assert ("key", kbdmouse.KEYS["W"], True) in m.dev.log
    m.axis(5, 32000); m.tick()
    assert ("key", kbdmouse.BTN_LEFT, True) in m.dev.log
    m.axis(2, 32000); m.tick()
    assert any(e[0] == "move" and e[1] > 0 for e in m.dev.log)
    custom = padkeys.template("custom", {"left": "arrows", "buttons": {"a": "Enter"}})
    assert custom["left"] == "arrows" and custom["buttons"]["a"] == "Enter"
