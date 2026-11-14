"""Proton A/B test: play a game a few minutes on one Proton version, then on another, and
Cornerplay compares how they ran (MangoHud's logs, perf.py): average FPS, the 1 % low, stutters
and how long it took to start. Then it says which to keep.

One test per game at a time, kept in ~/.local/share/cornerplay/abtest.json:
  {key: {"a": proton, "b": proton, "minutes": 10, "step": "a" | "b" | "done",
         "results": {"a": {...}, "b": {...}}, "started": t}}
While a test runs, the game starts with the step's Proton version and records its performance
whatever the game's own settings say (app.py's _options_for).
"""
import os
import re
import time

from .config import DATA_DIR, read_json, write_json

FILE = DATA_DIR / "abtest.json"


def _all():
    return read_json(FILE, {}) or {}


def get(key):
    return _all().get(key) or {}


def start(key, a, b, minutes):
    data = _all()
    data[key] = {"a": a, "b": b, "minutes": int(minutes), "step": "a", "results": {}, "started": time.time()}
    write_json(FILE, data)
    return data[key]


def stop(key):
    data = _all()
    data.pop(key, None)
    write_json(FILE, data)


def proton_now(key):
    """The Proton version the next start of this game should use, or None (no test running)."""
    t = get(key)
    return t.get(t.get("step")) if t.get("step") in ("a", "b") else None


def load_seconds(log_path, started):
    """How long the game took to show its first frame: MangoHud names its log after the
    moment it began logging (<exe>_YYYY-MM-DD_HH-MM-SS.csv)."""
    m = re.search(r"(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})", os.path.basename(log_path or ""))
    if not m or not started:
        return 0
    try:
        t = time.mktime(time.strptime(m.group(1), "%Y-%m-%d_%H-%M-%S"))
    except ValueError:
        return 0
    return max(0, int(t - started)) if t - started < 600 else 0


def record(key, entry):
    """A session of the test ended with these numbers (perf.record's entry, or None when it was
    too short to say anything). Returns the test, moved on a step when the numbers count."""
    data = _all()
    t = data.get(key)
    if not t or t.get("step") not in ("a", "b"):
        return {}
    if entry and entry.get("minutes", 0) >= max(1, t["minutes"] // 2):
        t["results"][t["step"]] = entry
        t["step"] = "b" if t["step"] == "a" else "done"
        if t["step"] == "done":
            t["verdict"] = verdict(t["results"]["a"], t["results"]["b"], t["a"], t["b"])
    else:
        t["short"] = True  # played too briefly: the same step again
    data[key] = t
    write_json(FILE, data)
    return t


def verdict(ra, rb, a, b):
    """Which version ran it better, and the numbers that say so."""
    def pct(x, y):
        return round((y - x) * 100 / x) if x else 0
    keep_a, keep_b = a, b
    a, b = (os.path.basename((p or "").rstrip("/")) or "UMU-Proton" for p in (a, b))
    fps, low = pct(ra["avgFps"], rb["avgFps"]), pct(ra["low1"], rb["low1"])
    st_a, st_b = ra.get("stutters", 0), rb.get("stutters", 0)
    score = fps + low * 1.5 + (st_a - st_b) * 2
    la, lb = ra.get("load", 0), rb.get("load", 0)
    if la and lb:
        score += (la - lb) * 0.5
    winner = "b" if score > 5 else "a" if score < -5 else ""
    reasons = []
    if abs(fps) >= 3:
        reasons.append(f"{abs(fps)}% {'more' if fps > 0 else 'fewer'} frames on average with {b if fps > 0 else a}")
    if abs(low) >= 5:
        reasons.append(f"1% low {abs(low)}% {'higher' if low > 0 else 'lower'} with {b}")
    if st_a != st_b:
        reasons.append(f"{st_a} stutters with {a}, {st_b} with {b}")
    if la and lb and abs(la - lb) >= 3:
        reasons.append(f"started in {la} s with {a}, {lb} s with {b}")
    return {"winner": winner, "keep": {"a": keep_a, "b": keep_b}.get(winner, keep_a), "reasons": reasons,
            "same": not winner}
