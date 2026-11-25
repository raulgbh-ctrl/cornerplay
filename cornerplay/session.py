"""Runs one game and uploads its cloud saves when it closes.

Cornerplay starts this as a detached process (python3 -m cornerplay.session <file>), so the
upload still happens if Cornerplay itself was closed while you played. The file holds
the game, its command, environment and working folder as JSON. Progress goes to
~/.cache/cornerplay/sessions/<key>.json, which Cornerplay watches to show what happened.
"""
import json
import os
import shutil
import subprocess
import sys
import time

from . import playtime
from .config import CACHE_DIR, write_json
from .stores.base import Game

SESSIONS = CACHE_DIR / "sessions"
ASK_WAIT = 10  # seconds Battle.net's sign-in window may show before it counts as waiting for you


def status_file(key):
    return SESSIONS / (key.replace(":", "_").replace("/", "_") + ".json")


def notify(title, body):
    if shutil.which("notify-send"):
        subprocess.run(["notify-send", "-a", "Cornerplay", "-i", "cornerplay", title, body], check=False)


def run(game, argv, env_extra, cwd, log_path, sync):
    """Run the game, wait for it, then upload saves. Returns the game's exit code."""
    out = status_file(game.key)
    write_json(out, {"key": game.key, "state": "playing", "since": time.time(), "title": game.title})
    env = dict(os.environ)
    env.update(env_extra or {})
    if cwd and not os.path.isdir(cwd):
        cwd = None
    started = time.time()
    ended = None
    presence = None
    try:
        from . import discord
        presence = discord.start(game, started)
    except Exception:
        presence = None  # Discord is a nicety; never in the way of playing
    with open(log_path, "w", encoding="utf-8") as log:
        try:
            # Its own process group, so Quit / Force close in Cornerplay reach Wine's helpers too.
            proc = subprocess.Popen(argv, env=env, cwd=cwd or None, stdout=log, stderr=subprocess.STDOUT,
                                    start_new_session=True)
            write_json(out, {"key": game.key, "state": "playing", "since": started, "title": game.title,
                             "pid": proc.pid})
            if game.store == "battlenet":
                code, started, ended = _battlenet(game, proc, out, started)
            elif game.store == "xbox" and game.install_path:
                code, started, ended = _follow_folder(game, proc, out, started)
            else:
                code = proc.wait()
        except OSError as e:
            log.write(f"Could not start: {e}\n")
            code = -1
    if presence:
        presence.clear()
    if game.store in playtime.TIMED and started:
        try:
            playtime.record(game.key, started, ended)
        except OSError:
            pass  # never lose the save upload over a playtime file
    result = {"status": "skipped", "message": ""}
    if sync:
        write_json(out, {"key": game.key, "state": "uploading", "since": time.time(), "title": game.title})
        from . import saves
        result = saves.sync(game, "upload")
        if result["status"] == "conflict":
            notify(f"{game.title}: saves not uploaded",
                   "The cloud has newer saves from another PC. Open Cornerplay to choose which to keep.")
        elif result["status"] == "error":
            notify(f"{game.title}: cloud save upload failed", result["message"])
    write_json(out, {"key": game.key, "state": "done", "exit": code, "sync": result,
                     "title": game.title, "since": time.time(), "started": started, "log": log_path})
    return code


def _norm(path):
    r"""A program path to compare folders by: / between parts, lower case, and Wine's Z:\ (the
    Linux root) taken off, so a game seen as Z:\home\... matches /home/..."""
    p = (path or "").replace("\\", "/").rstrip("/").lower()
    return p[2:] if p.startswith("z:/") else p


def _follow_folder(game, proc, out, started, wait_start=600, poll=2.0, grace=8.0):
    """Xbox games are started by someone else (explorer.exe on Windows, Nexus Launcher on Linux,
    which may hand the game to its window that is already open and return at once): follow the
    processes whose program is in the game's folder. Returns (exit code, started, ended);
    started is 0 when the game never showed up."""
    from .osinfo import process_programs
    root = _norm(game.install_path) + "/"
    t0, seen, gone_since, code = time.time(), None, None, None
    while True:
        if code is None:
            code = proc.poll()
        pids = [pid for pid, prog in process_programs() if _norm(prog).startswith(root)]
        if pids:
            if seen is None:
                seen = time.time()
            gone_since = None
            write_json(out, {"key": game.key, "state": "playing", "since": started, "title": game.title,
                             "pid": os.getpid(), "pids": pids})
        elif seen is not None:
            gone_since = gone_since or time.time()
            if time.time() - gone_since >= grace:  # gone for a while, not just restarting itself
                return (code or 0), seen, gone_since
        elif code is not None and time.time() - t0 > wait_start:
            return code, 0, 0  # it never started
        elif code not in (None, 0) and time.time() - t0 > 30:
            return code, 0, 0  # the launcher failed and nothing came up
        time.sleep(poll)


def _battlenet(game, proc, out, started):
    """Battle.net hands the game over and stays open (or quits): follow the game's own
    processes instead. This process stands for the session meanwhile (its pid is alive until
    the game closes); the game's pids go in the status file so Quit reaches the game itself.
    Returns (exit code, started, ended); started is 0 when the game never ran."""
    from . import bnethide
    from .config import settings
    from .stores.battlenet import BattleNet, close_launcher, launcher_running, watch
    store = BattleNet()
    state = {"pids": [], "needs": "", "was_open": launcher_running(store) or settings.get("battlenet_warm")}
    hide = bool(settings.get("battlenet_hide")) and bnethide.available()

    def status():
        write_json(out, {"key": game.key, "state": "playing", "since": started, "title": game.title,
                         "pid": os.getpid(), "pids": state["pids"], "needs": state["needs"]})

    from .config import game_options
    own = game_options.get(game.key)
    fast = own["fast_cores"] if "fast_cores" in own else settings.get("fast_cores")

    def changed(pids):
        state["pids"] = pids
        if fast:  # Battle.net starts the game, so taskset at our start does not reach it
            from . import cores
            for pid in pids:
                cores.pin(pid)
        status()

    def tick(running):
        if not hide:
            return
        bnethide.park()  # classic Hyprland has no rule: windows are moved as they appear
        ask = bnethide.asking() if not running else {}
        # Its sign-in window shows for a few seconds even when it signs in by itself: only one
        # that is still there after ASK_WAIT really waits for you.
        if not ask:
            state.pop("ask_since", None)
        elif time.time() - state.setdefault("ask_since", time.time()) < ASK_WAIT and not state["needs"]:
            ask = {}
        need = (ask.get("title") or "Battle.net") if ask else ""
        if need != state["needs"]:
            state["needs"] = need
            if ask:
                bnethide.show(ask)  # the sign-in or error window, where you are
            status()
    if hide:
        bnethide.rule(True)
    status()
    try:
        seen, gone = watch(store, game, proc, changed, on_tick=tick)
    finally:
        if hide and not settings.get("battlenet_warm"):
            bnethide.rule(False)
    if not state["was_open"] and seen:
        close_launcher(store)  # opened only for this game: closed with it (not mid-download)
    elif hide and not settings.get("battlenet_warm"):
        bnethide.show()  # it was open before: back where you can see it
    code = proc.poll()
    return (0 if code is None else code), seen, (gone or None)


def main(path):
    with open(path, encoding="utf-8") as f:
        job = json.load(f)
    os.remove(path)
    game = Game.from_dict(job["game"])
    run(game, job["argv"], job.get("env"), job.get("cwd"), job["log"], job.get("sync"))


if __name__ == "__main__":
    main(sys.argv[1])
