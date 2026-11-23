"""Variants: one form for a word the same item prints two ways.

One of the finders of the automatic word fixes (:mod:`.words`).  An item
(one expenditure code; for a header or section title, its kind, section and
code) is printed every year; where two consecutive years print it with one
word written otherwise, and the two forms differ by one letter, the labels
should write that word one way, never in a form a row of ``spelling.csv``
rewrites.  It gets hazm's form when hazm's corpus writes it at least
HAZM_LEAD times as often as the others (``درآمد`` / ``درامد``, ``برآورد`` /
``براورد``, ``زغال`` / ``ذغال``); otherwise the form most rows of all the
labels write, then the form of the latest year (``بجز`` / ``به جز``,
``جابجایی`` / ``جابه‌جایی``, ``پینگ‌پونگ`` / ``پینگ‌پنگ``, ``بچگانه`` /
``بچه‌گانه``).  A form of several words counts as often as its rarest word.

Two forms are variants of one word (:func:`one_letter`) when, spaces and
ZWNJs aside, they differ by one letter changed anywhere but at the end
(``ذغال`` / ``زغال``; not ``شور`` / ``شوی``), or by one ``ه``, ``و`` or ``ئ`` (a
hamza's seat) added inside the word (``بجز`` / ``به جز``, ``آینه`` /
``آئینه``), or only in how hamza is written, or a tanwin (``تأتر`` / ``تئاتر``,
``مستقیما`` / ``مستقیماً``).  An ``ا``
added inside makes a variant only when hazm does not know both forms as common
words, which would be a singular and its broken plural (``کتاب`` / ``کتب``,
``مجلس`` / ``مجالس``; but ``کروات`` / ``کراوات``); a letter added at either end
never does (``لباس`` / ``لباسی``, a glued و).
They are also variants when they differ only in spaces and ZWNJs
(:func:`spacing`: ``جا به جایی`` / ``جابه‌جایی``).  A stretch where ``و``
stands alone is never a variant: with the spaces squeezed out, the و hides
where a word ends (``اثاثه و`` / ``اثاث و``, ``ته‌گرد و`` / ``ته گردو``).  Among
such forms, only those with the fewest words hazm does not know, then the fewest
ZWNJs nothing vouches for, count (never words joined by ZWNJs:
``حق‌بیمه‌استعلاجی‌…``); of these, the one hazm lists as
a single word wins, else the one most rows write; hazm's frequencies, which
cannot weigh one word against three, decide only between forms of other
letters.
"""

from __future__ import annotations

import difflib
import itertools
import re

import polars as pl

from ..utils import ZWNJ
from .canonical import unknown_words
from .fixes import FixList
from .hazm_rules import unlicensed_joins
from .lexicon import COMMON, Lexicon
from .text import WORD, whole

_INSIDE = "هوئ"  # the letters a variant may add or drop inside a word (ئ: a hamza seat)
_MAX_WORDS = 3  # how many words a varying stretch may hold (جا به جایی)
HAZM_LEAD = 10  # how many times as often hazm must write a form for it to win


def _squeeze(s: str) -> str:
    return s.replace(" ", "").replace(ZWNJ, "")


# hamza's seats, and tanwin: written or not, the word is the same (تأتر / تئاتر, مستقیما / مستقیماً)
_HAMZA = str.maketrans({"أ": "ا", "إ": "ا", "ؤ": "و", "ئ": None, "ء": None, "\u064b": None})


def one_letter(a: str, b: str, lex: Lexicon | None = None) -> bool:
    """Are ``a`` and ``b`` (spaces and ZWNJs aside) one word written two ways?"""
    a, b = _squeeze(a), _squeeze(b)
    if a == b or min(len(a), len(b)) < 3:
        return False
    if a.translate(_HAMZA) == b.translate(_HAMZA):  # hamza written otherwise: تأتر / تئاتر
        return True
    ops = [o for o in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes() if o[0] != "equal"]
    if len(ops) != 1:
        return False
    tag, i1, i2, j1, j2 = ops[0]
    if tag == "replace":
        return i2 - i1 == 1 and j2 - j1 == 1 and i2 < len(a)
    added = a[i1:i2] or b[j1:j2]
    inside = 0 < i1 < len(a) and 0 < j1 < len(b)
    if len(added) != 1 or not inside:
        return False
    if added == "ا":
        # a singular and its broken plural are two words hazm knows well
        # (کتاب / کتب, مجلس / مجالس); a rare word written two ways is one (کروات / کراوات)
        return lex is None or min(lex.count(a), lex.count(b)) < COMMON
    return added in _INSIDE


def spacing(a: str, b: str) -> bool:
    """Do ``a`` and ``b`` differ only in spaces and ZWNJs?"""
    return a != b and _squeeze(a) == _squeeze(b) and len(_squeeze(a)) >= 4


def variant(a: str, b: str, lex: Lexicon | None = None) -> bool:
    """One word (or a few) written two ways, with no و standing alone: with
    the spaces squeezed out, a و beside a word hides where the word ends
    (``اثاثه و`` / ``اثاث و``, ``ته‌گرد و`` / ``ته گردو``)."""
    if "و" in a.split(" ") + b.split(" "):
        return False
    return one_letter(a, b, lex) or spacing(a, b)


