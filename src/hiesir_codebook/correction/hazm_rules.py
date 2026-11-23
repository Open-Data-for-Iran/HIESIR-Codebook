"""hazm's rules: word fixes found with hazm's word list.

One of the finders of the automatic word fixes (:mod:`.words`): it reads every
label as the steps up to ``letters`` and the finders before it (learned,
folded) leave it, tries each rule below on each word, and proposes what it
finds; the ``autocorrect`` command writes it to
``output/2_corrected/autocorrect/words.csv`` with the other finders' fixes.

The rules ask the lexicon of :mod:`.lexicon` (hazm's word list, its verb
forms and ``curated/2_corrected/words.csv``, read with polars) whether a word
is *known* (hazm vouches for it), a known word with a suffix, or only *listed*.

============ ====================================================================
rule         what it fixes
============ ====================================================================
glued_vav    a word that starts with و and ranks higher without it (known >
             known with a suffix > listed > not listed; a tie keeps the word, as
             ``ورودی`` = ورود + ی and ``رودی`` = رود + ی): the conjunction glued
             to the next word
             (``ویخ`` -> ``و یخ``, ``وسنگی`` -> ``و سنگی``, ``وپلاستیکی`` ->
             ``و پلاستیکی``); ``ورنی``, ``ورودی``, ``ویفر`` stay, as their rest
             (``رنی``, ``رودی``) ranks no higher
glued_words  words written as one, or joined by a stray ZWNJ, cut into words
             (``پودرپیاز`` -> ``پودر پیاز``, ``صندلی‌چرخداربچه`` -> ``صندلی
             چرخدار بچه``): only a token hazm does not list; every part common
             (or used often in the labels); scored by how common the parts are
             and how few, a cut the labels write elsewhere gaining a bonus; kept
             only when it clearly leads the next cut.  A token printed every year
             is cut only around a joining word (و, در, سایر ...), so compounds
             written joined (لباسشویی) stay whole
joined_plural  a known word with the plural (ها, های, هایی) joined to it
             without its ZWNJ, on the labels as ``glued_vav`` leaves them
             (``سالنهای`` -> ``سالن‌های``); left alone after ا د ذ ر ز ژ و
             (``کالاها``), when hazm vouches for the word as written
             (``تنها``), and when it may be a glued و as well (``وبهای``)
compound     two words hazm lists as one compound with a ZWNJ, even where the
             questionnaires always print them apart (``تخم مرغ`` -> ``تخم‌مرغ``,
             ``نمک سود`` -> ``نمک‌سود``), or as one written joined where the
             questionnaires print it joined too (``زرد آلو`` -> ``زردآلو``; ``صورت
             حساب``, never printed joined, stays); never with a function word, a
             verb phrase (``پرداخت شده``) or a head the house style writes apart
             (``قابل حمل``)
spaced_suffix  a known word and a suffix written apart (ها, های, هایی, ترین, and
             ای after ه), on the labels as ``glued_vav`` leaves them: joined with
             a ZWNJ, or with nothing after ا د ذ ر ز ژ و, on the labels as the
             rules above leave them (``نمایش های`` ->
             ``نمایش‌های``, ``پارچه ای`` -> ``پارچه‌ای``, ``پودر های`` -> ``پودرهای``);
             left alone when the two together are a word of their own (``تن ها``
             / ``تنها``)
============ ====================================================================

Where a word row of ``spelling.csv`` matches a label, the rules leave that
stretch to it, both when they find their fixes and when the build applies them,
so a hand decision always wins; ``spaced_suffix``, which changes no word, may
cross it.
"""

from __future__ import annotations

import functools
import itertools
import math
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass

import polars as pl

from ..utils import ZWNJ
from .fixes import FixList
from .lexicon import COMMON, Lexicon
from .text import EDGE, LETTER, WORD, letters

RULES = ("glued_vav", "glued_words", "joined_plural", "compound", "spaced_suffix")

