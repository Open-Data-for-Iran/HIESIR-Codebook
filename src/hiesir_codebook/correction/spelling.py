"""Spelling suggestions from hazm's dictionary.

``curated/2_corrected/spelling.csv`` fixes the spellings people have listed.
This module looks for the rest: it reads every label as it stands after the
corrections, the punctuation clean-up and ``spelling.csv``, and checks each
word against hazm's word list (about 194,000 words with their frequency in a
large corpus) and its stemmer, and against the questionnaires' own words.  It writes what it finds
to ``output/2_corrected/spelling_suggestions.csv``:

========= =====================================================================
kind      what it finds
========= =====================================================================
plural    a plural with ``ها`` / ``های`` / ``هایی`` written without the ZWNJ,
          joined (``سبزیهای``) or spaced (``سبزی های``), whose stem is a word
          and which is not a word of its own (``تنها``, ``آنها`` stay)
broken    a word split by a space (``گو شت``, ``ا نواع``): the two pieces
          joined are a common word, and one of them is no word at all
he_ye     ``ه + ای`` without the ZWNJ: spaced (``پارچه ای`` -> ``پارچه‌ای``),
          or joined (``جادهای`` -> ``جاده‌ای``) when ``Xه`` is far more common
          than ``X`` (so not a plural of ``X``)
prefix    the verb prefix ``می`` / ``نمی`` spaced (``می شود`` -> ``می‌شود``)
compound  two words whose joined form is a common word in hazm, also with
          a suffix on the second (``ثبت نام`` -> ``ثبت‌نام``, ``اجاره بهای`` ->
          ``اجاره‌بهای``); applied on its own, except a verb phrase
          (``خریداری شده``, ``قابل حمل``), applied only when the printed
          questionnaires write it joined somewhere
glued     two or more words written as one (``پودرپیاز``, ``منزلو``), or
          joined by a stray ZWNJ: not a word, and it can be cut into words
          of the dictionary or of the questionnaires; the best cut has the
          most frequent words and few of them, and wins when the
          questionnaires write that phrase elsewhere
typo      a rare word that is no word, one letter away from a common one
          that starts with the same letter (``رایو`` -> ``رادیو``)
years     one item reads with the same letters but other spacing or ZWNJs in
          other years: the form all the labels write most wins, but never a
          form with a word the dictionary lacks over one without
          (``سایرحق`` -> ``سایر حق``, ``موتور سیکلت`` -> ``موتورسیکلت``)
========= =====================================================================

``apply`` says whether the build applies a suggestion on its own: ``yes``
for plural and broken suggestions on common words, and for glued words cut
into common words where the best cut clearly beats the next, and for years
suggestions where every other form has a word the dictionary lacks; ``no`` for
the others (a years choice between two spellings of known words), for
``he_ye`` (``فرآوردهای`` may be a plural with a ``ه`` lost) and for every typo,
since a rare word may be a name or a term the dictionary lacks.
``curated/2_corrected/spelling_suggestions.csv`` overrides it, one row per
suggestion (``find``): ``confirm`` applies it, ``reject`` blocks it,
``change`` applies ``replace`` instead.  Every row needs a ``reason``.

hazm is an optional dependency, needed only to regenerate the file:

    uv run --python 3.13 --extra hazm python -m hiesir_codebook.correction.spelling

The build (``correct``) only reads the file and the decisions, so it runs
without hazm.  Regenerate after changing the corrections or ``spelling.csv``.
"""

from __future__ import annotations

import argparse
import csv
import difflib
import functools
import itertools
import math
import re
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

from .. import CORRECTED, CURATED_CORRECTED, EXTRACTED
from ..utils import ZWNJ

SUGGESTIONS = CORRECTED / "spelling_suggestions.csv"
DECISIONS = CURATED_CORRECTED / "spelling_suggestions.csv"
KINDS = ("plural", "he_ye", "prefix", "compound", "broken", "glued", "typo", "years")
DECISION_KINDS = ("confirm", "reject", "change")

