"""Cornerplay: one library for Steam, Epic, GOG, Amazon and Battle.net."""
import argparse
import os
import shutil
import signal
import sys
from pathlib import Path


def load_fonts(app):
    """Use the bundled fonts (OFL, cornerplay/fonts) so the app looks the same on every desktop:
    Nunito, rounded like the logo's letters (the desktop's own font if it cannot load)."""
    from PySide6.QtGui import QFont, QFontDatabase
    ok = [QFontDatabase.addApplicationFont(str(f)) >= 0
          for f in sorted((Path(__file__).parent / "fonts").glob("*.ttf"))]
    if any(ok) and "Nunito" in QFontDatabase.families():
        font = QFont("Nunito")
        font.setPointSizeF(app.font().pointSizeF())
        font.setHintingPreference(QFont.PreferNoHinting)
        app.setFont(font)


def auto_scale():
    """A big screen the desktop does not scale (a 4K monitor or TV at 100%): grow the interface
    so it is not tiny. Desktops that scale already (most do; Qt picks that up) are left alone."""
    import shutil
    import subprocess
    width, desk = 0, 1.0
    try:
        if os.environ.get("HYPRLAND_INSTANCE_SIGNATURE") and shutil.which("hyprctl"):
            import json
            mons = json.loads(subprocess.run(["hyprctl", "monitors", "-j"], capture_output=True,
                                             text=True, timeout=3).stdout or "[]")
            mon = next((m for m in mons if m.get("focused")), mons[0] if mons else {})
            width, desk = int(mon.get("width", 0)), float(mon.get("scale", 1.0))
        elif os.environ.get("XDG_SESSION_TYPE") == "x11" and shutil.which("xrandr"):
            import re
            out = subprocess.run(["xrandr", "--current"], capture_output=True, text=True, timeout=3).stdout
            m = re.search(r" connected primary (\d+)x\d+", out) or re.search(r" connected (\d+)x\d+", out)
            width = int(m.group(1)) if m else 0
    except (OSError, ValueError, subprocess.SubprocessError):
        return 1.0
    if not width:
        # Other desktops (KDE, GNOME, niri on Wayland): what Qt saw on the last start, kept by
        # _note_screen_size. A desktop that scales itself already shows up as a ratio above 1.
        try:
            from .config import settings
            size, ratio = settings.get("screen_size") or [], float(settings.get("screen_dpr") or 1.0)
            width, desk = (int(size[0]) if len(size) == 2 else 0), ratio
        except (TypeError, ValueError):
            return 1.0
    if desk > 1.01 or width < 3200:
        return 1.0
    return min(2.5, round(width / 1920 * 4) / 4)  # 3840 wide -> 2x


def _note_screen_size(app):
    """Remember the main screen's size in pixels: gamescope draws games at it, also when a game
    starts from Steam through --play (no window to ask then)."""
    from .config import settings
    screen = app.primaryScreen()
    if not screen or app.platformName() == "offscreen":  # tests and headless runs have no real screen
        return
    dpr = round(float(screen.devicePixelRatio()), 2)
    size = screen.size() * dpr
    wh = [int(size.width()), int(size.height())]
    if wh[0] > 0 and wh[1] > 0 and settings.get("screen_size") != wh:
        settings.set("screen_size", wh)
    if settings.get("screen_dpr") != dpr:
        settings.set("screen_dpr", dpr)  # covers.hi_res(), and auto_scale() on desktops it cannot ask


def _load_translation(app):
    """The interface in the language from Settings > Appearance, or the system's when it is Automatic."""
    from PySide6.QtCore import QLocale, QTranslator
    from .config import settings
    lang = (settings.get("language") or "").strip() or QLocale.system().name()
    if lang.split("_")[0] == "en":
        return
    tr = QTranslator(app)
    if tr.load(QLocale(lang), "cornerplay", "_", str(Path(__file__).parent / "i18n")):
        app.installTranslator(tr)
        app._cornerplay_translator = tr  # keep it alive for as long as the app


