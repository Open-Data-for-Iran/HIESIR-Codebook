"""The fixes the build applies to descriptions, and the files that hold them.

Every file of fixes is a table of ``find`` -> ``replace``, read with polars
into a :class:`FixList`, which applies them to a text in order:

================================================ =========== ===============
file                                             written by  applied in step
================================================ =========== ===============
``output/2_corrected/autocorrect/canonical.csv`` autocorrect ``canonical``
                                                             (whole labels)
``curated/2_corrected/spelling.csv``, ``text``   hand        ``letters``
rows
``output/2_corrected/autocorrect/words.csv``     autocorrect ``words``
``curated/2_corrected/spelling.csv``, ``word``   hand        ``spelling``
rows
================================================ =========== ===============

The build itself needs none of hazm's data: it applies these files (the
``autocorrect`` command writes the two of ``output/``, see :mod:`.words`).

Columns of ``spelling.csv``:

========== ===================================================================
find       the wrong form (may be several words), as it reads after the
           house style; ZWNJs are ignored (شدهباشد finds شده‌باشد)
replace    the right form
match      ``word``: only as whole words (not inside a longer word);
           ``text``: anywhere in the label (letters inside words: تزئین ->
           تزیین), applied with the house style
years      empty for all years, else years and ranges: ``1386``,
           ``1383-1385``, ``1383-1385 1390``
reason     why
========== ===================================================================

A ``word`` row is a hand decision: where it matches, the automatic word
fixes leave that stretch of the label to it (the ``guard`` of
:meth:`FixList.apply`), so a hand decision always wins.  Only a fix that
changes no word (``UNGUARDED``: a suffix joined to its word) may cross it.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

import polars as pl

from .. import CORRECTED, CURATED_CORRECTED, csv_io
from ..utils import ZWNJ, parse_years
from .text import bare, whole

SPELLING = CURATED_CORRECTED / "spelling.csv"
AUTOCORRECT_DIR = CORRECTED / "autocorrect"
CANONICAL = AUTOCORRECT_DIR / "canonical.csv"
WORDS = AUTOCORRECT_DIR / "words.csv"

# kinds of fix that change no word, and so may cross a stretch a hand row decides
UNGUARDED = frozenset({"spaced_suffix"})
ROUNDS = 3  # the most times FixList.settle applies a list


@dataclass(frozen=True)
class Fix:
    find: str
    replace: str
    match: str = "word"  # "word" (whole words only) | "text" (anywhere)
    years: frozenset[int] | None = None  # None: every year
    kind: str = ""  # the reason, rule or kind of the row

    @cached_property
    def bare(self) -> str:
        return bare(self.find)

    @cached_property
    def pattern(self) -> re.Pattern:
        # blind to ZWNJs: a fix for شدهباشد also finds شده‌باشد, since where the
        # PDF shows a ZWNJ the extractor keeps it and a fix should still apply
        p = f"{ZWNJ}?".join(re.escape(ch) for ch in self.bare)
        return re.compile(whole(p) if self.match == "word" else p)

    @property
    def guarded(self) -> bool:
        return self.kind not in UNGUARDED

    def applies(self, year: int) -> bool:
        return self.years is None or year in self.years


class FixList:
    """Fixes applied to a text in order, each to the text the ones before leave."""

    def __init__(self, fixes=()):
        self.fixes: tuple[Fix, ...] = tuple(fixes)

    @classmethod
    def from_frame(cls, df: pl.DataFrame) -> FixList:
        """From a table of ``find``, ``replace`` and, when it has them,
        ``match``, ``years`` (as written: ``1383-1385 1390``) and ``kind``."""
        cols = set(df.columns)
        return cls(
            Fix(
                r["find"],
                r["replace"],
                r.get("match") or "word",
                parse_years(r["years"]) if "years" in cols else None,
                r.get("kind", ""),
            )
            for r in df.iter_rows(named=True)
        )

    def __iter__(self) -> Iterator[Fix]:
        return iter(self.fixes)

    def __len__(self) -> int:
        return len(self.fixes)

    def where(self, keep: Callable[[Fix], bool]) -> FixList:
        return FixList(fx for fx in self.fixes if keep(fx))

    def apply(
        self, text: str, year: int = 0, hits: list[Fix] | None = None, guard: FixList | None = None
    ) -> str:
        """``text`` with every fix for ``year`` applied, each that changed it
        added to ``hits`` (a fix blind to ZWNJs may match a text already
        right).  With a ``guard``, a fix is applied only outside the stretches
        the guard matches in the text as it then reads (unless it changes no
        word)."""
        flat = bare(text)
        for fx in self.fixes:
            # the substring test is a cheap filter before the regex
            if fx.bare not in flat or not fx.applies(year):
                continue
            if guard is not None and fx.guarded:
                new = "".join(fx.pattern.sub(fx.replace, t) if free else t for t, free in guard.parts(text))
            else:
                new = fx.pattern.sub(fx.replace, text)
            if new != text:
                if hits is not None:
                    hits.append(fx)
                text, flat = new, bare(new)
        return text

    def settle(
        self, text: str, year: int = 0, hits: list[Fix] | None = None, guard: FixList | None = None
    ) -> str:
        """:meth:`apply` again until ``text`` stops changing (at most ROUNDS
        times): a word one fix makes meets every fix of the list, wherever it
        stands (``بجزروانی`` -> ``بجز روانی`` -> ``به جز روانی``)."""
        for _ in range(ROUNDS):
            new = self.apply(text, year, hits, guard)
            if new == text:
                break
            text = new
        return text

    def parts(self, label: str) -> list[tuple[str, bool]]:
        """``label`` cut into ``(text, free)`` pieces: a stretch any of these
        fixes matches (whatever its years) is not free."""
        flat = bare(label)
        spans = sorted(m.span() for fx in self.fixes if fx.bare in flat for m in fx.pattern.finditer(label))
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


# --- the files ---------------------------------------------------------------------


def _read(path: Path, columns: list[str]) -> pl.DataFrame:
    """``path`` as a table, or an empty one with ``columns`` when it is not there."""
    if not path.exists():
        return pl.DataFrame(schema=dict.fromkeys(columns, pl.String))
    return csv_io.read_frame(path)


def read_spelling(path: Path = SPELLING) -> FixList:
    """``spelling.csv``, in file order; every row needs a find and a reason,
    and ``match`` is ``word`` (the default) or ``text``."""
    df = _read(path, ["find", "replace", "match", "years", "reason"]).with_columns(
        pl.when(pl.col("match") == "").then(pl.lit("word")).otherwise("match").alias("match"),
        pl.col("reason").alias("kind"),
    )
    bad = df.filter(~pl.col("match").is_in(["word", "text"]))
    if bad.height:
        raise ValueError(
            f"{path}: match must be 'word' or 'text', got {bad['match'][0]!r} ({bad['find'][0]})"
        )
    empty = df.filter((pl.col("find") == "") | (pl.col("reason").str.strip_chars() == ""))
    if empty.height:
        raise ValueError(f"{path}: every row needs find and reason ({empty['find'][0]})")
    return FixList.from_frame(df)


def read_words(path: Path = WORDS) -> FixList:
    """``words.csv``: whole-word fixes, in file order (the order they are found)."""
    return FixList.from_frame(_read(path, ["find", "replace", "kind"]).select("find", "replace", "kind"))


def read_variants(path: Path = CANONICAL) -> dict[str, str]:
    """``canonical.csv``: a label -> the wording of its group."""
    df = _read(path, ["find", "replace"])
    return dict(zip(df["find"], df["replace"], strict=True))


@dataclass(frozen=True)
class Fixes:
    """Every fix the build applies, by the step that applies it."""

    variants: dict[str, str] = field(default_factory=dict)  # canonical.csv
    letters: FixList = field(default_factory=FixList)  # spelling.csv, text rows
    words: FixList = field(default_factory=FixList)  # words.csv: the automatic word fixes
    spelling: FixList = field(default_factory=FixList)  # spelling.csv, word rows: the hand decisions

    @classmethod
    def load(cls, spelling: Path = SPELLING, words: Path = WORDS, canonical: Path = CANONICAL) -> Fixes:
        hand = read_spelling(spelling)
        return cls(
            variants=read_variants(canonical),
            letters=hand.where(lambda fx: fx.match == "text"),
            words=read_words(words),
            spelling=hand.where(lambda fx: fx.match == "word"),
        )