# a word as label fixes see it: letters, digits and ZWNJ (see correct._WORD_CHAR)
_WORD = re.compile(f"[ء-ٟٮ-ۓە۰-۹{ZWNJ}A-Za-z0-9]+")
_PERSIAN_ONLY = re.compile(f"[ء-يٮ-ۓە{ZWNJ}]+")
_PLURAL = re.compile("(.+?)(ها|های|هایی)")
_SUFFIXES = ("ها", "های", "هایی")
_KEEP_AFTER = (*_SUFFIXES, "ای", "ی", "ام", "ات", "اش", "تر", "ترین")  # a ZWNJ before these stays
_NON_JOINING = "اآأإدذرزژوؤ"  # letters that never join the next one
_SHORT = ("و", "در", "از", "با", "به", "یا", "جز", "تا", "آن", "این")  # short words a glued token may hold
_FUNCTION = (*_SHORT, "که", "را", "هر", "نیز", "هم", "برای")  # words that are never half of a compound
# words that glue a phrase together; a token the questionnaires repeat is only cut around one
# a second word that makes a verb phrase, a first word that heads an adjective
# phrase: hazm's corpus joins them (خریداری‌شده, قابل‌حمل), Persian writes them apart
_VERB_PHRASE = ("شده", "نشده", "شود", "نشود", "شدن", "شوند", "گردد", "گردیده", "است")
_PHRASE_HEAD = ("قابل", "غیرقابل")
_GLUE = (*_SHORT, "سایر", "نظیر", "شامل", "برای", "جهت", "انواع", "کلیه", "مانند", "مربوط", "هزینه")
_LETTERS = "ءآأؤئابپتثجچحخدذرزژسشصضطظعغفقکگلمنوهی"

COMMON = 10_000  # a common word in hazm's corpus
TYPO_TARGET = 50_000  # how common a typo's correction must be
RARE = 3  # at most this many uses in the questionnaires counts as rare
OWN_WORD = 50  # a plural form at least 1/50 as frequent as its stem is a word of its own
PART = 1_000  # how common a word must be to be cut out of a glued token
PART_COST = 1.0  # what each word beyond two costs a cut (in log frequency)
SEEN_BONUS = 4.0  # what a cut gains when the questionnaires write that phrase elsewhere
MARGIN = 2.0  # how far the best cut must lead the next to be applied on its own
EDGE_AND = 3.0  # what a cut gains for a و glued to the start or end (the commonest glue here)
MAX_PARTS = 4


def _key(w: str) -> str:
    """A word for lookup: no ZWNJ, and one way to write ی and ک."""
    return w.replace(ZWNJ, "").replace("ئ", "ی").replace("ي", "ی").replace("ك", "ک")


@dataclass
class Lexicon:
    """What the algorithm needs from hazm (tests pass a small one)."""

    freq: dict[str, int]  # word -> frequency
    stem: Callable[[str], str] = lambda w: w
    _bare: dict[str, int] = field(default_factory=dict, repr=False)
    _with_zwnj: dict[str, str] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        for w, n in self.freq.items():
            b = _key(w)
            self._bare[b] = max(n, self._bare.get(b, 0))
            if ZWNJ in w and n > self.freq.get(self._with_zwnj.get(b, ""), -1):
                self._with_zwnj[b] = w

    def zwnj_form(self, w: str) -> str | None:
        """How hazm writes ``w`` (no ZWNJ) when it has only a ZWNJ form of it:
        حشرهکش -> حشره‌کش.  A word hazm also lists joined (دستمال, نگهداری)
        stays: its corpus puts a ZWNJ in many words written joined."""
        if ZWNJ in w or w in self.freq:
            return None
        return self._with_zwnj.get(_key(w))

    def has(self, w: str) -> bool:
        """Is ``w`` a word (ignoring ZWNJs, ئ / ی, ي / ی and ك / ک)?"""
        return w in self.freq or _key(w) in self._bare

    def count(self, w: str) -> int:
        return self.freq.get(w, self._bare.get(_key(w), 0))


def hazm_lexicon() -> Lexicon:
    try:
        import hazm
    except ImportError as e:  # pragma: no cover - depends on the environment
        raise SystemExit(
            "hazm is not installed: "
            "uv run --python 3.13 --extra hazm python -m hiesir_codebook.correction.spelling"
        ) from e
    return Lexicon({w: n for w, n, _ in hazm.words_list()}, stem=hazm.Stemmer().stem)


@dataclass
class Suggestion:
    find: str
    replace: str
    kind: str
    apply: bool
    evidence: str
    uses: int = 0
    labels: set[str] = field(default_factory=set)
    years: set[int] = field(default_factory=set)


def _n(x: int) -> str:
    return f"{x:,}"


def years_text(years: Iterable[int]) -> str:
    """{1383, 1384, 1385, 1390} -> '1383-1385 1390'."""
    ys = sorted(years)
    if not ys:
        return ""
    out, start = [], ys[0]
    for a, b in zip(ys, [*ys[1:], None], strict=True):
        if b is None or b != a + 1:
            out.append(str(start) if start == a else f"{start}-{a}")
            start = b
    return " ".join(out)