def check_qml():
    """Compile every QML file (catches syntax and reserved-word mistakes before a restart)."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlComponent, QQmlEngine
    try:
        from PySide6.QtWebEngineQuick import QtWebEngineQuick
        QtWebEngineQuick.initialize()
    except ImportError:
        pass
    app = QGuiApplication.instance() or QGuiApplication(["cornerplay"])
    engine = QQmlEngine()
    bad = 0
    for qml in sorted((Path(__file__).parent / "qml").glob("*.qml")):
        c = QQmlComponent(engine, QUrl.fromLocalFile(str(qml)), QQmlComponent.PreferSynchronous)
        errors = [e.toString() for e in c.errors()]
        if errors and "QtWebEngine" in " ".join(errors) and "is not installed" in " ".join(errors):
            print(f"skip  {qml.name} (Qt WebEngine not installed)")
            continue
        print(("ok    " if not errors else "FAIL  ") + qml.name)
        for e in errors:
            print("      " + e)
        bad += bool(errors)
    del app
    return 1 if bad else 0


def fetch_backends():
    """Download the legendary / gogdl / nile release binaries into Cornerplay's data dir,
    each checked against the SHA-256 GitHub lists for it."""
    from .config import BACKEND_REPOS, BIN_DIR, find_tool
    from .host import BUNDLED_BIN
    from .net import download_checked, github_asset
    from .osinfo import WINDOWS, exe
    failed = 0
    for name, repo in BACKEND_REPOS.items():
        existing = find_tool(name)
        if existing and not existing.startswith((str(BIN_DIR), BUNDLED_BIN)):
            print(f"{name}: already available at {existing}")
            continue
        try:
            asset = f"{name}_windows_x86_64.exe" if WINDOWS else f"{name}_linux_x86_64"
            tag, url, sha = github_asset(repo, lambda n, asset=asset: n == asset)
            print(f"{name} {tag}: downloading {url}" + ("" if sha else " (no checksum published)"))
            print(f"{name}: installed to {download_checked(url, BIN_DIR / exe(name), sha, mode=0o755)}")
        except Exception as e:
            print(f"{name}: not downloaded: {e}")
            failed += 1
    # umu-launcher (Proton for non-Steam games): most distributions other than Arch do not
    # package it, so a portable copy (one Python zipapp) goes next to the others when it is missing.
    if not WINDOWS and not find_tool("umu-run") and not shutil.which("wine"):
        try:
            fetch_umu(BIN_DIR)
        except Exception as e:
            print(f"umu-launcher: not downloaded: {e}")
            failed += 1
    return 1 if failed else 0


def fetch_umu(bin_dir):
    import tarfile
    import tempfile
    from .net import download_checked, github_asset
    tag, url, sha = github_asset("Open-Wine-Components/umu-launcher", lambda n: n.endswith("-zipapp.tar"))
    print(f"umu-launcher {tag}: downloading {url}" + ("" if sha else " (no checksum published)"))
    bin_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        tar_path = download_checked(url, os.path.join(tmp, "umu.tar"), sha)
        with tarfile.open(tar_path) as tar:
            member = next(m for m in tar.getmembers() if m.isfile() and os.path.basename(m.name) == "umu-run")
            data = tar.extractfile(member).read()
    dest = bin_dir / "umu-run"
    with open(f"{dest}.part", "wb") as f:
        f.write(data)
    os.chmod(f"{dest}.part", 0o755)
    os.replace(f"{dest}.part", dest)
    print(f"umu-launcher: installed to {dest}")


def status():
    from .stores import all_stores
    for s in all_stores():
        if not getattr(s, "in_accounts", True):
            continue
        if s.problem():
            state = s.problem()
        elif s.id == "battlenet":
            state = s.account() or "ready; install the Battle.net app from its tile"
        else:
            state = ("signed in" + (f" as {s.account()}" if s.account() else "")) if s.logged_in() else "ready, not signed in"
        print(f"{s.name:14} {state}")
    return 0


def play_steam(appid, start_wait=180, poll=2.0, run=None, running=None, sleep=None):
    """A Steam game in the foreground (Sunshine's entries run `--play steam:<id>`): Steam starts
    it, and this waits until it closes, so a stream lasts exactly as long as the game.
    Steam may update the game or show a launcher first: it has `start_wait` seconds to appear."""
    import subprocess
    import time
    from . import session, steamrun
    from .stores.steam import Steam
    run = run or (lambda argv: subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                                start_new_session=True))
    running = running or steamrun.running
    sleep = sleep or time.sleep
    if not appid.isdigit():
        return 1
    try:
        cmd = Steam().launch(type("G", (), {"id": appid})())
    except Exception as e:
        session.notify("Steam game did not start", str(e))
        return 1
    run(cmd.argv)
    waited = 0.0
    while appid not in running():
        if waited >= start_wait:
            session.notify("Steam game did not start", "Steam did not start it within 3 minutes.")
            return 1
        sleep(poll)
        waited += poll
    while appid in running():
        sleep(poll)
    return 0


def play(key):
    """Start one game in the foreground: download saves, run it, upload saves.
    Steam (and Game Mode) treat the game as running for as long as this process lives."""
    import shlex
    from . import runner, saves, session
    from .config import CACHE_DIR, LOG_DIR, game_options, read_json
    from .stores import all_stores
    from .stores.base import Game
    if key.startswith("steam:"):
        return play_steam(key.split(":", 1)[1])
    stores = {s.id: s for s in all_stores() if s.id != "steam"}
    cached = {d["store"] + ":" + d["id"]: d for d in read_json(CACHE_DIR / "library.json") or []}
    if key not in cached or cached[key]["store"] not in stores:
        session.notify("Cornerplay", f"Game not found: {key}. Open Cornerplay once to refresh the library.")
        return 1
    game = Game.from_dict(cached[key])
    store = stores[game.store]
    opts = game_options.get("battlenet:battlenet-app" if game.store == "battlenet" else key)
    sync = saves.enabled_for(game)
    if sync:
        res = saves.sync(game, "download")
        if res["status"] == "conflict":
            sync = False  # never overwrite either side without asking; the app asks next time
            session.notify(f"{game.title}: saves not synced",
                           "Cloud and local saves both changed. Open Cornerplay to choose which to keep.")
    try:
        with runner.using(opts):
            cmd = store.launch(game)
    except Exception as e:
        session.notify(f"{game.title} did not start", str(e))
        return 1
    if opts.get("args"):
        cmd.argv += shlex.split(opts["args"])
    log = str(LOG_DIR / (key.replace(":", "_") + ".log"))
    return session.run(game, cmd.argv, cmd.env, cmd.cwd, log, sync)


def main():
    from .osinfo import hide_console_windows, run_frozen_helper
    if run_frozen_helper():  # the packaged Windows build, started as a helper (osinfo.python_argv)
        return 0
    hide_console_windows()
    ap = argparse.ArgumentParser(prog="cornerplay", description=__doc__)
    ap.add_argument("--fetch-backends", action="store_true",
                    help="download the legendary, gogdl and nile CLIs into ~/.local/share/cornerplay/bin")
    ap.add_argument("--fetch-sdl", action="store_true",
                    help="make sure controller support (SDL2) is there: a private copy when the system has none")
    ap.add_argument("--status", action="store_true", help="print what each store backend needs and exit")
    ap.add_argument("--tv", action="store_true", help="start full screen in TV mode (controller friendly)")
    ap.add_argument("--play", metavar="GAME",
                    help="start a game and wait for it to close (used by the shortcuts added to Steam)")
    ap.add_argument("--add-to-steam", action="store_true",
                    help="add Cornerplay to Steam (Game Mode) with artwork; closes and reopens Steam if needed")
    ap.add_argument("--background", action="store_true",
                    help="start in the tray, without the window (used when starting with the PC)")
    ap.add_argument("--overlay", action="store_true",
                    help="open or close the in-game panel of the Cornerplay that is running (bind it to a key)")
    ap.add_argument("--quick", action="store_true",
                    help="open or close quick access (volume, frame limit, quit...) over the game being played")
    ap.add_argument("--launcher", action="store_true",
                    help="open or close the small search-and-play window (bind it to a key); starts Cornerplay in the tray if needed")
    ap.add_argument("--nxm", metavar="URL",
                    help="install a mod from a Nexus Mods \"Mod Manager Download\" link (nxm://...)")
    ap.add_argument("--stream-display", nargs="+", metavar="start|stop",
                    help="fit the display to a Sunshine stream and back (Sunshine runs this; start takes W H FPS too)")
    ap.add_argument("--steam-sync", action="store_true", help=argparse.SUPPRESS)  # Game Mode: restart Steam with the games added
    ap.add_argument("--demo", action="store_true", help="open with sample games (nothing is launched)")
    ap.add_argument("--session", action="store_true",
                    help="run as a login session (loginsession.py): TV mode, and leaving it ends the session")
    ap.add_argument("--check", action="store_true", help="compile every QML file and report errors, then exit")
    ap.add_argument("--smoke-test", action="store_true", help=argparse.SUPPRESS)  # CI: open the window with sample games, close after a few seconds
    ap.add_argument("--fetch-umu", action="store_true", help=argparse.SUPPRESS)  # install.sh: a portable umu-launcher
    ap.add_argument("--userns-profile", action="store_true", help=argparse.SUPPRESS)  # install.sh: Ubuntu's AppArmor profile
    args = ap.parse_args()
    if args.smoke_test:
        args.demo = True
    if args.session:
        args.tv = True
    if args.userns_profile:
        from .userns import PROFILE_TEXT
        sys.stdout.write(PROFILE_TEXT)
        return 0
    if args.fetch_backends:
        return fetch_backends()
    if args.fetch_umu:
        from .config import BIN_DIR
        try:
            fetch_umu(BIN_DIR)
            return 0
        except Exception as e:
            print(f"umu-launcher: not downloaded: {e}")
            return 1
    if args.fetch_sdl:
        from . import sdl
        if sdl.system_has_it():
            print("SDL2 (controller support): the system's")
            return 0
        try:
            print(f"SDL2 (controller support): private copy at {sdl.fetch()}")
            return 0
        except Exception as e:
            print(f"SDL2 (controller support): not downloaded: {e}")
            return 1
    if args.stream_display:
        from . import stream
        return stream.display_command(args.stream_display[0], args.stream_display[1:4])
    if args.check:
        return check_qml()
    if args.status:
        return status()
    if args.play:
        return play(args.play)
    if args.steam_sync:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtGui import QGuiApplication
        _app = QGuiApplication(sys.argv[:1])  # artwork is drawn for games without any
        from . import steamgames
        from .config import LOG_DIR
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_DIR / steamgames.GAMEMODE_LOG, "a") as f:
            return steamgames.run_helper(log=lambda m: (f.write(m + "\n"), f.flush()))
    if args.add_to_steam:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtGui import QGuiApplication
        _app = QGuiApplication(sys.argv[:1])  # needed to draw the artwork
        load_fonts(_app)
        from . import steamshortcut, theme
        try:
            n = steamshortcut.add_with_restart(theme.current())
        except Exception as e:
            print(f"Not added: {e}")
            return 1
        print(f"Added Cornerplay to Steam for {n} account(s). It opens in TV mode from Game Mode.")
        return 0

    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QIcon
    from PySide6.QtNetwork import QNetworkAccessManager, QNetworkDiskCache
    from PySide6.QtQml import QQmlApplicationEngine, QQmlNetworkAccessManagerFactory

    from .app import AioLaunch
    from .config import CACHE_DIR
    from .gamepad import Gamepad

    class CachingFactory(QQmlNetworkAccessManagerFactory):
        """Gives QML images an on-disk HTTP cache so covers load once."""

        def create(self, parent):
            nam = QNetworkAccessManager(parent)
            cache = QNetworkDiskCache(nam)
            cache.setCacheDirectory(str(CACHE_DIR / "covers"))
            cache.setMaximumCacheSize(1 << 30)
            nam.setCache(cache)
            return nam

    # The built-in sign-in window needs Qt's web engine. Importing it here would load
    # Chromium on every start (~35 MB, ~0.1 s), so only set the two options it needs
    # before the app object exists; QML loads the engine when the sign-in window opens.
    from PySide6.QtCore import QLibraryInfo
    qml_dir = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.QmlImportsPath))
    web_login = (qml_dir / "QtWebEngine" / "qmldir").is_file()
    if web_login:
        from PySide6.QtCore import QCoreApplication, Qt
        from PySide6.QtQuick import QQuickWindow, QSGRendererInterface
        QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
        QQuickWindow.setGraphicsApi(QSGRendererInterface.OpenGL)

    # Interface size (Settings > Appearance): Qt scales everything; a QT_SCALE_FACTOR already set wins.
    try:
        from .config import settings as _settings
        scale = float(_settings.get("ui_scale") or 0.0)
    except (TypeError, ValueError):
        scale = 0.0
    if scale <= 0:
        scale = auto_scale()
    if abs(scale - 1.0) > 0.01 and "QT_SCALE_FACTOR" not in os.environ:
        os.environ["QT_SCALE_FACTOR"] = f"{scale:.2f}"
    # The window class must say "cornerplay" so desktops (KDE on the Steam Deck, X11 docks)
    # match the window to cornerplay.desktop and show its icon. Qt builds the class from
    # argv[0] and the application name; started as "python3 -m cornerplay" both were wrong.
    from PySide6.QtWidgets import QApplication  # QApplication, not QGuiApplication: the tray menu is a widget
    app = QApplication(["cornerplay"])
    from . import tray
    if (args.overlay or args.quick) and not args.demo:
        if tray.hand_over("quick" if args.quick else "overlay"):
            return 0
        print("Cornerplay is not running", file=sys.stderr)
        return 1
    if args.launcher and not args.demo and tray.hand_over("launcher"):
        return 0  # the running Cornerplay opens it
    if args.launcher:
        args.background = True  # not running yet: start in the tray, then open the launcher
    if args.nxm and not args.demo and tray.hand_over("nxm:" + args.nxm.strip()):
        return 0  # the running Cornerplay installs it
    if not args.demo and tray.hand_over("tv" if args.tv else "show"):
        return 0  # Cornerplay was already running (perhaps in the tray): it shows its window instead
    _note_screen_size(app)
    _load_translation(app)
    app.setApplicationName("cornerplay")
    app.setApplicationDisplayName("Cornerplay")
    from .host import FLATPAK_ID
    app.setDesktopFileName(FLATPAK_ID or "cornerplay")  # the Wayland app id: matches the .desktop file
    load_fonts(app)
    here = Path(__file__).parent
    icon = QIcon(str(here / "cornerplay.svg"))
    for png in sorted((here / "icons" / "app").glob("cornerplay-*.png")):
        icon.addFile(str(png))
    app.setWindowIcon(icon)
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    try:   # a stream that never said it ended (Sunshine crashed) must not leave this screen dark
        from . import stream as _stream
        _stream.screen_on()
    except Exception:
        pass
    from .ui import limit_malloc_arenas
    limit_malloc_arenas()
    cornerplay = AioLaunch(demo=args.demo)
    cornerplay.session_mode = bool(args.session)
    cornerplay.web_login = web_login
    gamepad = Gamepad(app)
    gamepad.screenshot.connect(cornerplay.takeScreenshot)
    cornerplay.gamepad = gamepad  # asked at check time: SDL only loads a moment after start-up
    cornerplay.setTvActive(bool(args.tv))
    factory = CachingFactory()
    has_video = (qml_dir / "QtMultimedia" / "qmldir").is_file()

    def build(hidden):
        """The interface (Main.qml) in a fresh QML engine. Built at start (unless started in the
        tray) and again whenever it was let go while out of sight (ui.py)."""
        engine = QQmlApplicationEngine()
        engine.setNetworkAccessManagerFactory(factory)
        ctx = engine.rootContext()
        ctx.setContextProperty("app", cornerplay)
        ctx.setContextProperty("library", cornerplay.proxy)
        ctx.setContextProperty("tvLibrary", cornerplay.tvProxy)
        ctx.setContextProperty("tvNextLibrary", cornerplay.tvNextProxy)
        ctx.setContextProperty("tvAllLibrary", cornerplay.tvAllProxy)
        ctx.setContextProperty("pad", gamepad)
        ctx.setContextProperty("startTv", bool(getattr(cornerplay, "_tv_active", False)) if ui.built_once else bool(args.tv))
        ctx.setContextProperty("startHidden", bool(hidden))
        ctx.setContextProperty("webLogin", web_login)
        # TV-mode trailers need Qt Multimedia's QML module; without it they are simply left out.
        ctx.setContextProperty("canPlayVideo", has_video)
        # Say why when the window cannot be built (a QML error), instead of quitting silently.
        engine.warnings.connect(lambda ws: [print("QML:", w.toString(), file=sys.stderr) for w in ws])
        engine.load(QUrl.fromLocalFile(str(here / "qml" / "Main.qml")))
        return engine

    from .ui import Ui

    def settings_light():
        from .config import settings as _s
        return bool(_s.get("light_background", True))
    ui = Ui(app, build)
    # Starting up (reading the stores, compiling the interface, decoding art) leaves tens of MB
    # freed but still held by the C allocator; hand it back once things have settled, and again
    # now and then (cheap: a few milliseconds). ~40 MB on a typical start.
    from PySide6.QtCore import QTimer
    from .ui import give_back_memory
    QTimer.singleShot(45_000, give_back_memory)
    _trim = QTimer(app, interval=10 * 60_000)
    _trim.timeout.connect(give_back_memory)
    _trim.start()
    # The game panel, quick access and the launcher live in the interface: build it first if it
    # was let go, then ask (a moment later, once its Connections exist).
    gamepad.overlay.connect(lambda: ui.run(cornerplay.overlayRequested.emit))
    gamepad.quickAccess.connect(lambda: ui.run(cornerplay.quickAccessRequested.emit))
    # Started with the PC, into the tray: no interface at all until it is opened.
    from PySide6.QtWidgets import QSystemTrayIcon
    in_tray_only = (bool(args.background) and not args.demo and not args.smoke_test
                    and QSystemTrayIcon.isSystemTrayAvailable() and settings_light())
    if not in_tray_only and not ui.load(hidden=bool(args.background)):
        print("Cornerplay could not open its window (see the QML errors above).", file=sys.stderr)
        return 1
    window = ui.window
    from . import wintitle
    wintitle.follow(app, cornerplay)  # Windows: the title bar takes the app's colours
    the_tray = tray.Tray(app, ui, cornerplay, start_hidden=args.background)
    if os.name == "nt" and the_tray.available:  # Windows: notifications are the tray icon's
        from PySide6.QtWidgets import QSystemTrayIcon
        from . import app as app_module
        app_module.TRAY_NOTIFY = lambda title, body, urgent: the_tray.icon.showMessage(
            title, body, QSystemTrayIcon.MessageIcon.Warning if urgent else QSystemTrayIcon.MessageIcon.Information, 8000)
    if not args.demo:
        def on_message(msg):
            if msg == "overlay":
                ui.run(cornerplay.overlayRequested.emit)
            elif msg == "quick":
                ui.run(cornerplay.quickAccessRequested.emit)
            elif msg == "launcher":
                ui.run(cornerplay.launcherRequested.emit)
            elif msg.startswith("nxm:"):
                the_tray.show_window(tv=False)
                ui.run(lambda: cornerplay.openNxm(msg[4:]))
            else:
                the_tray.show_window(tv=msg == "tv")
        instance = tray.Instance(on_message, app)  # noqa: F841 (kept alive)
    elif args.background and window is not None:
        window.setProperty("hiddenAtStart", False)
    if args.launcher:
        from PySide6.QtCore import QTimer
        QTimer.singleShot(1200, lambda: ui.run(cornerplay.launcherRequested.emit))
    if args.nxm and not args.demo:  # started by the link itself: install once the library is there
        from PySide6.QtCore import QTimer
        QTimer.singleShot(1500, lambda: cornerplay.openNxm(args.nxm))
    app.aboutToQuit.connect(cornerplay.shutdown)
    if args.smoke_test:  # the window opened without QML errors: wait a moment for late errors, then leave
        from PySide6.QtCore import QTimer
        failed = []
        ui.engine.warnings.connect(lambda ws: failed.extend(w for w in ws if "Error transferring" not in w.toString()))  # a missing cover online is not a broken app
        from PySide6.QtCore import QMetaObject, Q_ARG, Q_RETURN_ARG
        # A tour of what start-up alone never builds: every Settings tab, then a game's Options
        # (an Epic game's, where the Proton rows live; hidden on Windows).
        key = next((g.key for g in cornerplay.model.games if g.store == "epic"), "")
        for step in range(7):
            QTimer.singleShot(1500 + 600 * step, lambda step=step: print("smoke step", step, QMetaObject.invokeMethod(
                window, "smokeStep", Q_RETURN_ARG("QVariant"), Q_ARG("QVariant", step), Q_ARG("QVariant", key))))

        def finish():
            for w in failed:
                print("smoke test warning:", w.toString(), file=sys.stderr)
            print("smoke test:", "QML warnings" if failed else "ok")
            app.exit(3 if failed else 0)
        QTimer.singleShot(7000, finish)
    code = app.exec()
    ui.unload(now=True)
    return code


if __name__ == "__main__":
    sys.exit(main())
