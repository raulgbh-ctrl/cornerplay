"""Plugins: small Python files of your own that hook into Cornerplay.

A plugin is a folder in ~/.local/share/cornerplay/plugins/<name>/ with a plugin.py that has
    NAME = "Shown name"
    DESCRIPTION = "One line"
    def register(api): ...
Plugins run with your own rights, like any program you start, so Cornerplay only loads the
ones you switched on (Settings > Advanced > Plugins); a new folder starts switched off.

What `api` offers (plugins/README.md has an example of each):
    api.shelf(id, name, test)          a TV Home row and Library list: test(game) -> bool,
                                       game = {"key", "title", "store", "installed", "playtime" (s),
                                       "lastPlayed", "genres"}
    api.on_game_start(fn)              fn(game) when a game starts
    api.on_game_stop(fn)               fn(game) when it closes
    api.action(label, fn)              a row in TV mode's Guide menu > Plugins and the desktop's
                                       Tools menu; fn() runs when chosen
    api.toast(text)                    a message at the bottom of the window
    api.setting(name, default)         a value kept for the plugin (plugins.json)
    api.set_setting(name, value)
A plugin that raises is switched off for the session and its error shows in Settings.
"""
import importlib.util
import sys
import traceback

from .config import DATA_DIR, read_json, write_json

FOLDER = DATA_DIR / "plugins"
STATE = DATA_DIR / "plugins.json"   # {"on": [names], "settings": {name: {...}}}


class Api:
    def __init__(self, name, host):
        self._name, self._host = name, host

    def shelf(self, sid, name, test):
        self._host["shelves"].append({"id": f"p:{self._name}:{sid}", "name": str(name), "test": test, "plugin": self._name})

    def on_game_start(self, fn):
        self._host["start"].append((self._name, fn))

    def on_game_stop(self, fn):
        self._host["stop"].append((self._name, fn))

    def action(self, label, fn):
        self._host["actions"].append({"id": f"{self._name}:{len(self._host['actions'])}", "label": str(label),
                                      "plugin": self._name, "fn": fn})

    def toast(self, text):
        self._host["toast"](str(text))

    def setting(self, name, default=None):
        return ((read_json(STATE) or {}).get("settings") or {}).get(self._name, {}).get(name, default)

    def set_setting(self, name, value):
        st = read_json(STATE) or {}
        st.setdefault("settings", {}).setdefault(self._name, {})[name] = value
        write_json(STATE, st)


def available():
    """Every plugin folder: [{"name", "title", "description", "on", "error"}] (not loaded)."""
    on = set((read_json(STATE) or {}).get("on") or [])
    out = []
    if FOLDER.is_dir():
        for d in sorted(FOLDER.iterdir()):
            f = d / "plugin.py"
            if d.is_dir() and f.is_file():
                title, desc = d.name, ""
                try:
                    for line in f.read_text(errors="replace").splitlines()[:60]:
                        if line.startswith("NAME") and "=" in line:
                            title = line.split("=", 1)[1].strip().strip("\"'") or d.name
                        elif line.startswith("DESCRIPTION") and "=" in line:
                            desc = line.split("=", 1)[1].strip().strip("\"'")
                except OSError:
                    pass
                out.append({"name": d.name, "title": title, "description": desc, "on": d.name in on})
    return out


def set_on(name, on):
    st = read_json(STATE) or {}
    names = [n for n in st.get("on") or [] if n != name] + ([name] if on else [])
    st["on"] = names
    write_json(STATE, st)


def load(toast):
    """Load the switched-on plugins. Returns the host: shelves, start/stop hooks, actions, errors."""
    host = {"shelves": [], "start": [], "stop": [], "actions": [], "errors": {}, "toast": toast}
    for p in available():
        if not p["on"]:
            continue
        path = FOLDER / p["name"] / "plugin.py"
        try:
            spec = importlib.util.spec_from_file_location(f"cornerplay_plugin_{p['name']}", path)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = mod
            spec.loader.exec_module(mod)
            mod.register(Api(p["name"], host))
        except Exception:
            host["errors"][p["name"]] = traceback.format_exc(limit=3).strip().splitlines()[-1]
    return host


def call(host, kind, game):
    """Run the start / stop hooks; one that raises is dropped and its error kept."""
    for name, fn in list(host.get(kind) or []):
        try:
            fn(dict(game))
        except Exception:
            host["errors"][name] = traceback.format_exc(limit=3).strip().splitlines()[-1]
            host[kind] = [(n, f) for n, f in host[kind] if n != name]


def test_of(host, sid):
    s = next((s for s in host.get("shelves") or [] if s["id"] == sid), None)
    return s["test"] if s else None


EXAMPLE = '''NAME = "Short games"
DESCRIPTION = "A Home row of games you have played less than two hours"


def register(api):
    api.shelf("short", "Quick to try", lambda g: g["installed"] and g["playtime"] < 2 * 3600)
    api.on_game_start(lambda g: print("Starting", g["title"]))
    api.action("Say hello", lambda: api.toast("Hello from a plugin"))
'''


def make_example():
    """Put an example plugin (switched off) in the plugins folder, and open-able README."""
    d = FOLDER / "example"
    d.mkdir(parents=True, exist_ok=True)
    if not (d / "plugin.py").exists():
        (d / "plugin.py").write_text(EXAMPLE)
    readme = FOLDER / "README.md"
    if not readme.exists():
        readme.write_text("# Cornerplay plugins\n\n" + (__doc__ or "") + "\n\nSee example/plugin.py.\n")
    return str(FOLDER)