class _Finder:
    def __init__(self, lex: Lexicon, uses: Counter, text: str = "", printed: str = ""):
        self.lex, self.uses, self.text, self.printed = lex, uses, text, printed

    def known(self, w: str) -> bool:
        """A word of the language or of the questionnaires."""
        return w == "و" or self.lex.has(w) or self.uses[w] > RARE

    def common(self, w: str) -> bool:
        return w in _SHORT or self.lex.count(w) >= COMMON or self.uses[w] > RARE

    def _part_ok(self, w: str) -> bool:
        """Can ``w`` be one of the words a glued token is cut into?  A plural
        counts as its stem."""
        if w in _SHORT:
            return True
        if len(w) < 3 or w in _SUFFIXES:
            return False
        if self.lex.count(w) >= PART or self.uses[w] > RARE:
            return True
        m = _PLURAL.fullmatch(w)
        return bool(m) and len(m.group(1)) >= 2 and self._part_ok(m.group(1))

    def _base(self, w: str) -> str:
        """A part as the frequency lookup sees it: the stem of a plural it does not know."""
        m = _PLURAL.fullmatch(w)
        if m and not (self.lex.count(w) >= PART or self.uses[w] > RARE):
            return m.group(1)
        return w

    def _render(self, w: str) -> str:
        """A part as written: a plural it does not know gets its ZWNJ."""
        base = self._base(w)
        if base == w:
            fix = self.plural(w)
            return fix.replace if fix else w
        return base + ("" if base[-1] in _NON_JOINING else ZWNJ) + w[len(base) :]

    def seen(self, phrase: str) -> bool:
        """Do the questionnaires write ``phrase`` somewhere (as whole words)?"""
        return phrase in self.text and _pattern(phrase).search(self.text) is not None

    def _score(self, parts: tuple[str, ...]) -> float:
        """Mean log frequency of the words (``و`` left out), less a cost per
        extra word, plus a bonus when the questionnaires write the phrase."""
        words = [self._base(p) for p in parts if p != "و"] or list(parts)
        weight = [self.lex.count(p) + 100_000 * self.uses[p] for p in words]
        score = sum(math.log(1 + x) for x in weight) / len(words) - PART_COST * (len(parts) - 2)
        if parts[0] == "و" or parts[-1] == "و":
            score += EDGE_AND
        return score + (SEEN_BONUS if self.seen(" ".join(map(self._render, parts))) else 0.0)

    def _he_ye_reading(self, w: str) -> bool:
        """Is ``Xهای`` rather ``Xه‌ای`` (``جادهای``) than a plural of ``X``?"""
        if not w.endswith("های"):
            return False
        base, stem = w[:-2], w[:-3]
        return self.lex.count(base) >= COMMON and self.lex.count(stem) * 10 < self.lex.count(base)

    # -- one word ---------------------------------------------------------------

    def missing_zwnj(self, w: str) -> Suggestion | None:
        """``حشرهکش`` -> ``حشره‌کش``: a compound written joined that hazm lists
        only with a ZWNJ (so ``glued`` takes it for a word).  hazm's corpus puts
        a ZWNJ in many words written joined (دست‌مال), so it applies on its own
        only when the questionnaires write it apart somewhere."""
        if ZWNJ in w or len(w) < 4:
            return None
        form = self.lex.zwnj_form(w)
        if form is None or form.split(ZWNJ)[-1] in _KEEP_AFTER:
            return None  # a suffix (ها, ای ...) is the plural and he_ye rules' business
        apart = self._printed(form) or self._printed(form.replace(ZWNJ, " "))
        return Suggestion(
            w,
            form,
            "compound",
            apart,
            f"hazm: {form} {_n(self.lex.count(form))}; {w} not listed"
            + ("; the questionnaires write it apart" if apart else ""),
        )

    def he_ye(self, w: str) -> Suggestion | None:
        """``جادهای`` is ``جاده‌ای`` (ه + ای), not a plural of ``جاد``."""
        if ZWNJ in w[-4:] or self.lex.has(w) or not self._he_ye_reading(w):
            return None
        base = w[:-2]
        return Suggestion(
            w,
            f"{base}{ZWNJ}ای",
            "he_ye",
            False,
            f"hazm: {base} {_n(self.lex.count(base))}; may also be a plural ({w[:-3]}{ZWNJ}های)",
        )

    def plural(self, w: str) -> Suggestion | None:
        m = _PLURAL.fullmatch(w)
        if not m or m.group(1).endswith(ZWNJ):
            return None
        stem, suffix = m.groups()
        if len(stem) < 2 or stem[-1] in _NON_JOINING or not self.lex.has(stem) or self._he_ye_reading(w):
            return None  # after ا د ذ ر ز ژ و the ZWNJ changes nothing
        own, base = self.lex.count(w), self.lex.count(stem)
        if own and own * OWN_WORD >= base:  # تنها, بها
            return None
        return Suggestion(
            w,
            f"{stem}{ZWNJ}{suffix}",
            "plural",
            self.common(stem),
            f"hazm: {stem} {_n(base)}; {w} {_n(own) if own else 'not a word'}",
        )

    def _cuts(self, s: str) -> list[tuple[str, ...]]:
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
                if self._part_ok(s[i:j]):
                    out += [(s[i:j], *rest) for rest in go(j, k - 1)]
            return out

        return [c for c in go(0, MAX_PARTS) if len(c) >= 2]

    def _segment(self, s: str, force: bool = False) -> tuple[str, bool]:
        """``s`` (no ZWNJ) cut into words, and whether the cut is sure: the
        words are common and the cut clearly beats the next best one.  ``s``
        itself when it is a word or cannot be cut (``force``: even when the
        questionnaires use it often)."""
        known = self.lex.has(s) or self.lex.has(self.lex.stem(s)) if force else self.known(s)
        if known or (not force and self.known(self.lex.stem(s))) or s.startswith("ال"):
            return s, True
        ranked = sorted(self._cuts(s), key=self._score, reverse=True)
        if not ranked:
            return s, True
        best = ranked[0]
        clear = len(ranked) == 1 or self._score(best) - self._score(ranked[1]) >= MARGIN
        return " ".join(map(self._render, best)), clear and all(self.common(self._base(x)) for x in best)

    def glued(self, w: str) -> Suggestion | None:
        """Words written as one, with or without a stray ZWNJ between them.
        A token the questionnaires repeat is no proof it is a word: a glue
        printed every year repeats too.  So only hazm's dictionary rules a
        token out; a repeated token without a ZWNJ is cut only around a word
        that glues a phrase (و, در, سایر, نظیر ...), which keeps compounds the
        questionnaires write joined (لباسشویی) whole."""
        rest = w[1:]
        if (
            w.startswith("و")
            and ZWNJ not in w
            and len(rest) >= 3
            and self.lex.count(rest) >= COMMON
            and self.lex.count(w) * 10 < self.lex.count(rest)
        ):
            # و glued to a common word, though hazm lists the glue too (وکیف, ولوله)
            return Suggestion(
                w,
                f"و {rest}",
                "glued",
                True,
                f"hazm: {rest} {_n(self.lex.count(rest))}; {w} {_n(self.lex.count(w))}",
            )
        if w == "و" or self.lex.has(w) or self.lex.has(self.lex.stem(w)):
            return None
        segs = w.split(ZWNJ)
        if len(segs) == 1 and self.uses[w] > RARE:
            cut, sure = self._segment(w, force=True)
            # cut only around a word that glues a phrase, or as the questionnaires write it elsewhere
            if not (any(x in _GLUE for x in cut.split(" ")) or (" " in cut and self.seen(cut))):
                return None
            return self._glued_suggestion(w, cut, sure)
        first, sure = self._segment(segs[0])
        out = [first]
        for prev, seg in itertools.pairwise(segs):
            # a ZWNJ before a suffix, after می / نمی, inside a word, or between two
            # pieces the questionnaires repeat as a token of their own (house style:
            # اجاره‌بهای, کم‌دوام) stays; else it is a space.  Judged per ZWNJ, not per
            # token: some years join a whole phrase with ZWNJs (حق‌بیمه‌های‌غیردرمانی‌...)
            keep = (
                self.uses[prev + ZWNJ + seg] > RARE
                or seg in _KEEP_AFTER
                or prev in ("می", "نمی")
                or self.lex.has(prev + ZWNJ + seg)
            )
            suffix = next((x for x in ("هایی", "های", "ها") if seg.startswith(x) and seg != x), None)
            if not keep and suffix:  # هزینه‌هایپرداختی: the suffix stays, the next word is glued to it
                cut, ok = self._segment(seg[len(suffix) :])
                out.append(f"{ZWNJ}{suffix} {cut}")
            else:
                cut, ok = self._segment(seg)
                out.append((ZWNJ if keep else " ") + cut)
            sure = sure and ok
        return self._glued_suggestion(w, "".join(out), sure)

    def _glued_suggestion(self, w: str, new: str, sure: bool) -> Suggestion | None:
        if new == w:
            return None
        words = [x for x in re.split(f"[ {ZWNJ}]", new) if x]
        seen = "; the questionnaires write it so elsewhere" if self.seen(new) else ""
        return Suggestion(
            w,
            new,
            "glued",
            sure,
            "hazm: " + " + ".join(f"{x} {_n(self.lex.count(x))}" for x in words) + f"; {w} not a word{seen}",
        )

    def typo(self, w: str) -> Suggestion | None:
        if len(w) < 4 or ZWNJ in w or self.known(w) or self.known(self.lex.stem(w)):
            return None
        near = [e for e in _edits1(w) if e[0] == w[0] and self.lex.count(e) >= TYPO_TARGET]
        if not near:
            return None
        best = max(near, key=self.lex.count)
        return Suggestion(w, best, "typo", False, f"hazm: {best} {_n(self.lex.count(best))}; {w} not a word")

    # -- two words --------------------------------------------------------------

    def spaced_plural(self, a: str, b: str) -> Suggestion | None:
        if b not in _SUFFIXES or not self.lex.has(a) or a.endswith(ZWNJ):
            return None
        joint = "" if a[-1] in _NON_JOINING else ZWNJ  # after ا د ذ ر ز ژ و no ZWNJ is needed
        return Suggestion(
            f"{a} {b}", f"{a}{joint}{b}", "plural", self.common(a), f"hazm: {a} {_n(self.lex.count(a))}"
        )

    def spaced_ye(self, a: str, b: str) -> Suggestion | None:
        """``پارچه ای`` -> ``پارچه‌ای``: a spaced ``ای`` after ``ه`` is always the suffix."""
        if b != "ای" or not a.endswith("ه") or len(a) < 2:
            return None
        return Suggestion(f"{a} {b}", f"{a}{ZWNJ}{b}", "he_ye", True, "ه + ای takes a ZWNJ")

    def prefix(self, a: str, b: str) -> Suggestion | None:
        """``می شود`` -> ``می‌شود``: the verb prefix می / نمی takes a ZWNJ."""
        if a not in ("می", "نمی") or len(b) < 2:
            return None
        return Suggestion(f"{a} {b}", f"{a}{ZWNJ}{b}", "prefix", True, f"{a} + verb takes a ZWNJ")

    def _joined(self, a: str, b: str) -> str:
        """``a`` and ``b`` as one word, the way hazm writes it more often."""
        if a[-1] in _NON_JOINING:
            return a + b  # after ا د ذ ر ز ژ و no ZWNJ is needed
        return max((a + ZWNJ + b, a + b), key=self.lex.count)

    def compound(self, a: str, b: str) -> Suggestion | None:
        """``ثبت نام`` -> ``ثبت‌نام``: two words whose joined form is a common
        word in hazm's dictionary, also with a suffix on the second
        (``اجاره بهای`` -> ``اجاره‌بهای``, as ``اجاره‌بها``).  Applied on its own,
        except a verb phrase (``خریداری شده``, ``قابل حمل``), which hazm's
        corpus also joins but Persian writes apart: that one applies only when
        the printed questionnaires write it joined somewhere."""
        if b in _SUFFIXES or b in ("ای", "ی") or a in _FUNCTION or b in _FUNCTION:
            return None  # no compound holds و, در, که ... (سر و صورت is not سرو)
        if not self.lex.has(a):
            return None
        # the compound must be common in hazm; its second piece need not be a
        # word of its own (بندی in طبقه‌بندی)
        joined, suffix = self._joined(a, b), ""
        if self.lex.count(joined) < COMMON:
            if not self.lex.has(b):
                return None  # a suffix is read only off a word (بهای, not ارهای: کاردار + های)
            for x in ("هایی", "های", "ها", "ای", "ی"):
                stem = b[: -len(x)]
                if b.endswith(x) and len(stem) >= 2 and self.lex.has(stem):
                    j = self._joined(a, stem)
                    if self.lex.count(j) >= COMMON:
                        joined, suffix = j, x
                        break
            else:
                return None
        joint = ZWNJ if suffix.startswith("ها") and joined[-1] not in _NON_JOINING else ""
        printed = any(self._printed(x) for x in (a + ZWNJ + b, a + b))
        phrase = b in _VERB_PHRASE or a in _PHRASE_HEAD
        return Suggestion(
            f"{a} {b}",
            joined + joint + suffix,
            "compound",
            printed or not phrase,
            f"hazm: {joined} {_n(self.lex.count(joined))}"
            + ("; the questionnaires print it joined" if printed else "")
            + ("; a verb phrase" if phrase else ""),
        )

    def _printed(self, word: str) -> bool:
        return word in self.printed and _pattern(word).search(self.printed) is not None

    def glued_plural(self, a: str, b: str, glue: Suggestion) -> Suggestion | None:
        """``سایرهزینه های`` -> ``سایر هزینه‌های``: the glued word is cut, and
        the plural suffix after it joins the last word."""
        if b not in _SUFFIXES:
            return None
        last = glue.replace.split(" ")[-1]
        joint = "" if last[-1] in _NON_JOINING else ZWNJ
        return Suggestion(f"{a} {b}", f"{glue.replace}{joint}{b}", "glued", glue.apply, glue.evidence)

    def broken(self, a: str, b: str) -> Suggestion | None:
        if b in _SUFFIXES or b.startswith("ال") or (self.known(a) and self.known(b)):
            return None
        joined = max((a + b, a + ZWNJ + b), key=self.lex.count)
        if self.lex.count(joined) < COMMON:
            return None
        return Suggestion(
            f"{a} {b}",
            joined,
            "broken",
            True,
            f"hazm: {joined} {_n(self.lex.count(joined))}; "
            + " + ".join(
                f"{x} {'not a word' if not self.known(x) else _n(self.lex.count(x))}" for x in (a, b)
            ),
        )