# suffixes a label may write as a word of their own, after a space: the plural,
# the superlative, and ای after ه (پارچه ای); تر stays out, as it is also a
# word (دستمال تر, a wet wipe)
SPACED = ("هایی", "های", "ها", "ترین", "ای")
# the plural, which takes a ZWNJ after a letter that joins (سالن‌های)
PLURALS = ("هایی", "های", "ها")
# letters that never join the next one: no ZWNJ is needed after them (کالاها)
_NON_JOINING = "اآأإدذرزژوؤة"

# glued_words: how the cutter weighs a cut (the numbers of the old spelling
# suggestions, which a person reviewed row by row)
RARE = 3  # at most this many uses in the labels counts as rare
PART = 1_000  # how common a word must be to be cut out of a glued token
PART_COST = 1.0  # what each word beyond two costs a cut (in log frequency)
SEEN_BONUS = 4.0  # what a cut gains when the labels write that phrase elsewhere
MARGIN = 2.0  # how far the best cut must lead the next to be applied
EDGE_AND = 3.0  # what a cut gains for a و glued to the start or end (the commonest glue here)
MAX_PARTS = 4
# short words a glued token may hold
_SHORT = ("و", "در", "از", "با", "به", "یا", "جز", "تا", "آن", "این")
# words that glue a phrase together: a token the labels repeat is cut only around one
_GLUE = (*_SHORT, "سایر", "نظیر", "شامل", "برای", "جهت", "انواع", "کلیه", "مانند", "مربوط", "هزینه")
# a ZWNJ before these stays (a suffix, not a word)
_KEEP_AFTER = (*PLURALS, "ای", "ی", "ام", "ات", "اش", "تر", "ترین")
_PLURAL = re.compile("(.+?)(ها|های|هایی)")
# a word followed by one of SPACED, spaced
_SPACED_PAIR = re.compile(f"(?<![{LETTER}])([{LETTER}]+) ({'|'.join(SPACED)})(?![{LETTER}])")


# --- the rules -------------------------------------------------------------------


@dataclass(frozen=True)
class Fix:
    find: str
    replace: str
    rule: str
    evidence: str


def glued_vav(w: str, lex: Lexicon) -> Fix | None:
    """``وپلاستیکی`` -> ``و پلاستیکی``: more of a word without its و than with it."""
    rest = w[1:]
    if not w.startswith("و") or not rest or rest.startswith(ZWNJ) or lex.level(rest) <= lex.level(w):
        return None
    return Fix(
        w, f"و {rest}", "glued_vav", f"hazm: {w} {_LEVEL[lex.level(w)]}; {rest} {_describe(rest, lex)}"
    )


_LEVEL = ("not listed", "listed, not vouched for", "a word with a suffix", "a word")


def _describe(w: str, lex: Lexicon) -> str:
    if n := lex.count(w):
        return f"{n:,}"
    if not lex.known(w) and (parts := lex.stem(w)):
        stem, suffix = parts
        return f"= {stem} {_describe(stem, lex)} + {suffix}"
    return _LEVEL[lex.level(w)]


# compound: words that never make half of a compound, and a second word that
# makes a verb phrase, which hazm's corpus joins (خریداری‌شده) but Persian writes
# apart; and the heads the house style writes apart (قابل حمل, غیر ...)
_FUNCTION = (*_SHORT, "که", "را", "هر", "نیز", "هم", "برای", "یک", "دو", "سه")
_VERB_PHRASE = ("شده", "نشده", "شود", "نشود", "شدن", "شوند", "گردد", "گردیده", "است", "باشد", "کرده", "کردن")
_APART_HEADS = ("قابل", "غیرقابل", "غیر")


