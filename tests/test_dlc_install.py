"""Installing DLC into the game's own copy or your copy of it on another store (AioLaunch.installDlcs)."""
import types
from types import SimpleNamespace as NS

import pytest

from cornerplay import app as A
from cornerplay.runner import StoreError

C = A.AioLaunch


class Store:
    def __init__(self, sid, fail=False):
        self.id, self.name, self.fail, self.calls, self.changes = sid, sid.title(), fail, [], 0

    def install_dlc(self, g, dlc_id):
        if self.fail:
            raise StoreError("no")
        self.calls.append((g.key, dlc_id))
        return NS(argv=["x"], env={})

    def changed(self):
        self.changes += 1


@pytest.fixture
def fx(monkeypatch):
    games = {k: NS(key=k, store=k.split(":")[0], title=k, installed=True) for k in ("epic:a", "steam:a", "gog:a")}
    stores = {"epic": Store("epic"), "steam": Store("steam"), "gog": Store("gog")}
    toasts, started = [], []
    f = NS(demo=False, stores=stores, procs={}, _paused={}, _queue=[], _dlc_cache={}, _dlc_pending={},
           model=NS(find=games.get, jobs={}), toast=NS(emit=toasts.append))
    f._guard = lambda k: (games.get(k), stores[games[k].store]) if k in games else (None, None)
    f._touch = lambda k: None
    f._options_for = lambda g: {}

    def start(g, kind, cmd):
        started.append((g.key, kind))
        f.procs[g.key] = object()
        f.model.jobs[g.key] = {"kind": kind}
    f._start_job = start
    for name in ("installDlcs", "_dlc_next", "dlcBusy", "_forget_dlcs"):
        setattr(f, name, types.MethodType(getattr(C, name), f))
    monkeypatch.setattr(A.runner, "using", lambda o: __import__("contextlib").nullcontext())

    def finish(key, code=0):  # what _job_done does for the DLC queue
        f.procs.pop(key, None)
        f.model.jobs.pop(key, None)
        if code != 0:
            f._dlc_pending.pop(key, None)
        f._dlc_next(key)
    return NS(f=f, games=games, stores=stores, toasts=toasts, started=started, finish=finish)


def test_each_copy_gets_its_own_dlc_one_after_another(fx):
    fx.f.installDlcs([{"key": "epic:a", "id": "d1"}, {"key": "epic:a", "id": "d2"}, {"key": "steam:a", "id": "s1"},
                      {"key": "epic:a", "id": "d1"}])  # a repeat is ignored
    assert fx.started == [("epic:a", "dlc"), ("steam:a", "dlc")]
    assert fx.stores["epic"].calls == [("epic:a", "d1")] and fx.f.dlcBusy("epic:a")
    fx.finish("epic:a")
    assert fx.stores["epic"].calls[-1] == ("epic:a", "d2")
    fx.finish("epic:a")
    assert not fx.f.dlcBusy("epic:a") and len(fx.stores["epic"].calls) == 2


def test_gog_installs_all_owned_dlc_in_one_go(fx):
    fx.f.installDlcs([{"key": "gog:a", "id": "1"}, {"key": "gog:a", "id": "2"}])
    fx.finish("gog:a")
    assert fx.stores["gog"].calls == [("gog:a", "1")]


def test_a_busy_copy_waits_its_turn(fx):
    fx.f.procs["epic:a"] = object()
    fx.f.model.jobs["epic:a"] = {"kind": "update"}
    fx.f.installDlcs([{"key": "epic:a", "id": "d1"}])
    assert fx.started == [] and fx.f.dlcBusy("epic:a")
    fx.finish("epic:a")  # the update finished
    assert fx.stores["epic"].calls == [("epic:a", "d1")]


def test_a_failure_stops_the_rest(fx):
    fx.f.installDlcs([{"key": "epic:a", "id": "d1"}, {"key": "epic:a", "id": "d2"}])
    fx.finish("epic:a", code=1)
    assert fx.stores["epic"].calls == [("epic:a", "d1")] and not fx.f.dlcBusy("epic:a")


def test_not_installed_or_gone_copies_are_refused(fx):
    fx.games["steam:a"].installed = False
    fx.f.installDlcs([{"key": "steam:a", "id": "s1"}, {"key": "nope:x", "id": "1"}, {"key": "", "id": "1"}, {}])
    assert fx.started == [] and any("first" in t for t in fx.toasts)


def test_uninstalled_while_waiting_drops_the_rest(fx):
    fx.f.installDlcs([{"key": "epic:a", "id": "d1"}, {"key": "epic:a", "id": "d2"}])
    fx.games["epic:a"].installed = False
    fx.finish("epic:a")
    assert len(fx.stores["epic"].calls) == 1 and not fx.f.dlcBusy("epic:a")


def test_store_refusing_clears_the_queue(fx):
    fx.stores["epic"].fail = True
    fx.f.installDlcs([{"key": "epic:a", "id": "d1"}, {"key": "epic:a", "id": "d2"}])
    assert fx.started == [] and not fx.f.dlcBusy("epic:a") and "no" in fx.toasts


def test_every_window_showing_the_copy_is_refreshed(fx):
    fx.f._dlc_cache = {"steam:a": (0, [{"gameKey": "epic:a"}]), "epic:a": (0, []), "gog:a": (0, [{"gameKey": "gog:a"}])}
    fx.f._forget_dlcs("epic:a")
    assert set(fx.f._dlc_cache) == {"gog:a"} and fx.stores["epic"].changes == 1


def test_cancel_drops_waiting_dlc(fx):
    fx.f._dlc_pending["epic:a"] = ["d2"]
    fx.f.cancel = types.MethodType(C.cancel, fx.f)
    fx.f._external_job = lambda k: False
    A.settings  # noqa: B018 - the real settings object answers night_queue
    fx.f.cancel("epic:a")
    assert "epic:a" not in fx.f._dlc_pending


def test_opening_the_window_clears_new_dlc_on_every_copy(monkeypatch):
    from cornerplay import dlcfinder
    cleared, touched = [], []
    monkeypatch.setattr(dlcfinder, "seen", lambda k: cleared.append(k) or True)
    games = {"epic:a": NS(key="epic:a", title="A"), "steam:a": NS(key="steam:a", title="A")}
    f = NS(demo=False, model=NS(find=games.get, touch=touched.append))
    f._copies = lambda g: [games["steam:a"]]
    C.dlcsSeen(f, "epic:a")
    assert cleared == ["epic:a", "steam:a"] and touched == ["epic:a", "steam:a"]