def _edits1(w: str) -> set[str]:
    cuts = [(w[:i], w[i:]) for i in range(len(w) + 1)]
    return (
        {a + b[1:] for a, b in cuts if b}
        | {a + c + b for a, b in cuts for c in _LETTERS}
        | {a + c + b[1:] for a, b in cuts if b for c in _LETTERS}
        | {a + b[1] + b[0] + b[2:] for a, b in cuts if len(b) > 1}
    ) - {w}


def suggest(
    labels: Iterable[tuple[int, str]],
    lex: Lexicon,
    printed: Iterable[str] | None = None,
    keys: Iterable[str] | None = None,
) -> list[Suggestion]:
    """Spelling suggestions for ``(year, label)`` pairs.  ``printed`` are the
    labels as printed (after the corrections and punctuation only), the
    evidence for how the questionnaires write a compound; ``labels`` by
    default.  ``keys`` name the item of each label across years (its kind and
    code); with them come the ``years`` suggestions."""
    labels = list(labels)
    tokens = [(y, s, _WORD.findall(s)) for y, s in labels]
    uses = Counter(w for _, _, ts in tokens for w in ts)
    text = "\n".join(s for _, s in labels)
    f = _Finder(lex, uses, text, text if printed is None else "\n".join(printed))
    found: dict[str, Suggestion] = {}

    def add(s: Suggestion | None) -> bool:
        if s is not None and s.find not in found:
            found[s.find] = s
        return s is not None

    for w in uses:
        if not _PERSIAN_ONLY.fullmatch(w):
            continue
        add(f.he_ye(w)) or add(f.plural(w)) or add(f.missing_zwnj(w)) or add(f.glued(w)) or add(f.typo(w))
    for _, _, ts in tokens:
        for a, b in itertools.pairwise(ts):
            if not (_PERSIAN_ONLY.fullmatch(a) and _PERSIAN_ONLY.fullmatch(b)):
                continue
            if a in found and found[a].kind == "glued":
                add(f.glued_plural(a, b, found[a]))
                continue
            (
                add(f.spaced_plural(a, b))
                or add(f.spaced_ye(a, b))
                or add(f.prefix(a, b))
                or add(f.broken(a, b))
                or add(f.compound(a, b))
            )
    # a compound followed by a spaced plural suffix (قطب نما ها): one suggestion,
    # or the compound would take نما and leave ها apart
    for _, _, ts in tokens:
        for a, b, c in zip(ts, ts[1:], ts[2:], strict=False):
            pair = found.get(f"{a} {b}")
            if c in _SUFFIXES and pair is not None and pair.kind == "compound":
                joint = "" if pair.replace[-1] in _NON_JOINING else ZWNJ
                add(
                    Suggestion(
                        f"{a} {b} {c}", pair.replace + joint + c, "compound", pair.apply, pair.evidence
                    )
                )
    # a piece of a broken pair is no word, so it was also read as a typo or a glue
    pieces = {p for s in found.values() if s.kind == "broken" for p in s.find.split(" ")}
    for p in pieces:
        if p in found and found[p].kind in ("typo", "glued"):
            del found[p]
    # where each suggestion occurs
    pattern = {s.find: _pattern(s.find) for s in found.values()}
    for y, label, _ in tokens:
        for find, pat in pattern.items():
            if find in label and pat.search(label):
                s = found[find]
                s.uses += len(pat.findall(label))
                s.labels.add(label)
                s.years.add(y)
    out = [s for s in found.values() if s.uses]
    if keys is not None:
        out += _across_years(labels, list(keys), out, lex)
    return sorted(out, key=lambda s: (KINDS.index(s.kind), -s.uses, s.find))