def compound(a: str, b: str, lex: Lexicon, labels: Labels | None = None) -> Fix | None:
    """``تخم مرغ`` -> ``تخم‌مرغ``, ``نمک سود`` -> ``نمک‌سود``: two words hazm lists
    as one compound with a ZWNJ, written so even where the questionnaires
    always print them apart; ``زرد آلو`` -> ``زردآلو``: two words hazm lists as
    one written joined, where the questionnaires print them joined too (so
    ``صورت حساب``, never printed joined, stays).  Never with a function word
    (و, در, یک ...), a verb phrase (پرداخت شده) or a head the house style
    writes apart (قابل حمل)."""
    if a in _FUNCTION or b in _FUNCTION or b in _VERB_PHRASE or a in _APART_HEADS:
        return None
    joined = f"{a}{ZWNJ}{b}"
    if joined not in lex.words:
        glued = a + b
        if glued not in lex.words or labels is None or labels.count(glued) == 0:
            return None
        return Fix(
            f"{a} {b}",
            glued,
            "compound",
            f"hazm: {glued} {_describe(glued, lex)}; the labels write it joined",
        )
    written = labels is not None and (labels.count(joined) + labels.count(a + b)) > 0
    return Fix(
        f"{a} {b}",
        joined,
        "compound",
        f"hazm: {joined} {_describe(joined, lex)}" + ("; the labels write it joined" if written else ""),
    )


def spaced_suffix(word: str, suffix: str, lex: Lexicon) -> Fix | None:
    """``نمایش های`` -> ``نمایش‌های``, ``پودر های`` -> ``پودرهای``: a known word
    and a suffix written apart.  Left alone when the two written together are
    a word of their own (``تن ها`` / ``تنها``), or ای after anything but ه."""
    if len(word) < 2 or word.endswith(ZWNJ) or not lex.known(word):
        return None
    if suffix == "ای" and not word.endswith("ه"):
        return None
    if lex.known(word + suffix):
        return None
    joint = "" if word[-1] in _NON_JOINING else ZWNJ
    return Fix(
        f"{word} {suffix}",
        f"{word}{joint}{suffix}",
        "spaced_suffix",
        f"hazm: {word} {_describe(word, lex)}; {suffix} a suffix",
    )


class Labels:
    """What the rules may know of the labels: how often each word is written
    and all the text (to see whether a phrase is written somewhere), both
    whatever the forms of ی, ک and hamza (موسسات counts مؤسسات)."""

    def __init__(self, labels: pl.Series):
        words = labels.str.extract_all(WORD.pattern).explode().drop_nulls().to_frame("w")
        counts = words.group_by(letters.expr("w").alias("w")).len()
        self._uses: dict[str, int] = dict(zip(counts["w"], counts["len"], strict=True))
        self._text = letters("\n".join(labels))

    @classmethod
    def of(cls, labels: Iterable[str]) -> Labels:
        return cls(pl.Series(list(labels), dtype=pl.String))

    @classmethod
    def either(cls, printed: pl.Series, now: pl.Series, glued: Iterable[str] = ()) -> Labels:
        """Two views of the same labels: each word as often as the view that
        writes it more (a word an earlier fix respelled elsewhere still counts:
        بجز in بجزروانی), but a printed word the fixes only cut apart
        (``glued``: ونظایر, و + نظایر) is no word; and the phrases as the labels
        ``now`` read them."""
        out, before = cls(now), cls(printed)
        skip = {letters(w) for w in glued}
        for w, n in before._uses.items():
            if w not in skip:
                out._uses[w] = max(n, out._uses.get(w, 0))
        return out

    def seen(self, phrase: str) -> bool:
        """Do the labels write ``phrase`` somewhere, as whole words?"""
        phrase = letters(phrase)
        return (
            phrase in self._text
            and re.search(f"(?<!{EDGE}){re.escape(phrase)}(?!{EDGE})", self._text) is not None
        )

    def count(self, w: str) -> int:
        """How often the labels write ``w``."""
        return self._uses.get(letters(w), 0)


