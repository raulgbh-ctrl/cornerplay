"""Every test runs against a throwaway home: cornerplay.config creates its folders on import,
so HOME and the XDG folders are pointed at a temp dir before anything imports it."""
import os
import sys
import tempfile
from pathlib import Path

_HOME = Path(tempfile.mkdtemp(prefix="cornerplay-test-home-"))
os.environ["HOME"] = str(_HOME)
for var, sub in (("XDG_CONFIG_HOME", ".config"), ("XDG_DATA_HOME", ".local/share"), ("XDG_CACHE_HOME", ".cache")):
    os.environ[var] = str(_HOME / sub)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _no_real_backlight(monkeypatch, tmp_path_factory):
    """Never this PC's real screen: a stream's "start" step darkens /sys/class/backlight, and a
    test once ran it for real and turned the developer's laptop screen off."""
    from cornerplay import stream
    monkeypatch.setattr(stream, "BACKLIGHT_DIR", tmp_path_factory.mktemp("backlight"))
    monkeypatch.setattr(stream, "_start_watch", lambda *a, **k: None)


@pytest.fixture(autouse=True, scope="session")
def _one_qt_app():
    """One QGuiApplication for every test (a QCoreApplication made first by one test would stop
    a later one from drawing pictures or windows)."""
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtGui import QGuiApplication
    yield QCoreApplication.instance() or QGuiApplication([])
