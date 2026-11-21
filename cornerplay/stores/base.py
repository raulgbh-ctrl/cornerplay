"""Common shape of a store backend."""
import re
import subprocess
from dataclasses import dataclass, field, asdict

from ..runner import StoreError


@dataclass
class Game:
    store: str
    id: str
    title: str
    cover: str = ""
    cover_fallback: str = ""
    installed: bool = False
    install_path: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def key(self) -> str:
        return f"{self.store}:{self.id}"

    def to_dict(self):
        return asdict(self)

    @staticmethod
    def from_dict(d):
        return Game(**{k: d[k] for k in Game.__dataclass_fields__ if k in d})


@dataclass
class Command:
    argv: list
    env: dict = field(default_factory=dict)
    cwd: str = ""


class PartialResult(Exception):
    """fetch() got some games but part of it failed."""

    def __init__(self, games, message):
        super().__init__(message)
        self.games = games


class Store:
    id = ""
    name = ""
    color = "#888888"
    # True when install/uninstall is handed to an external client (Steam):
    # the command returns immediately and there is no progress to follow.
    external_installs = False
    dlc_note = ""
    login_kind = "paste"  # "paste": open URL then paste a code; "external": opens a client

    # --- state -----------------------------------------------------------
    def problem(self) -> str:
        """Empty when the backend is usable, otherwise what is missing."""
        return ""

    def logged_in(self) -> bool:
        return False

    def account(self) -> str:
        return ""

    # --- sign-in ---------------------------------------------------------
    def login_begin(self) -> dict:
        """Return {"url": ..., "prompt": ...} for the paste dialog."""
        raise StoreError("Sign-in is not supported for this store")

    def login_finish(self, text: str) -> None:
        raise StoreError("Sign-in is not supported for this store")

    def logout(self) -> None:
        pass

    def verify(self, game):
        """Check the game's files and fetch any that are missing or broken; a Command, or StoreError."""
        raise StoreError(f"{self.name} has no repair tool Cornerplay can run")

    # --- library ---------------------------------------------------------
    def fetch(self) -> list:
        """Blocking; runs on a worker thread. Return list[Game]."""
        return []

    def dlcs(self, game: Game) -> list | None:
        """Blocking. None if unsupported, else a list of
        {"id", "title", "status": installed|owned|available, "url", "image", "price", "canInstall"}."""
        return None

    def changed(self):
        """Something was installed or removed: forget short-lived caches of what is on disk."""

    def install_dlc(self, game: Game, dlc_id: str) -> Command:
        """Install one owned DLC of an installed game."""
        raise StoreError("Installing DLC is not supported for this store")

    # --- actions ---------------------------------------------------------
    def install(self, game: Game) -> Command:
        raise StoreError("Install is not supported for this store")

    def uninstall(self, game: Game) -> Command | None:
        """Return a Command to run, or None when it was done in-process."""
        raise StoreError("Uninstall is not supported for this store")

    def launch(self, game: Game) -> Command:
        raise StoreError("Launch is not supported for this store")

    def update(self, game: Game) -> Command:
        """Update an installed game. fetch() marks games that have one with extra["update"] = True."""
        raise StoreError("Updates are not supported for this store")


def run(argv, timeout=120, env=None) -> subprocess.CompletedProcess:
    """Run a backend CLI and capture its output."""
    import os
    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    try:
        return subprocess.run(argv, capture_output=True, text=True, timeout=timeout, env=full_env)
    except subprocess.TimeoutExpired:
        raise StoreError(f"{argv[0].rsplit('/', 1)[-1]} timed out")
    except OSError as e:
        raise StoreError(str(e))


# Side builds a store lists next to the real game: test servers, betas, playtests, demos.
_SIDE = re.compile(r"""(?:[\s:\-\u2013\u2014(]+|(?<=[a-z0-9])(?=[A-Z]))(?:
      public\s+test(?:ing|\s+server|\s+branch|\s+client)?
    | test\s+(?:server|branch|client|realm)
    | experimental(?:\s+server|\s+branch)?
    | (?:public\s+|tech\s+|open\s+|closed\s+)?beta(?:\s+client|\s+branch|\s+test)?
    | playtest | demo | pts
    )\)?\s*$""", re.I | re.X)
# Things sold as items that are not games: soundtracks, art books, wallpapers.
_EXTRA = re.compile(r"(?:\bsoundtrack|\bost|\bart\s*book|\bwallpapers?)\s*$", re.I)


def _norm(title):
    return re.sub(r"[^a-z0-9]", "", title.lower())


def side_build_of(title, others):
    """True when title is a test server, beta, playtest or demo of a game among others
    ("PUBG: Test Server" next to "PUBG: BATTLEGROUNDS", "KillingFloor2Beta")."""
    m = _SIDE.search(title)
    if not m:
        return False
    base = _norm(title[:m.start()])
    return len(base) >= 3 and any(o != title and not _SIDE.search(o) and _norm(o).startswith(base) for o in others)


def drop_side_builds(games):
    """Remove side builds and non-game extras from {id: Game} in place."""
    titles = [g.title for g in games.values()]
    for key in [k for k, g in games.items()
                if not g.installed and (_EXTRA.search(g.title) or side_build_of(g.title, titles))]:
        del games[key]