class Cutter:
    """Cuts a token into the words glued in it: every way of cutting it into
    two to four words that are each common (or used often in the labels) is
    scored by how common its words are and how few, a cut the labels write
    elsewhere gaining a bonus; the best wins when it clearly leads the next."""

    def __init__(self, lex: Lexicon, labels: Labels):
        self.lex, self.labels = lex, labels

    def common(self, w: str) -> bool:
        return w in _SHORT or self.lex.count(w) >= COMMON or self.labels.count(w) > RARE

    def part_ok(self, w: str) -> bool:
        """Can ``w`` be one of the words a token is cut into?  A plural counts as its stem."""
        if w in _SHORT:
            return True
        if len(w) < 3 or w in PLURALS or w.startswith("ء"):  # no word starts with a bare hamza
            return False
        if self.lex.count(w) >= PART or self.labels.count(w) > RARE:
            return True
        m = _PLURAL.fullmatch(w)
        return bool(m) and len(m.group(1)) >= 2 and self.part_ok(m.group(1))

    def base(self, w: str) -> str:
        """A part as the frequency lookup sees it: the stem of a plural it does not know."""
        m = _PLURAL.fullmatch(w)
        if m and not (self.lex.count(w) >= PART or self.labels.count(w) > RARE):
            return m.group(1)
        return w

    def render(self, w: str) -> str:
        """A part as written: a plural gets its ZWNJ (after a letter that joins)."""
        m = _PLURAL.fullmatch(w)
        if m and len(m.group(1)) >= 2 and self.lex.known(m.group(1)) and not self.lex.known(w):
            stem = m.group(1)
            return stem + ("" if stem[-1] in _NON_JOINING else ZWNJ) + m.group(2)
        return w

    def cuts(self, s: str) -> list[tuple[str, ...]]:
        """Every way to cut ``s`` into two to MAX_PARTS words."""
        if len(s) > 40:
            return []

        @functools.cache
        def go(i: int, k: int) -> list[tuple[str, ...]]:
            if i == len(s):
                return [()]
            if k == 0:
                return []
            out = []
            for j in range(i + 1, len(s) + 1):
                if self.part_ok(s[i:j]):
                    out += [(s[i:j], *rest) for rest in go(j, k - 1)]
            return out

        return [c for c in go(0, MAX_PARTS) if len(c) >= 2]

    def score(self, parts: tuple[str, ...]) -> float:
        """Mean log frequency of the words (و left out), less a cost per extra
        word, plus a bonus for a و at an edge and for a phrase the labels write."""
        words = [self.base(p) for p in parts if p != "و"] or list(parts)
        weight = [self.lex.count(p) + 100_000 * self.labels.count(p) for p in words]
        score = sum(math.log(1 + x) for x in weight) / len(words) - PART_COST * (len(parts) - 2)
        if parts[0] == "و" or parts[-1] == "و":
            score += EDGE_AND
        return score + (SEEN_BONUS if self.labels.seen(" ".join(map(self.render, parts))) else 0.0)

    def is_word(self, w: str) -> bool:
        return w == "و" or self.lex.listed(w) or self.lex.level(w) >= 2

    def segment(self, s: str, force: bool = False) -> tuple[str, bool]:
        """``s`` (no ZWNJ) cut into words, and whether the cut is sure: its words
        are common and it clearly beats the next best one.  ``s`` itself when it
        is a word or cannot be cut (``force``: even when the labels use it often)."""
        if self.is_word(s) or (not force and self.labels.count(s) > RARE) or s.startswith("ال"):
            return s, True
        ranked = sorted(self.cuts(s), key=self.score, reverse=True)
        if not ranked:
            return s, True
        best = self.compounds(ranked[0])
        if len(best) == 1:
            return s, True
        clear = len(ranked) == 1 or self.score(ranked[0]) - self.score(ranked[1]) >= MARGIN
        return " ".join(map(self.render, best)), clear and all(self.common(self.base(x)) for x in best)

    def compounds(self, parts: tuple[str, ...]) -> tuple[str, ...]:
        """``parts`` with each compound head joined to the word before it
        (اطو + کشی -> اطوکشی, عزا + داری‌ها -> عزاداری‌ها), but never to a
        short word such as و."""
        out: list[str] = []
        for p in parts:
            if out and out[-1] not in _SHORT and p not in _SHORT and self.lex.compound_head(p):
                out[-1] += p
            else:
                out.append(p)
        return tuple(out)

    def cut(self, w: str) -> tuple[str, bool]:
        """``w`` with its glued words apart, and whether that is sure.  A token
        the labels repeat is no proof it is a word (a glue printed every year
        repeats too), so only hazm rules a token out; a repeated token without
        a ZWNJ is cut only around a word that glues a phrase (و, در, سایر ...)
        or as the labels write it elsewhere, which keeps compounds written
        joined (لباسشویی) whole.  Each ZWNJ is judged on its own: it stays
        before a suffix, after می, in a compound hazm knows or between pieces
        the labels write as one token; elsewhere it is a space."""
        if self.is_word(w):
            return w, True
        segs = w.split(ZWNJ)
        if len(segs) == 1 and self.labels.count(w) > RARE:
            cut, sure = self.segment(w, force=True)
            if not (any(x in _GLUE for x in cut.split(" ")) or (" " in cut and self.labels.seen(cut))):
                return w, True
            return cut, sure
        first, sure = self.segment(segs[0])
        out = [first]
        for prev, seg in itertools.pairwise(segs):
            keep = (
                self.labels.count(prev + ZWNJ + seg) > RARE
                or seg in _KEEP_AFTER
                or prev in ("می", "نمی")
                or self.lex.listed(prev + ZWNJ + seg)
                or self.lex.compound_head(seg)
            )
            suffix = next((x for x in PLURALS if seg.startswith(x) and seg != x), None)
            if not keep and suffix:  # هزینه‌هایپرداختی: the suffix stays, the next word is glued to it
                cut, ok = self.segment(seg[len(suffix) :])
                out.append(f"{ZWNJ}{suffix} {cut}")
            else:
                cut, ok = self.segment(seg)
                out.append((ZWNJ if keep else " ") + cut)
            sure = sure and ok
        return "".join(out), sure


