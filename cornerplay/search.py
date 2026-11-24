"""Forgiving library search: "witcher 3", "baldurs gate", "rdr2" and "gta 5" all find their game.

A query matches a title when every word of it is found in the title (any order), after both
are folded the same way: lower case, accents and punctuation dropped, roman numerals read as
numbers (V = 5). A single word with no spaces also matches the title's initials, numbers
included ("rdr2" = Red Dead Redemption 2, "gtav" = Grand Theft Auto V, "botw").
"""
import re
import unicodedata
from functools import lru_cache

_ROMAN = {"i": "1", "ii": "2", "iii": "3", "iv": "4", "v": "5", "vi": "6", "vii": "7", "viii": "8",
          "ix": "9", "x": "10", "xi": "11", "xii": "12", "xiii": "13"}
_SMALL = {"the", "of", "a", "an", "and", "to", "in", "on", "for"}


def _fold(text: str) -> str:
    """Lower case with accents dropped from Latin letters only ("é" -> "e", "ș" -> "s"); other
    scripts keep their marks (ガ stays ガ, not カ), so their titles stay apart."""
    out = []
    for c in unicodedata.normalize("NFKD", (text or "").replace("\u2122", "").replace("\u00ae", "")):  # ™ is "TM" in NFKD
        if unicodedata.combining(c) and out and out[-1] < "\u0250":
            continue
        out.append(c)
    return unicodedata.normalize("NFKC", "".join(out)).lower()


@lru_cache(maxsize=8192)
def words(text: str, roman: bool = True) -> tuple:
    """The text as plain lower-case words: 'Baldur's Gate III' -> ('baldurs', 'gate', '3')."""
    t = _fold(text)
    t = re.sub(r"['’`]", "", t)                  # baldur's -> baldurs
    t = re.sub(r"(\d)([a-z])|([a-z])(\d)", lambda m: " ".join(x for x in m.groups() if x), t)  # rdr2 stays, "fallout4" -> "fallout 4"
    out = []
    for w in re.split(r"[\W_]+", t):              # any script: "ペルソナ", "Ведьмак" are words too
        if w:
            out.append(_ROMAN.get(w, w) if roman and (w != "i" or out) else w)  # a lone leading "I" is a word, not 1
    return tuple(out)


@lru_cache(maxsize=4096)
def _initials(title: str) -> tuple:
    """'Red Dead Redemption 2' -> ('rdr2', 'rr2', ...): with and without the small words, and
    with a roman numeral as its letters too ('Grand Theft Auto V' -> 'gta5' and 'gtav')."""
    out = []
    for ws in (words(title), words(title, roman=False)):
        out.append("".join(w if w.isdigit() or w in _ROMAN else w[0] for w in ws))
        out.append("".join(w if w.isdigit() or w in _ROMAN else w[0] for w in ws if w not in _SMALL))
    return tuple(out)


def compact(text: str) -> str:
    """A title as one run of letters and digits, for matching and cache keys, in any script:
    "Pokémon™: Co." -> "pokemonco", "Ведьмак 3" -> "ведьмак3" (not "", which every such title shared)."""
    t = _fold(text)
    return re.sub(r"[\W_]+", "", t)


def _query_words(query: str) -> tuple:
    return words(query)


def matches(query: str, title: str, extra=()) -> bool:
    """True when the query finds this title (or, word for word, one of the extra texts)."""
    q = _query_words(query)
    if not q:
        return True
    tw = words(title)
    joined = " ".join(tw)
    if all(any(t.startswith(w) or (len(w) > 2 and w in t) for t in tw) for w in q):
        return True
    if " ".join(q) in joined or "".join(q) in joined.replace(" ", ""):
        return True                                # "dead cells", "deadcells", "hollowknight"
    raw = re.sub(r"\s+", "", query.lower())
    if len(q) <= 2 and len(raw) >= 2 and raw.isalnum() and any(i.startswith(raw) for i in _initials(title)):
        return True
    for text in extra:
        ew = words(text)
        if ew and all(any(t.startswith(w) for t in ew) for w in q):
            return True
    return False


def score(query: str, title: str) -> int:
    """How well the query finds this title, for ranking (0 = not at all): the title starting
    with the query first, then words starting in order, then initials, then anywhere."""
    if not matches(query, title):
        return 0
    q, tw = _query_words(query), words(title)
    joined, qj = " ".join(tw), " ".join(q)
    if joined == qj:
        return 100
    if joined.startswith(qj):
        return 90
    if len(q) <= len(tw) and all(tw[i].startswith(w) for i, w in enumerate(q)):
        return 80
    raw = re.sub(r"\s+", "", query.lower())
    if any(i.startswith(raw) for i in _initials(title)):
        return 70
    if all(any(t.startswith(w) for t in tw) for w in q):
        return 60
    return 40
