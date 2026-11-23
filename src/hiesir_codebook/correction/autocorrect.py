"""Correction step 4: automatic fixes from hazm's word list.

This step reads every label once, as the structural corrections
(:mod:`.corrections`, step 1), the canonical wording (:mod:`.canonical`, step
2) and the house style (:mod:`.rules`, step 3) leave it: a label printed in
several ways reaches it already fixed, so its work is in the labels printed
one way.  It tries each rule below on each word and saves what it finds to
``output/2_corrected/autocorrect/hazm.csv``.  The build applies that file, one
whole word at a time, before ``spelling.csv`` (:mod:`.spelling`, step 5), so it
runs without hazm's data.  Regenerate it after changing steps 1-3 or the rules,
with hazm's data downloaded (``uv run hiesir-codebook hazm download``):

    uv run hiesir-codebook autocorrect

hazm's list mixes three kinds of entries: about 27,000 words met in its
corpus (with their frequency), 8,500 with a part of speech but frequency 0,
and 158,000 bare headwords with neither: mostly rare or archaic words
(``سنگی``, ``والک`` among them), but also glued junk (``ویخ``, ``وکم``).  A word
is *known* when hazm vouches for it (a frequency or a part of speech), or is
such a word with a suffix hazm does not list it with (``SUFFIXES``: the plural
ها / های, ی, ای, ان, ات, تر ...: ``پلاستیکی`` = ``پلاستیک`` + ی), and *listed*
when it is there at all; both ignore ZWNJs and the Arabic forms of ی
and ک.  A word is also known when ``curated/2_corrected/words.csv`` lists it: correct
words hazm lacks (``word``, ``reason``), such as the plant ``والک``, which the
rule below would otherwise cut into و + الک.

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
             ``نمک سود`` -> ``نمک‌سود``); never with a
             function word, a verb phrase (``پرداخت شده``) or a head the house
             style writes apart (``قابل حمل``)
spaced_suffix  a known word and a suffix written apart (ها, های, هایی, ترین, and
             ای after ه), on the labels as ``glued_vav`` leaves them: joined with
             a ZWNJ, or with nothing after ا د ذ ر ز ژ و, on the labels as the
             rules above leave them (``نمایش های`` ->
             ``نمایش‌های``, ``پارچه ای`` -> ``پارچه‌ای``, ``پودر های`` -> ``پودرهای``);
             left alone when the two together are a word of their own (``تن ها``
             / ``تنها``)
============ ====================================================================

Where a word row of ``spelling.csv`` matches a label, the rules leave that
stretch to it, both when they find their fixes and when the build applies them
(:func:`free_parts`), so a hand decision always wins; ``spaced_suffix``, which
changes no word, may cross it.

Columns of ``hazm.csv``: ``find`` (the word, or the word and its suffix, as
the labels write it),
``replace``, ``rule``, ``uses`` (how many times the labels write it),
``years``, ``evidence`` (the hazm frequencies behind the fix) and an
``example`` label.
"""

from __future__ import annotations

import functools
import itertools
import math
import re
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

import polars as pl

from .. import CORRECTED, CURATED_CORRECTED, csv_io
from ..utils import ZWNJ
from .spelling import LabelFix

AUTOCORRECT_DIR = CORRECTED / "autocorrect"
HAZM_FIXES = AUTOCORRECT_DIR / "hazm.csv"
WORDS = CURATED_CORRECTED / "words.csv"
COLUMNS = ["find", "replace", "rule", "uses", "years", "evidence", "example"]
RULES = ("glued_vav", "glued_words", "joined_plural", "compound", "spaced_suffix")

# what a known word may carry and still count as known, longest first: the
# plural, ی (adjective, indefinite, ezafe), ای / یی after a vowel, the plurals
# ان and ات, and the comparative
SUFFIXES = ("هایی", "های", "ها", "ترین", "تر", "ای", "یی", "ان", "ات", "ی")

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
COMMON = 10_000  # a common word in hazm's corpus; curated words and verb forms count as one
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
_EDGE = f"[ء-ٟٮ-ۓە۰-۹{ZWNJ}A-Za-z0-9]"

