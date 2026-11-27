"""Store sign-ins kept fresh in the background, so a launch never stops to ask for one.

Every few hours (and a while after Cornerplay starts) each signed-in store renews its session
the way its own tool does: legendary (Epic) re-uses and refreshes its login, GOG's refresh
token is exchanged for a new one, nile (Amazon) checks its session, and Steam's web sign-in
renews itself from its refresh cookie. A store whose session really ran out is reported once,
so Cornerplay can say "sign in again" before you press Play instead of when you do.
Works the same on Linux and Windows (the tools are the same).
"""
import time

EVERY = 6 * 3600       # seconds between rounds
FIRST = 3 * 60         # the first round, after the library settled

OK, EXPIRED, SKIPPED, OFFLINE = "ok", "expired", "skipped", "offline"
EXPIRED_WORDS = ("sign in again", "expired", "not signed in", "invalid_grant", "login failed",
                 "loggedin\": false", "please login", "re-authenticate")


def _expired(text) -> bool:
    t = str(text or "").lower()
    return any(w in t for w in EXPIRED_WORDS)


def _epic(store):
    from .stores.base import run
    import json
    r = run([store.tool(), "status", "--json"], timeout=90)
    out = r.stdout or ""
    try:
        account = str(json.loads(out[out.index("{"):]).get("account") or "")
    except ValueError:
        account = ""
    if account and "not logged in" not in account.lower():
        return OK
    if "not logged in" in account.lower() or _expired(out + (r.stderr or "")):
        return EXPIRED
    return OFFLINE


def _gog(store):
    store._token()  # renews it when it is close to running out; raises StoreError when it cannot
    return OK


def _amazon(store):
    import json
    from .stores.base import run
    r = run([store.tool(), "auth", "--status"], timeout=60)
    try:
        return OK if json.loads((r.stdout or "").strip().splitlines()[-1]).get("LoggedIn") else EXPIRED
    except (ValueError, IndexError, AttributeError):
        return EXPIRED if _expired(r.stdout) or _expired(r.stderr) else OFFLINE


def _steam_web(_store):
    from . import steamweb
    try:
        steamweb.token()
    except steamweb.NotSignedIn as e:
        return SKIPPED if "not signed in to steam" in str(e).lower() else EXPIRED
    return OK


CHECKS = {"epic": _epic, "gog": _gog, "amazon": _amazon, "steam": _steam_web}


def refresh(store_id, store) -> str:
    """One store's session renewed: OK, EXPIRED (sign in again), OFFLINE (could not tell, try
    later) or SKIPPED (not signed in, or nothing to renew)."""
    check = CHECKS.get(store_id)
    if not check:
        return SKIPPED
    try:
        if store_id != "steam" and not store.logged_in():
            return SKIPPED
        if store_id in ("epic", "amazon") and store.problem():
            return SKIPPED  # its tool is not there
        return check(store)
    except Exception as e:  # noqa: BLE001 - a store failing must never stop the others
        from .runner import StoreError
        if isinstance(e, StoreError) and _expired(e):
            return EXPIRED
        try:
            import requests
            if isinstance(e, requests.RequestException):
                return OFFLINE
        except ImportError:
            pass
        return EXPIRED if _expired(e) else OFFLINE


def refresh_all(stores: dict) -> dict:
    """{store_id: result} for every store that has a session to keep."""
    return {sid: refresh(sid, store) for sid, store in stores.items() if sid in CHECKS}


class Seen:
    """Which expired sign-ins were already told, so each is told once until it works again."""

    def __init__(self):
        self.told = {}

    def news(self, results: dict) -> list:
        out = []
        for sid, res in results.items():
            if res == EXPIRED and sid not in self.told:
                self.told[sid] = time.time()
                out.append(sid)
            elif res == OK:
                self.told.pop(sid, None)
        return out
