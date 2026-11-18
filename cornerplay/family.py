"""Family limits: per person, a daily play time, a bedtime, and the games allowed (one
collection). A PIN guards leaving a limited person and changing the limits.

It is a gentle limit for the family PC and the TV, not a lock: Cornerplay refuses to start
games past a limit and closes them (with a warning five minutes before), and hides the games
outside the allowed collection, but a person at a desktop can still start games another way.

settings["family"]: {person: {"limit": minutes a day (0: none), "bedtime": "HH:MM" ("": none),
                              "only": a collection's name ("": every game)}}
settings["family_pin"]: "salt$sha256" ("" : no PIN)
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


def set_pin(pin: str):
    if not pin:
        settings.set("family_pin", "")
        return
    salt = os.urandom(8).hex()
    settings.set("family_pin", salt + "$" + hashlib.sha256((salt + pin).encode()).hexdigest())


def pin_ok(pin: str) -> bool:
    stored = settings.get("family_pin") or ""
    if not stored:
        return True
    salt, _, digest = stored.partition("$")
    return hmac.compare_digest(hashlib.sha256((salt + str(pin)).encode()).hexdigest(), digest)


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