# a Persian word: Arabic-script letters, with the ZWNJs inside it
_LETTERS = f"ء-يٹ-ۓ{ZWNJ}"
_WORD = re.compile(f"[{_LETTERS}]+")
# a word followed by one of SPACED, spaced
_SPACED_PAIR = re.compile(f"(?<![{_LETTERS}])([{_LETTERS}]+) ({'|'.join(SPACED)})(?![{_LETTERS}])")


_FOLD = str.maketrans({"ي": "ی", "ك": "ک", "ئ": "ی", "أ": "ا", "إ": "ا", "ؤ": "و", "ء": None, ZWNJ: None})
# the letter forms alone, ZWNJs kept
_LETTERS = str.maketrans({"ي": "ی", "ك": "ک", "ئ": "ی", "أ": "ا", "إ": "ا", "ؤ": "و", "ء": None})


def _key(w: str) -> str:
    """A word for lookup: no ZWNJ, one way to write ی and ک, and no hamza
    (تامین finds تأمین, موسسات مؤسسات); آ stays, as آب is not اب."""
    return w.translate(_FOLD)


_FOLD_PAIRS = {"ي": "ی", "ك": "ک", "ئ": "ی", "أ": "ا", "إ": "ا", "ؤ": "و", "ء": "", ZWNJ: ""}


def _key_expr(column: str) -> pl.Expr:
    """:func:`_key` as a polars expression."""
    return pl.col(column).str.replace_many(list(_FOLD_PAIRS), list(_FOLD_PAIRS.values()))


@dataclass
class Lexicon:
    """The words hazm lists (tests pass a small one).  ``freq`` holds every
    listed word with its frequency; ``words`` the ones hazm vouches for: met
    in its corpus or given a part of speech."""

    freq: dict[str, int]
    words: set[str]
    stems: frozenset[str] = frozenset()  # present stems of verbs (کش, دار, بند): the head of a compound
    _by_key: dict[str, int] = field(default_factory=dict, repr=False)
    _word_keys: set[str] = field(default_factory=set, repr=False)

    def __post_init__(self) -> None:
        if self._by_key or not self.freq:  # built by from_frame, or empty
            return
        for w, n in self.freq.items():
            k = _key(w)
            self._by_key[k] = max(n, self._by_key.get(k, 0))
        self._word_keys = {_key(w) for w in self.words}

    @classmethod
    def from_frame(cls, df: pl.DataFrame, stems: frozenset[str] = frozenset()) -> Lexicon:
        """A lexicon from a table of ``word``, ``freq`` and ``vouched``, its
        lookup keys (no ZWNJ, no hamza, one ی and one ک) worked out in polars."""
        df = df.group_by("word").agg(pl.col("freq").max(), pl.col("vouched").any())
        df = df.with_columns(_key_expr("word").alias("key"))
        by_key = df.group_by("key").agg(pl.col("freq").max())
        return cls(
            dict(zip(df["word"], df["freq"], strict=True)),
            set(df.filter("vouched")["word"]),
            stems,
            dict(zip(by_key["key"], by_key["freq"], strict=True)),
            set(df.filter("vouched")["key"]),
        )

    def count(self, w: str) -> int:
        return self.freq.get(w) or self._by_key.get(_key(w), 0)

    def listed(self, w: str) -> bool:
        """In hazm's list at all, even a bare headword."""
        return w in self.freq or _key(w) in self._by_key

    def known(self, w: str) -> bool:
        """A word hazm vouches for."""
        return w in self.words or _key(w) in self._word_keys

    def stem(self, w: str) -> tuple[str, str] | None:
        """``(stem, suffix)`` when ``w`` is a known word with a suffix hazm
        does not list it with: ``پلاستیکی`` -> ``("پلاستیک", "ی")``,
        ``کالاهای`` -> ``("کالا", "های")``, ``پارچه‌ای`` -> ``("پارچه", "ای")``."""
        bare = _key(w)
        for suffix in SUFFIXES:
            stem = bare[: -len(suffix)]
            if bare.endswith(suffix) and len(stem) >= 2 and (self.known(stem) or self._stem_once(stem)):
                return stem, suffix
        return None

    def _stem_once(self, w: str) -> bool:
        """A known word with one suffix: lets suffixes stack (بیماریهای =
        بیمار + ی + های), two deep at most."""
        return any(w.endswith(x) and len(w) - len(x) >= 2 and self.known(w[: -len(x)]) for x in SUFFIXES)

    def compound_head(self, w: str) -> bool:
        """Is ``w`` a verb's present stem, or one with ی or نده (کش, کشی,
        داری, بندها, کننده), which makes a compound with the word before it
        (اطوکشی, عزاداری, ترکبند, ضدعفونی‌کننده)?"""
        w = _key(w)
        for suffix in ("هایی", "های", "ها", ""):
            if suffix and not w.endswith(suffix):
                continue
            core = w[: len(w) - len(suffix)]
            for tail in ("", "ی", "نده", "ندگی"):
                if (tail == "" or core.endswith(tail)) and core[: len(core) - len(tail)] in self.stems:
                    return True
        return False

    def level(self, w: str) -> int:
        """How sure hazm is that ``w`` is a word: 3 known, 2 a known word with a
        suffix, 1 only listed, 0 not there."""
        return 3 if self.known(w) else 2 if self.stem(w) else 1 if self.listed(w) else 0