def unlicensed_joins(text: str, lex: Lexicon) -> int:
    """How many ZWNJs of ``text`` join two pieces nothing vouches for as one
    word: not a compound hazm lists, nor a suffix (های, ای ...), a verb's stem
    after its word, or می before its verb (``حق‌بیمه‌استعلاجی‌…`` has many)."""
    n = 0
    for w in WORD.findall(text):
        for a, b in itertools.pairwise(w.split(ZWNJ)):
            licensed = (
                b in _KEEP_AFTER or a in ("می", "نمی") or lex.listed(f"{a}{ZWNJ}{b}") or lex.compound_head(b)
            )
            n += not licensed
    return n


def glued_words(w: str, lex: Lexicon, cutter: Cutter | None = None) -> Fix | None:
    """``پودرپیاز`` -> ``پودر پیاز``, ``لباسزیر`` -> ``لباس زیر``,
    ``صندلی‌چرخداربچه`` -> ``صندلی چرخدار بچه``: words written as one, or
    joined by a stray ZWNJ, cut when the cut is sure (see :class:`Cutter`)."""
    if cutter is None or (ZWNJ not in w and len(w) < 4):
        return None
    new, sure = cutter.cut(w)
    if new == w or not sure:
        return None
    parts = [x for x in re.split(f"[ {ZWNJ}]", new) if x]
    seen = "; the labels write it so elsewhere" if cutter.labels.seen(new) else ""
    return Fix(
        w,
        new,
        "glued_words",
        "hazm: " + " + ".join(f"{x} {_describe(x, lex)}" for x in parts) + f"; {w} not a word{seen}",
    )


