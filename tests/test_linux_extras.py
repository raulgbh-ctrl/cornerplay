"""The 2026-11-25 Linux extras: fast cores, ..."""
import os


def _w(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


def test_fast_cores_intel_hybrid(tmp_path):
    from cornerplay import cores
    _w(f"{tmp_path}/cpu_core/cpus", "0-15\n")
    _w(f"{tmp_path}/cpu_atom/cpus", "16-23\n")
    f = cores.fast(str(tmp_path))
    assert f["kind"] == "intel-hybrid" and f["cpus"] == list(range(16))


def test_fast_cores_amd_x3d_picks_the_big_cache(tmp_path):
    from cornerplay import cores
    for cpu in range(32):
        group = "0-7,16-23" if cpu % 16 < 8 else "8-15,24-31"
        _w(f"{tmp_path}/system/cpu/cpu{cpu}/cache/index3/shared_cpu_list", group)
        _w(f"{tmp_path}/system/cpu/cpu{cpu}/cache/index3/size", "98304K" if group.startswith("0") else "32768K")
    f = cores.fast(str(tmp_path))
    assert f["kind"] == "amd-x3d" and cores.to_list(f["cpus"]) == "0-7,16-23"


def test_fast_cores_nothing_on_an_ordinary_cpu(tmp_path):
    from cornerplay import cores
    for cpu in range(16):
        _w(f"{tmp_path}/system/cpu/cpu{cpu}/cache/index3/shared_cpu_list", "0-15")
        _w(f"{tmp_path}/system/cpu/cpu{cpu}/cache/index3/size", "16384K")
    assert cores.fast(str(tmp_path)) == {}
    assert cores.parse_list("0-3,8,10-11") == [0, 1, 2, 3, 8, 10, 11] and cores.to_list([3, 0, 1, 2, 8]) == "0-3,8"