def load_words(path: Path = WORDS) -> list[str]:
    """The correct words hazm lacks; every row needs a reason."""
    if not path.exists():
        return []
    rows = csv_io.read(path)
    for r in rows:
        if not r["word"].strip() or not r["reason"].strip():
            raise ValueError(f"{path}: every row needs a word and a reason ({r['word']})")
    return [r["word"].strip() for r in rows]


def hazm_lexicon(words: Path = WORDS) -> Lexicon:
    """hazm's word list (read with polars), with the forms of its verbs and
    the words of ``words`` as known."""
    from ..hazm_data import verbs_list, words_frame

    hazm = words_frame().select(
        "word", "freq", ((pl.col("freq") > 0) | (pl.col("pos") != "0")).alias("vouched")
    )
    listed = set(hazm["word"])
    # a verb form that is و + a word hazm lists is a glued و far more often
    # than a rare verb (وسیم of وشت#وس is و + سیم); ورزید stays
    forms = sorted(w for w in verb_forms() if not (w.startswith("و") and w[1:] in listed))
    curated = [x for w in load_words(words) for x in {w, *w.split(" ")}]  # گالینا بلانکا and its words
    extra = pl.DataFrame(
        {"word": forms + curated, "freq": [COMMON] * (len(forms) + len(curated)), "vouched": True},
        schema={"word": pl.String, "freq": pl.Int64, "vouched": pl.Boolean},
    )
    listed.update(forms)
    stems = frozenset(
        pres
        for line in verbs_list()
        for pres in [line.partition("#")[2].strip()]
        if len(pres) >= 2 and " " not in pres and not (pres.startswith("و") and pres[1:] in listed)
    )
    return Lexicon.from_frame(pl.concat([hazm, extra]), stems)


_PAST_ENDINGS = ("م", "ی", "", "یم", "ید", "ند")
_PRESENT_ENDINGS = ("م", "ی", "د", "یم", "ید", "ند")
_PERFECT = ("است",)  # the personal endings (سوخته‌ای) would read as plurals (سوختهای)


