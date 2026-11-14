import pytest

from cornerplay.problems import explain


@pytest.mark.parametrize("log, fix", [
    ("./game: error while loading shared libraries: libSDL2-2.0.so.0: cannot open", "native"),
    ("write failed: No space left on device", "storage"),
    ("err: DXVK: No adapters found", "vulkan"),
    ("Starting EasyAntiCheat_EOS service", ""),
    ("err:module:import_dll Library MSVCP140.dll (needed by game.exe) not found", "vcrun"),
    ("err:module:load mscoree.dll failed", "dotnet"),
    ("wine: Unhandled page fault on read access", "proton"),
    ("err:module:import_dll Library xinput9.dll (needed by x) not found", "proton"),
])
def test_rules(log, fix):
    assert explain(log)["fix"] == fix


def test_names_the_missing_library():
    assert "libSDL2-2.0.so.0" in explain("x: error while loading shared libraries: libSDL2-2.0.so.0: no")["detail"]


def test_vulkan_beats_anticheat_when_both_appear():
    assert explain("EasyAntiCheat\nVK_ERROR_INITIALIZATION_FAILED")["fix"] == "vulkan"


@pytest.mark.parametrize("log", ["", None, "all fine, game exited normally"])
def test_nothing_recognisable(log):
    assert explain(log) == {}


@pytest.mark.parametrize("log, fix", [
    ("err:module:import_dll Library d3dx9_43.dll (needed by game.exe) not found", "winetricks:d3dx9"),
    ("err:module:import_dll Library XAudio2_7.dll not found", "winetricks:xact"),
    ("[S_API FAIL] SteamAPI_Init() failed; no appID found.", "steam"),
    ("bwrap: setting up uid map: Permission denied", "userns"),
    ("vkQueueSubmit failed: VK_ERROR_DEVICE_LOST", "proton"),
    ("terminate called after throwing an instance of 'std::bad_alloc'", ""),
    ("./game.x86: cannot execute binary file: Exec format error", "native"),
    ("err:module:import_dll Library d3dcompiler_47.dll not found", "winetricks:d3dcompiler_47"),
])
def test_more_rules(log, fix):
    assert explain(log)["fix"] == fix


def test_the_log_line_and_fix_label():
    out = explain("start\nfoo\nerr:module:import_dll Library d3dx9_43.dll (needed by x) not found\nbye")
    assert out["line"] == "err:module:import_dll Library d3dx9_43.dll (needed by x) not found"
    assert out["fixLabel"] == "Install DirectX 9-11"


def test_needs_and_base_rebuild_the_detail():
    out = explain("err:module:import_dll Library xinput9.dll (needed by x) not found")
    assert out["needs"] == "xinput9.dll" and out["detail"] == f"It needs {out['needs']}. " + out["base"]