# --- across years --------------------------------------------------------------

_SUFFIX_FORMS = ("هایی", "های", "ها", "ترین", "تر", "ای", "ی", "ام", "ات", "اش")
_GAPS = re.compile(f"[ {ZWNJ}]")


def known(w: str, lex: Lexicon) -> bool:
    """A word of the dictionary, or a plural / suffixed form or ZWNJ compound of one."""
    if w in _SHORT or lex.has(w) or lex.has(lex.stem(w)):
        return True
    if ZWNJ in w:
        return all(p in _SUFFIX_FORMS or known(p, lex) for p in w.split(ZWNJ) if p)
    return any(w.endswith(s) and len(w) - len(s) >= 2 and lex.has(w[: -len(s)]) for s in _SUFFIX_FORMS)


def _all_known(span: str, lex: Lexicon) -> bool:
    return all(known(w, lex) for w in _WORD.findall(span) if _PERSIAN_ONLY.fullmatch(w))


def other_form(w: str, siblings: Iterable[tuple[int, str]], lex: Lexicon) -> tuple[str, int] | None:
    """How another label (``(year, text)``, nearest first) writes the letters of
    ``w``, when that is whole words the dictionary knows: ``سایرحق`` in 1383,
    ``سایر حق`` in 1386, though the rest of the two labels may differ."""
    bare = w.replace(ZWNJ, "")
    for year, text in siblings:
        letters, where = [], []
        for i, ch in enumerate(text):
            if ch not in f" {ZWNJ}":
                letters.append(ch)
                where.append(i)
        joined = "".join(letters)
        i = joined.find(bare)
        while i >= 0:
            a, b = where[i], where[i + len(bare) - 1] + 1
            whole = (a == 0 or not _WORD.match(text[a - 1])) and (b == len(text) or not _WORD.match(text[b]))
            span = text[a:b]
            if whole and span != w and _all_known(span, lex):
                return span, year
            i = joined.find(bare, i + 1)
    return None