def joined_plural(w: str, lex: Lexicon) -> Fix | None:
    """``سالنهای`` -> ``سالن‌های``: a known word with the plural joined to it
    without its ZWNJ.  Left alone after a letter that does not join
    (``کالاها`` needs none), when hazm vouches for the word as written
    (``تنها``, ``تنهایی``, ``آنها``), and when it may be a glued و as well
    (``وبهای``: وب + های, or و + بهای; ``glued_vav`` ties, ``spelling.csv``
    decides)."""
    if w.startswith("و") and lex.level(w[1:]) >= 2:
        return None
    head, _, last = w.rpartition(ZWNJ)
    for suffix in PLURALS:
        stem = last[: -len(suffix)]
        if not last.endswith(suffix) or len(stem) < 2:
            continue
        full = f"{head}{ZWNJ}{stem}" if head else stem
        if stem[-1] in _NON_JOINING or w in lex.words or not (lex.known(full) or lex.known(stem)):
            return None
        return Fix(
            w,
            f"{full}{ZWNJ}{suffix}",
            "joined_plural",
            f"hazm: {stem} {_describe(stem, lex)}; {w} not a word as written",
        )
    return None


# the rules on one word, each pass reading the label as the one before leaves it
WORD_PASSES: tuple[Callable[..., Fix | None], ...] = (glued_vav, glued_words, joined_plural)


def _join_pairs(text: str, rule: Callable[[str, str], str]) -> str:
    """``text`` with ``rule`` asked of each two words a single space apart, left
    to right; a pair it changes is not asked again with the next word."""
    pieces = WORD.split(text)
    words = WORD.findall(text)
    out, i = [pieces[0]], 0
    while i < len(words):
        if i + 1 < len(words) and pieces[i + 1] == " ":
            pair = f"{words[i]} {words[i + 1]}"
            new = rule(words[i], words[i + 1])
            if new != pair:
                out += [new, pieces[i + 2]]
                i += 2
                continue
        out += [words[i], pieces[i + 1]]
        i += 1
    return "".join(out)


# --- reading the labels once ---------------------------------------------------------


def find_fixes(
    labels: pl.DataFrame,
    lex: Lexicon,
    protected: FixList | None = None,
    context: Labels | None = None,
) -> pl.DataFrame:
    """The fixes the rules find in ``labels`` (``year``, ``label``):
    ``find``, ``replace``, ``kind`` (the rule) and ``evidence``, in the order
    the rules run.  They are found in passes, each on the label as the passes
    before leave it: the rules on one word (``WORD_PASSES``: ``وسالنهای`` ->
    ``و سالنهای`` -> ``و سالن‌های``), then ``compound`` on two words, then
    ``spaced_suffix`` on a word and the suffix after it.  Where a ``protected``
    fix (a word row of spelling.csv) matches, its words and pairs there are
    left to it (a hand decision wins).  Each distinct label is read once, each
    rule asked once per word."""
    protected = protected or FixList()
    cutter = Cutter(lex, context or Labels(labels["label"]))
    extra = {"glued_words": (cutter,), "compound": (cutter.labels,)}
    asked: dict[tuple[str, str], Fix | None] = {}

    def ask(rule: Callable[..., Fix | None], key: str, *args: str) -> str:
        """What ``key`` reads after ``rule``."""
        if (rule.__name__, key) not in asked:
            asked[rule.__name__, key] = rule(*args, lex, *extra.get(rule.__name__, ()))
        fix = asked[rule.__name__, key]
        return fix.replace if fix else key

    for label in labels["label"].unique(maintain_order=True):
        parts = []
        for text, free in protected.parts(label):
            if free:
                for rule in WORD_PASSES:
                    pieces = WORD.split(text)  # text between words, word, text, ...
                    out = [pieces[0]]
                    for w, after in zip(WORD.findall(text), pieces[1:], strict=True):
                        out += [ask(rule, w, w), after]
                    text = "".join(out)
                text = _join_pairs(text, lambda a, b: ask(compound, f"{a} {b}", a, b))
            parts.append(text)
        # a suffix joined to its word changes no word, so it may cross a stretch
        # a spelling.csv row matches (سی دی + های)
        for m in _SPACED_PAIR.finditer("".join(parts)):
            ask(spaced_suffix, m.group(0), m.group(1), m.group(2))

    return pl.DataFrame(
        [(f.find, f.replace, f.rule, f.evidence) for f in asked.values() if f],
        schema={"find": pl.String, "replace": pl.String, "kind": pl.String, "evidence": pl.String},
        orient="row",
    )
