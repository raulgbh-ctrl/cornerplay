from pathlib import Path

from PySide6.QtCore import QCoreApplication, QTranslator

from cornerplay import toastsi18n


def test_toasts_translate_with_their_parts():
    app = QCoreApplication.instance() or QCoreApplication([])
    tr = QTranslator()
    assert tr.load(str(Path(toastsi18n.__file__).parent / "i18n" / "cornerplay_ro.qm"))
    app.installTranslator(tr)
    try:
        assert toastsi18n.translate("Could not start Elden Ring: no Vulkan driver") == \
            "Nu am putut porni Elden Ring: no Vulkan driver"
        assert toastsi18n.translate("Saves of Hades backed up") == "Salvările Hades au fost copiate"
        assert toastsi18n.translate("Demo mode: Steam is not changed") == "Mod demo: Steam nu e modificat"
        assert toastsi18n.translate("something nobody wrote") == "something nobody wrote"
    finally:
        app.removeTranslator(tr)


def test_templates_are_current():
    """tools/toast_templates.py was run after the last toast changed."""
    import subprocess
    import sys
    root = Path(toastsi18n.__file__).parent.parent
    before = (root / "cornerplay/toastsi18n.py").read_text()
    subprocess.run([sys.executable, str(root / "tools/toast_templates.py")], check=True, capture_output=True)
    assert (root / "cornerplay/toastsi18n.py").read_text() == before


def test_health_rows_are_translatable():
    """Every health-check row name is a template (rerun tools/toast_templates.py after changing health.py)."""
    from cornerplay import health, toastsi18n
    rows = health.checks({}, gamepad_available=True)
    for r in rows:
        assert r["name"] in toastsi18n.TEMPLATES or any(rx.match(r["name"]) for _, rx in toastsi18n._patterns()), r["name"]


def test_template_with_empty_part():
    from cornerplay import toastsi18n
    assert any(t == "%1 found%2" for t, rx in toastsi18n._patterns() if rx.match("umu-run found"))