def _across_years(
    labels: list[tuple[int, str]], keys: list[str], suggestions: list[Suggestion], lex: Lexicon
) -> list[Suggestion]:
    """``years``: where one item reads with the same letters but other spacing or
    ZWNJs in other years (the whole label, or a word the dictionary does not
    know that another year writes as known words: مستقردرکارخانه‌ها / مستقر در
    کارخانه‌ها), every way the labels write those letters is counted,
    on the labels as the other suggestions leave them.  The form written most
    wins, but a form with a word the dictionary does not know never beats one
    without.  Applied on its own only when every other form has such a word
    (سایرحق -> سایر حق); a choice between two spellings of known words
    (موتورسیکلت / موتور سیکلت) waits for review."""
    from .correct import LabelFix, fix_label  # correct imports this module

    fixes = [
        LabelFix(s.find, s.replace, "word", None, "")
        for s in sorted(suggestions, key=lambda s: -len(s.find))
        if s.apply
    ]
    final = [(y, fix_label(s, y, fixes)) for y, s in labels]
    text = "\n".join(s for _, s in final)
    # the spans whose spacing differs between years of one item
    by_key: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for key, (y, s) in zip(keys, final, strict=True):
        by_key[key].append((y, s))
    spans: set[str] = set()
    for items in by_key.values():
        for y, s in items:
            for w in _WORD.findall(s):
                if not _PERSIAN_ONLY.fullmatch(w) or known(w, lex):
                    continue
                siblings = sorted((t for t in items if t[0] != y), key=lambda t: abs(t[0] - y))
                if other_form(w, siblings, lex):
                    spans.add(w.replace(ZWNJ, ""))
        same: dict[str, set[str]] = defaultdict(set)
        for _, s in items:
            same[_GAPS.sub("", s)].add(s)
        for forms in same.values():
            for a, b in itertools.combinations(sorted(forms), 2):
                wa, wb = _WORD.findall(a), _WORD.findall(b)
                sm = difflib.SequenceMatcher(None, wa, wb, autojunk=False)
                for op, i1, i2, j1, j2 in sm.get_opcodes():
                    if op != "equal" and i2 > i1 and j2 > j1:
                        spans.add("".join(wa[i1:i2]).replace(ZWNJ, ""))
    edge = f"[ء-ٟٮ-ۓە۰-۹{ZWNJ}A-Za-z0-9]"
    taken = {s.find: s for s in suggestions}
    out = []
    for bare in sorted(spans):
        pat = re.compile(f"(?<!{edge})" + f"[ {ZWNJ}]?".join(map(re.escape, bare)) + f"(?!{edge})")
        count = Counter(pat.findall(text))
        if len(count) < 2:
            continue
        win = max(count, key=lambda s: (_all_known(s, lex), count[s], s))
        safe = _all_known(win, lex) and not any(_all_known(s, lex) for s in count if s != win)
        evidence = "the labels write " + "; ".join(f"{s} {n}" for s, n in count.most_common())
        for form in count:
            if form == win:
                continue
            if form in taken:
                # another kind suggests the same and held it back (a glue it could
                # not cut for sure): the other years settle it
                other = taken[form]
                if safe and not other.apply and other.replace == win:
                    other.apply = True
                    other.evidence += f"; {evidence}"
                continue
            s = Suggestion(form, win, "years", safe, evidence)
            pf = _pattern(form)
            for y, label in final:
                if form in label and pf.search(label):
                    s.uses += len(pf.findall(label))
                    s.labels.add(label)
                    s.years.add(y)
            if s.uses:
                out.append(s)
    return out