def item_pairs(labels: pl.DataFrame, lex: Lexicon | None = None) -> list[tuple[str, str, str, int, int]]:
    """``(form, form, item, year, year)`` for every word an item prints two
    ways in consecutive years (``labels``: ``year``, ``key``, ``label``)."""
    out = []
    for (key,), g in (
        labels.unique(["key", "year"], maintain_order=True).sort("year").group_by("key", maintain_order=True)
    ):
        years = list(g.select("year", "label").iter_rows())
        for (ya, a), (yb, b) in itertools.pairwise(years):
            if a == b:
                continue
            ta, tb = WORD.findall(a), WORD.findall(b)
            for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, ta, tb, autojunk=False).get_opcodes():
                if tag != "replace" or i2 - i1 > _MAX_WORDS or j2 - j1 > _MAX_WORDS:
                    continue
                # the whole stretch, else any word or two of it against any of the other
                # ("، آینه" / "و آئینه" differ in a و beside the word)
                x, y = " ".join(ta[i1:i2]), " ".join(tb[j1:j2])
                found = [(x, y)] if variant(x, y, lex) else []
                if not found:
                    found = [(p, q) for p in _runs(ta[i1:i2]) for q in _runs(tb[j1:j2]) if variant(p, q, lex)]
                out += [(p, q, key, ya, yb) for p, q in found[:1]]
    return out


def _runs(words: list[str]) -> list[str]:
    """Every run of one to _MAX_WORDS words in a row of ``words``."""
    return [" ".join(words[i : i + n]) for n in range(1, _MAX_WORDS + 1) for i in range(len(words) - n + 1)]


def choose(forms: list[str], uses: dict[str, int], last: dict[str, int], lex: Lexicon) -> str:
    """The form a group of variants takes (see the module): the forms of the
    same letters settled by spacing first, then the letters."""
    classes: dict[str, list[str]] = {}
    for f in sorted(forms):
        classes.setdefault(_squeeze(f), []).append(f)

    def spaced(members: list[str]) -> str:
        # never a form with more words hazm does not know, or more ZWNJs nothing
        # vouches for (words joined by ZWNJs)
        def worse(f: str) -> tuple[int, int]:
            return len(unknown_words(f, lex)), unlicensed_joins(f, lex)

        fewest = min(worse(f) for f in members)
        members = [f for f in members if worse(f) == fewest]
        one_word = [f for f in members if " " not in f and lex.known(f)]
        if len(one_word) == 1:
            return one_word[0]
        return max(members, key=lambda f: (uses[f], last[f]))

    reps = {spaced(m): m for m in classes.values()}
    if len(reps) == 1:
        return next(iter(reps))
    corpus = {f: _count(f, lex) for f in reps}
    ranked = sorted(reps, key=lambda f: (-corpus[f], f))
    if corpus[ranked[0]] >= HAZM_LEAD * max(corpus[ranked[1]], 1):
        return ranked[0]
    total = {f: sum(uses[g] for g in m) for f, m in reps.items()}
    return max(sorted(reps), key=lambda f: (total[f], last[f]))


def variant_fixes(labels: pl.DataFrame, hand: FixList, lex: Lexicon) -> pl.DataFrame:
    """The ``variant`` fixes for ``labels`` (``year``, ``key``, ``label``):
    ``find``, ``replace``, ``kind``, ``evidence``."""
    pairs = item_pairs(labels, lex)
    # forms joined by any pair are one word; union-find over the forms
    parent: dict[str, str] = {}

    def root(f: str) -> str:
        parent.setdefault(f, f)
        while parent[f] != f:
            parent[f] = parent[parent[f]]
            f = parent[f]
        return f

    seen: dict[frozenset, tuple[str, int, int]] = {}
    for x, y, key, ya, yb in pairs:
        parent[root(x)] = root(y)
        seen.setdefault(frozenset((x, y)), (key, ya, yb))
    forms = list(parent)
    # how many rows write each form as whole words, and the latest year
    distinct = labels.group_by("label").agg(pl.len().alias("n"), pl.col("year").max().alias("last"))
    uses, last = dict.fromkeys(forms, 0), dict.fromkeys(forms, 0)
    patterns = {f: re.compile(whole(re.escape(f))) for f in forms}
    for label, n, year in distinct.iter_rows():
        for f in forms:
            if f in label and patterns[f].search(label):
                uses[f] += n
                last[f] = max(last[f], year)
    groups: dict[str, list[str]] = {}
    for f in forms:
        groups.setdefault(root(f), []).append(f)
    rows = []
    for members in groups.values():
        stable = [f for f in members if hand.apply(f) == f]
        if not stable:
            continue
        best = choose(stable, uses, last, lex)
        for f in members:
            if f == best:
                continue
            # the pair that showed f, with best if they were printed side by side
            key, ya, yb = seen.get(frozenset((f, best))) or next(v for k, v in seen.items() if f in k)
            rows.append(
                (
                    f,
                    best,
                    "variant",
                    f"item {key} prints both ({ya}, {yb}); the labels write {best} {uses[best]} "
                    f"times, {f} {uses[f]}; hazm {_count(best, lex):,} and {_count(f, lex):,}",
                )
            )
    return pl.DataFrame(
        rows,
        schema={"find": pl.String, "replace": pl.String, "kind": pl.String, "evidence": pl.String},
        orient="row",
    )


def _count(form: str, lex: Lexicon) -> int:
    return min(lex.count(w) for w in form.split(" "))
