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


def test_fps_cap_wins_over_the_profile(monkeypatch):
    from cornerplay import runner
    monkeypatch.setattr(runner, "_overrides", {"perf": "balanced", "fps_cap": 40, "perf_log": False, "show_fps": False})
    env = runner.perf_env("epic", "x")
    assert env["DXVK_FRAME_RATE"] == "40" and "fps_limit=40" in env["MANGOHUD_CONFIG"]
    assert env.get("WINE_FULLSCREEN_FSR") == "1"  # Balanced's upscaling stays
