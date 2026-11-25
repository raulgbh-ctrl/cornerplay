# PyInstaller spec for the Windows build: one folder, Cornerplay.exe without a console.
# Built by build.ps1 (which also fetches the backends and SDL2.dll it bundles).
import os
from PyInstaller.utils.hooks import collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, "..", ".."))
PKG = os.path.join(ROOT, "cornerplay")

# Everything that is not Python: QML, fonts, art, sounds, translations, icons.
datas = []
for sub in ("qml", "fonts", "art", "sounds", "i18n", "icons"):
    if os.path.isdir(os.path.join(PKG, sub)):
        datas.append((os.path.join(PKG, sub), os.path.join("cornerplay", sub)))
datas.append((os.path.join(PKG, "cornerplay.svg"), "cornerplay"))

binaries = []
extra = os.path.join(SPECPATH, "extra")  # build.ps1 puts SDL2.dll here
if os.path.isfile(os.path.join(extra, "SDL2.dll")):
    binaries.append((os.path.join(extra, "SDL2.dll"), "."))

a = Analysis(
    [os.path.join(SPECPATH, "entry.py")],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    # Modules Cornerplay imports by name at run time (helpers, stores, plugins).
    # Qt modules used only from QML (or imported lazily) are named so their QML plugins and
    # files come along: the sign-in window (WebEngine), trailers (Multimedia), dialogs, effects.
    hiddenimports=collect_submodules("cornerplay") + [
        "PySide6.QtWebEngineQuick", "PySide6.QtWebEngineCore", "PySide6.QtWebChannel", "PySide6.QtMultimedia",
        "PySide6.QtQuickControls2", "PySide6.QtQuickWidgets", "PySide6.QtSvg", "PySide6.QtTextToSpeech",
        "PySide6.QtNetwork", "PySide6.QtQml", "PySide6.QtQuick"],
    excludes=["tkinter", "PySide6.Qt3DCore", "PySide6.QtDesigner"],
)
pyz = PYZ(a.pure)
# Python's UTF-8 mode: Windows would otherwise read and write text (settings, game titles,
# Romanian, the store tools' output) in the old code page, and fail on letters it lacks.
options = [("X utf8", None, "OPTION")]
exe = EXE(
    pyz, a.scripts, options,
    exclude_binaries=True,
    name="Cornerplay",
    icon=os.path.join(SPECPATH, "cornerplay.ico"),
    console=False,
    version=os.path.join(SPECPATH, "version.txt") if os.path.isfile(os.path.join(SPECPATH, "version.txt")) else None,
)
coll = COLLECT(exe, a.binaries, a.datas, name="Cornerplay")
