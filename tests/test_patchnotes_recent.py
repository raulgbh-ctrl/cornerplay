import time

from cornerplay import patchnotes
from cornerplay.config import write_json


def test_recent_reads_only_the_cache(tmp_path, monkeypatch):
    f = tmp_path / "patch_notes.json"
    monkeypatch.setattr(patchnotes, "FILE", f)
    monkeypatch.setattr(patchnotes, "_mem", {"mtime": None, "cache": {}})
    monkeypatch.setattr(patchnotes, "fetch", lambda appid: (_ for _ in ()).throw(AssertionError("no network")))
    now = time.time()
    write_json(f, {"10": {"t": now, "notes": [{"date": now - 2 * 86400}]},
                   "20": {"t": now, "notes": [{"date": now - 30 * 86400}]}})
    assert patchnotes.recent("10") is True
    assert patchnotes.recent("20") is False
    assert patchnotes.recent("30") is False
    assert patchnotes.recent("") is False
