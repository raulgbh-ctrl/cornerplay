"""Family limits: per person, a daily play time, a bedtime, and the games allowed (one
collection). A PIN guards leaving a limited person and changing the limits.

It is a gentle limit for the family PC and the TV, not a lock: Cornerplay refuses to start
games past a limit and closes them (with a warning five minutes before), and hides the games
outside the allowed collection, but a person at a desktop can still start games another way.

settings["family"]: {person: {"limit": minutes a day (0: none), "bedtime": "HH:MM" ("": none),
                              "only": a collection's name ("": every game)}}
settings["family_pin"]: "scrypt$salt$hash" ("" : no PIN). Older ones, "salt$sha256", are still
accepted and turned into scrypt the next time the PIN is typed right. A PIN is a few digits,
so the hash is made slow (scrypt), and five wrong PINs in a row make Cornerplay wait a minute
(longer each time) before it checks another.
"""
import hashlib
import hmac
import os
import time

from .config import settings


def rules(person: str) -> dict:
    r = (settings.get("family") or {}).get(person) or {}
    return {"limit": int(r.get("limit") or 0), "bedtime": str(r.get("bedtime") or ""), "only": str(r.get("only") or "")}


def limited(person: str) -> bool:
    r = rules(person)
    return bool(r["limit"] or r["bedtime"] or r["only"])


def set_rules(person: str, limit: int, bedtime: str, only: str):
    allf = dict(settings.get("family") or {})
    r = {"limit": max(0, int(limit)), "bedtime": bedtime if _hm(bedtime) is not None else "", "only": only or ""}
    if any(r.values()):
        allf[person] = r
    else:
        allf.pop(person, None)
    settings.set("family", allf)


def _hm(text):
    try:
        h, m = (int(x) for x in str(text).split(":"))
        return h * 60 + m if 0 <= h < 24 and 0 <= m < 60 else None
    except ValueError:
        return None


def has_pin() -> bool:
    return bool(settings.get("family_pin"))


def _scrypt(salt: str, pin: str) -> str:
    return hashlib.scrypt(str(pin).encode(), salt=bytes.fromhex(salt), n=2 ** 14, r=8, p=1, dklen=32).hex()


def set_pin(pin: str):
    if not pin:
        settings.set("family_pin", "")
        return
    salt = os.urandom(16).hex()
    settings.set("family_pin", f"scrypt${salt}${_scrypt(salt, pin)}")


_tries = {"wrong": 0, "until": 0.0, "rounds": 0}
MAX_WRONG = 5


def pin_wait() -> int:
    """Seconds before another PIN is checked (0: now)."""
    return max(0, int(_tries["until"] - time.time() + 0.999))


def pin_ok(pin: str) -> bool:
    stored = settings.get("family_pin") or ""
    if not stored:
        return True
    if pin_wait():
        return False
    if stored.startswith("scrypt$"):
        _, salt, digest = stored.split("$", 2)
        ok = hmac.compare_digest(_scrypt(salt, pin), digest)
    else:  # the old salted SHA-256: accepted once, then made scrypt
        salt, _, digest = stored.partition("$")
        ok = hmac.compare_digest(hashlib.sha256((salt + str(pin)).encode()).hexdigest(), digest)
        if ok:
            set_pin(str(pin))
    if ok:
        _tries.update(wrong=0, rounds=0)
        return True
    _tries["wrong"] += 1
    if _tries["wrong"] >= MAX_WRONG:
        _tries["rounds"] += 1
        _tries.update(wrong=0, until=time.time() + 60 * 2 ** (_tries["rounds"] - 1))  # 1, 2, 4 ... minutes
    return False


def minutes_today(sessions, now=None, running_since=()):
    """Minutes played since midnight: the session log plus games running now."""
    now = now or time.time()
    lt = time.localtime(now)
    midnight = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1))
    secs = sum(max(0.0, min(e, now) - max(s, midnight)) for _k, s, e in sessions if e > midnight)
    secs += sum(max(0.0, now - max(s, midnight)) for s in running_since if s)
    return secs / 60


def blocked(person: str, sessions, now=None, running_since=()):
    """Why this person may not play now ("" when they may): past bedtime, or the day's time used."""
    r = rules(person)
    now = now or time.time()
    if r["bedtime"]:
        bed = _hm(r["bedtime"])
        lt = time.localtime(now)
        mins = lt.tm_hour * 60 + lt.tm_min
        if bed is not None and (mins >= bed or mins < 6 * 60):  # until 6 in the morning
            return "bedtime"
    if r["limit"] and minutes_today(sessions, now, running_since) >= r["limit"]:
        return "limit"
    return ""


def minutes_left(person: str, sessions, now=None, running_since=()):
    """Minutes until a limit or bedtime stops play, or None when nothing limits today."""
    r = rules(person)
    now = now or time.time()
    left = []
    if r["limit"]:
        left.append(r["limit"] - minutes_today(sessions, now, running_since))
    if r["bedtime"]:
        bed = _hm(r["bedtime"])
        lt = time.localtime(now)
        mins = lt.tm_hour * 60 + lt.tm_min
        if bed is not None and mins >= 6 * 60:
            left.append(bed - mins)
    return min(left) if left else None