def verb_forms() -> set[str]:
    """The forms of hazm's verbs (``verbs.dat``: past#present stems), which its
    word list leaves out: past (کرد, کردند), participle (شده, نشده) and
    perfect (شده‌است), present with می / نمی (می‌شود, نمی‌شود), subjunctive
    (شود, بشود), the agent noun (کننده), each also negated; and the verb to be."""
    from ..hazm_data import verbs_list

    out = {"است", "نیست", "هست", "هستند", "نیستند", "بود", "بودند", "باشد", "نباشد", "باشند", "نباشند"}
    for line in verbs_list():
        past, _, present = line.partition("#")
        for neg in ("", "ن"):
            if past:
                out.update(neg + past + e for e in _PAST_ENDINGS)
                out.add(neg + past + "ه")
                out.update(f"{neg}{past}ه{ZWNJ}{e}" for e in _PERFECT)
            if present:
                out.update(neg + present + e for e in _PRESENT_ENDINGS)
                out.update(f"{'نمی' if neg else 'می'}{ZWNJ}{present}{e}" for e in _PRESENT_ENDINGS)
                out.add(neg + present + "نده")
                if not neg:
                    out.update("ب" + present + e for e in _PRESENT_ENDINGS)
    return out


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
    always print them apart.  Never with a function word (و, در, یک ...), a
    verb phrase (پرداخت شده) or a head the house style writes apart (قابل حمل)."""
    if a in _FUNCTION or b in _FUNCTION or b in _VERB_PHRASE or a in _APART_HEADS:
        return None
    joined = f"{a}{ZWNJ}{b}"
    if joined not in lex.words:
        return None
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


@dataclass(eq=False)
class Labels:
    """What the rules may know of the labels: how often each word is written,
    and all the text (to see whether a phrase is written somewhere)."""

    uses: Counter
    text: str

    @classmethod
    def of(cls, labels: Iterable[str]) -> Labels:
        labels = list(labels)
        return cls(Counter(w for t in labels for w in _WORD.findall(t)), "\n".join(labels))

    def seen(self, phrase: str) -> bool:
        """Do the labels write ``phrase`` somewhere, as whole words, whatever the
        forms of ی, ک and hamza (سایر موسسات is سایر مؤسسات)?"""
        text, phrase = self._folded, phrase.translate(_LETTERS)
        return phrase in text and re.search(f"(?<!{_EDGE}){re.escape(phrase)}(?!{_EDGE})", text) is not None

    @functools.cached_property
    def _folded(self) -> str:
        return self.text.translate(_LETTERS)

    @functools.cached_property
    def _folded_uses(self) -> Counter:
        out: Counter = Counter()
        for w, n in self.uses.items():
            out[w.translate(_LETTERS)] += n
        return out

    def count(self, w: str) -> int:
        """How often the labels write ``w``, whatever the forms of ی, ک and
        hamza (موسسات counts مؤسسات)."""
        return self._folded_uses[w.translate(_LETTERS)]


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
    pieces = _WORD.split(text)
    words = _WORD.findall(text)
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


# --- reading the labels once, writing the fixes ---------------------------------


@dataclass
class Found:
    fix: Fix
    uses: int = 0
    years: set[int] = field(default_factory=set)
    example: str = ""


def find_fixes(
    labels: Iterable[tuple[int, str]],
    lex: Lexicon,
    protected: Iterable[str] = (),
    context: Labels | None = None,
) -> list[Found]:
    """Every fix the rules find in the ``(year, label)`` pairs, in passes,
    each on the label as the passes before leave it: the rules on one word
    (``WORD_PASSES``: ``وسالنهای`` -> ``و سالنهای`` -> ``و سالن‌های``), then the
    rule on a word and the suffix after it."""
    labels = list(labels)
    cutter = Cutter(lex, context or Labels.of(t for _, t in labels))
    # where a spelling.csv row matches a label, its words and pairs there are
    # left to it (a hand decision wins); elsewhere the rules may fix them
    rows = [LabelFix(p, p, "word", None, "") for p in protected]
    extra = {"glued_words": (cutter,), "compound": (cutter.labels,)}
    found: dict[tuple[str, str], Found | None] = {}

    def apply(rule: Callable[..., Fix | None], key: str, args: tuple, uses: tuple[int, set, str]) -> str:
        """Count ``key`` for ``rule`` (asking the rule once per key) and return
        what the label reads after it; ``uses``: how many rows print the label,
        in which years, and the label."""
        if (rule.__name__, key) not in found:
            fix = rule(*args, lex, *extra.get(rule.__name__, ()))
            found[rule.__name__, key] = Found(fix) if fix else None
        hit = found[rule.__name__, key]
        if hit is None:
            return key
        n, years, label = uses
        hit.uses += n
        hit.years |= years
        hit.example = hit.example or label
        return hit.fix.replace

    # each distinct label once, with how many rows print it and in which years
    # (27,000 rows hold about 3,500 labels), in the order they are first met
    df = pl.DataFrame({"year": [y for y, _ in labels], "label": [t for _, t in labels]}, orient="col")
    distinct = (
        df.group_by("label", maintain_order=True).agg(
            pl.len().alias("n"), pl.col("year").unique().alias("years")
        )
        if labels
        else df
    )
    for label, n, years in distinct.iter_rows() if labels else ():
        use = (n, set(years), label)
        parts = []
        for text, free in free_parts(label, rows):
            if free:
                for rule in WORD_PASSES:
                    pieces = _WORD.split(text)  # text between words, word, text, ...
                    words = _WORD.findall(text)
                    out = [pieces[0]]
                    for w, after in zip(words, pieces[1:], strict=True):
                        out += [apply(rule, w, (w,), use), after]
                    text = "".join(out)
                text = _join_pairs(text, lambda a, b, u=use: apply(compound, f"{a} {b}", (a, b), u))
            parts.append(text)
        # a suffix joined to its word changes no word, so it may cross a stretch
        # a spelling.csv row matches (سی دی + های)
        for m in _SPACED_PAIR.finditer("".join(parts)):
            apply(spaced_suffix, m.group(0), (m.group(1), m.group(2)), use)
    return sorted(
        (f for f in found.values() if f), key=lambda f: (RULES.index(f.fix.rule), -f.uses, f.fix.find)
    )


def years_text(years: Iterable[int]) -> str:
    """{1383, 1384, 1385, 1390} -> "1383-1385 1390"."""
    ys, out = sorted(years), []
    for y in ys:
        if out and y == out[-1][1] + 1:
            out[-1][1] = y
        else:
            out.append([y, y])
    return " ".join(str(a) if a == b else f"{a}-{b}" for a, b in out)


def write_fixes(found: list[Found], path: Path = HAZM_FIXES) -> None:
    csv_io.write(
        path,
        COLUMNS,
        (
            {
                "find": f.fix.find,
                "replace": f.fix.replace,
                "rule": f.fix.rule,
                "uses": f.uses,
                "years": years_text(f.years),
                "evidence": f.fix.evidence,
                "example": f.example,
            }
            for f in found
        ),
    )


def load_fixes(path: Path = HAZM_FIXES) -> list[LabelFix]:
    """The fixes of ``hazm.csv`` as whole-word label fixes (none when the
    file is not there)."""
    if not path.exists():
        return []
    return [LabelFix(r["find"], r["replace"], "word", None, r["rule"]) for r in csv_io.read(path)]


def free_parts(label: str, rows: Iterable[LabelFix]) -> list[tuple[str, bool]]:
    """``label`` cut into ``(text, free)`` pieces: the stretches a spelling.csv
    row matches are not free, and the automatic fixes leave them to that row,
    both when they are found and when the build applies them."""
    bare = label.replace(ZWNJ, "")
    spans = sorted(
        m.span() for fx in rows if fx.find.replace(ZWNJ, "") in bare for m in fx.pattern.finditer(label)
    )
    out: list[tuple[str, bool]] = []
    at = 0
    for a, b in spans:
        if b <= at:
            continue
        a = max(a, at)
        if a > at:
            out.append((label[at:a], True))
        out.append((label[a:b], False))
        at = b
    if at < len(label) or not out:
        out.append((label[at:], True))
    return out


def fix_free(
    label: str, year: int, fixes: list[LabelFix], rows: list[LabelFix], hits: dict | None = None
) -> str:
    """``label`` with ``fixes`` applied outside the stretches ``rows`` match,
    but the ``spaced_suffix`` fixes everywhere (they change no word)."""
    from .spelling import fix_label

    words = [fx for fx in fixes if fx.reason != "spaced_suffix"]
    suffixes = [fx for fx in fixes if fx.reason == "spaced_suffix"]
    text = "".join(fix_label(t, year, words, hits) if free else t for t, free in free_parts(label, rows))
    return fix_label(text, year, suffixes, hits)


def protected_finds(path: Path | None = None) -> list[str]:
    """The ``find`` of every spelling.csv row: the words and pairs the automatic
    fixes leave to it, so a hand decision always wins."""
    from .spelling import LABELS, load_label_fixes

    # a text-match row fixes letters inside words (تزئین -> تزیین) and decides no word
    return [fx.find for fx in load_label_fixes(path or LABELS) if fx.match == "word"]


def main(*, out: Path = HAZM_FIXES) -> None:
    """Correction step 4: automatic fixes from hazm's word list.

    Needs hazm's data (``hiesir-codebook hazm download``).

    Parameters
    ----------
    out
        Where the fixes go.
    """
    from .correct import labels_for_autocorrect

    found = find_fixes(labels_for_autocorrect(), hazm_lexicon(), protected_finds())
    write_fixes(found, out)
    by_rule = Counter(f.fix.rule for f in found)
    uses = defaultdict(int)
    for f in found:
        uses[f.fix.rule] += f.uses
    print(
        f"{len(found)} automatic fixes -> {out.as_posix()}: "
        + ", ".join(f"{r} {by_rule[r]} words ({uses[r]} uses)" for r in RULES)
    )