def _pattern(find: str) -> re.Pattern:
    edge = f"[ء-ٟٮ-ۓە۰-۹{ZWNJ}A-Za-z0-9]"
    return re.compile(f"(?<!{edge}){re.escape(find)}(?!{edge})")


# --- files ---------------------------------------------------------------------

COLUMNS = ["find", "replace", "kind", "apply", "uses", "labels", "years", "evidence", "example"]


def write_suggestions(suggestions: list[Suggestion], path: Path = SUGGESTIONS) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(COLUMNS)
        for s in suggestions:
            w.writerow(
                [
                    s.find,
                    s.replace,
                    s.kind,
                    "yes" if s.apply else "no",
                    s.uses,
                    len(s.labels),
                    years_text(s.years),
                    s.evidence,
                    min(s.labels, key=lambda x: (len(x), x)),  # shortest, ties broken alike every run
                ]
            )


@dataclass
class Decision:
    find: str
    decision: str
    replace: str
    reason: str


def load_suggestions(path: Path = SUGGESTIONS) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def load_decisions(path: Path = DECISIONS) -> list[Decision]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8-sig") as f:
        out = [Decision(r["find"], r["decision"], r["replace"], r["reason"]) for r in csv.DictReader(f)]
    for d in out:
        if d.decision not in DECISION_KINDS:
            raise ValueError(f"{path}: decision must be one of {', '.join(DECISION_KINDS)} ({d.find})")
        if d.decision == "change" and not d.replace:
            raise ValueError(f"{path}: change needs a replace ({d.find})")
        if not d.reason.strip():
            raise ValueError(f"{path}: every decision needs a reason ({d.find})")
    return out


def accepted(
    suggestions: list[dict[str, str]], decisions: list[Decision]
) -> tuple[list[tuple[str, str]], list[Decision]]:
    """The (find, replace) pairs the build applies, longest first, the
    ``years`` ones last (they are found on the labels the others leave), and
    the decisions that match no suggestion (stale)."""
    by_find = {d.find: d for d in decisions}
    pairs = []
    for s in suggestions:
        d = by_find.get(s["find"])
        last = s.get("kind") == "years"
        if d is None:
            if s["apply"] == "yes":
                pairs.append((last, s["find"], s["replace"]))
        elif d.decision == "confirm":
            pairs.append((last, s["find"], s["replace"]))
        elif d.decision == "change":
            pairs.append((last, s["find"], d.replace))
    listed = {s["find"] for s in suggestions}
    stale = [d for d in decisions if d.find not in listed]
    return [(f, r) for _, f, r in sorted(pairs, key=lambda p: (p[0], -len(p[1])))], stale


def main(argv: list[str] | None = None) -> None:
    from . import correct

    ap = argparse.ArgumentParser(
        prog="python -m hiesir_codebook.correction.spelling", description=__doc__.split("\n")[0]
    )
    ap.add_argument("--extracted", type=Path, default=EXTRACTED)
    ap.add_argument("--out", type=Path, default=SUGGESTIONS)
    args = ap.parse_args(argv)
    rows = [
        (y, r["description"], f"{r['kind']} {r['expenditure_code'] or r['code'] or r['section']}")
        for y, year_rows in correct.before_suggestions(args.extracted)
        for r in year_rows
        if r["description"]
    ]
    printed = [
        r["description"] for _, rows in correct.before_suggestions(args.extracted, labels=None) for r in rows
    ]
    suggestions = suggest(((y, s) for y, s, _ in rows), hazm_lexicon(), printed, keys=(k for _, _, k in rows))
    write_suggestions(suggestions, args.out)
    kinds = defaultdict(lambda: [0, 0])
    for s in suggestions:
        kinds[s.kind][0 if s.apply else 1] += 1
    print(
        f"{len(suggestions)} spelling suggestions -> {args.out.as_posix()}: "
        + ", ".join(f"{k} {a + b} ({a} applied on their own)" for k, (a, b) in kinds.items())
    )


if __name__ == "__main__":
    main()
