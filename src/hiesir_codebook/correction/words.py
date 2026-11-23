"""The automatic fixes: what the ``autocorrect`` command writes, with hazm's
word list, to ``output/2_corrected/autocorrect/``.

    uv run hiesir-codebook autocorrect

It writes two files, which the build applies without hazm's data:

- ``canonical.csv``: one wording for each group of labels printed in several
  ways (:mod:`.canonical`), applied to whole labels in the ``canonical`` step;
- ``words.csv``: every word fix found automatically, applied in the ``words``
  step, after ``letters`` and before the hand decisions of ``spelling.csv``.

``words.csv`` comes from a chain of finders.  Each reads the labels as the
steps up to ``letters`` and the finders before it leave them, and proposes
fixes (``find``, ``replace``, ``kind``, ``evidence``):

============ =========================================================================
finder       kinds
============ =========================================================================
learned      ``learned``: what the losers of the canonical groups write otherwise
             than their winner (:func:`.canonical.learned_fixes`)
folded       ``folded``: one form of each word written with other forms of ی, ک or
             hamza (:func:`.canonical.folded_fixes`)
variant      ``variant``: one form of a word the same item prints two ways in
             consecutive years, a letter apart (:mod:`.variants`)
hazm         hazm's rules, in the order they run: ``glued_vav``, ``glued_words``,
             ``joined_plural``, ``compound``, ``spaced_suffix``
             (:mod:`.hazm_rules`)
============ =========================================================================

A find another finder already proposed with another replacement is left to
the first.  The chain runs again, on the labels as the first pass leaves them,
until a pass adds nothing that changes a label (at most PASSES): a word one
finder makes may need another that ran before it (``بجزروانی`` -> ``بجز
روانی`` -> ``به جز روانی``).  How often the labels write a word, which
``glued_words`` weighs, is read from the labels both as printed and as the
finders leave them.  The build applies the file until the label stops changing
(:meth:`.fixes.FixList.settle`), and so do the finders and the bookkeeping.
The file lists the fixes in the order the build applies them: by pass, finder
and kind, then the longest find first.  Then
the bookkeeping applies the whole file to the labels, as the build does, and
records what each fix changes: ``uses`` (how many descriptions), ``years``
and the first ``example``; a fix that changes nothing is dropped, so every
row of the file does something.

Like the build, the finders leave the stretches a ``word`` row of
``spelling.csv`` matches to that row (a hand decision wins), and a fix that
changes no word (``spaced_suffix``) may cross them.

``canonical.csv`` is chosen first, by what the steps as they stand make of
each variant (``words.csv`` included); ``words.csv`` is then found on the
labels as the new ``canonical.csv`` leaves them.  The command makes both again,
each time from the last, until they stop changing (at most ROUNDS times): they
come out the same from nothing as from the files as they stand, and a test
checks that they are up to date.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from pathlib import Path

import polars as pl

from .. import csv_io
from ..utils import ZWNJ
from . import hazm_rules
from .canonical import choose_wordings, folded_fixes, learned_fixes, unknown_words, variant_groups
from .correct import labels as step1_labels
from .correct import trace
from .fixes import CANONICAL, SPELLING, WORDS, Fixes, FixList, read_spelling
from .lexicon import Lexicon, hazm_lexicon
from .rules import house_style
from .text import years_text
from .variants import variant_fixes

KINDS = ("learned", "folded", "variant", *hazm_rules.RULES)
COLUMNS = ["find", "replace", "kind", "uses", "years", "evidence", "example"]
PASSES = 3  # the most passes of the finders
ROUNDS = 10  # the most times autocorrect makes both files again, each from the last, until they settle
_PROPOSAL = {"find": pl.String, "replace": pl.String, "kind": pl.String, "evidence": pl.String}


@dataclasses.dataclass
class Context:
    """What a finder may read."""

    # year, key (the item), label: as the steps up to letters and the finders so far leave them
    labels: pl.DataFrame
    printed: pl.DataFrame  # the same, as the steps up to letters leave them: what the labels write
    variants: pl.DataFrame  # canonical.csv, and ``finished``: what the steps make of each winner
    lex: Lexicon
    hand: FixList  # every row of spelling.csv
    guard: FixList  # its word rows: the hand decisions
    found: pl.DataFrame = dataclasses.field(default_factory=pl.DataFrame)  # the fixes found so far


def _learned(ctx: Context) -> pl.DataFrame:
    # each loser lined up with what the label steps make of its group's best label
    learned = learned_fixes(
        ctx.variants.select(
            pl.col("find").map_elements(house_style, return_dtype=pl.String).alias("loser"),
            pl.col("finished").alias("winner"),
            pl.col("uses").cast(pl.Int64).alias("n"),
        )
    )
    # never a fix that writes more words hazm does not know, or more ZWNJs nothing
    # vouches for, than it finds: the best label of a group may itself be printed
    # badly (its words joined by ZWNJs)
    worse = [
        len(unknown_words(b, ctx.lex)) > len(unknown_words(a, ctx.lex))
        or hazm_rules.unlicensed_joins(b, ctx.lex) > hazm_rules.unlicensed_joins(a, ctx.lex)
        for a, b in learned.select("find", "replace").iter_rows()
    ]
    return learned.filter(~pl.Series(worse, dtype=pl.Boolean))


def _folded(ctx: Context) -> pl.DataFrame:
    # each distinct (year, label) counts once, so a word printed in more years weighs more
    return folded_fixes(ctx.labels.unique(["year", "label"], maintain_order=True)["label"], ctx.lex, ctx.hand)


def _variant(ctx: Context) -> pl.DataFrame:
    return variant_fixes(ctx.labels, ctx.hand, ctx.lex)


def _hazm(ctx: Context) -> pl.DataFrame:
    # how often the labels write a word is read from them both as printed and as
    # the finders leave them: an earlier finder may have respelled every other
    # بجز, but بجزروانی still holds one; a printed word the fixes only cut
    # apart (ونظایر) is no word
    glued = []
    if ctx.found.height:
        same = ctx.found.filter(
            pl.col("find").str.replace_all(f"[ {ZWNJ}]", "")
            == pl.col("replace").str.replace_all(f"[ {ZWNJ}]", "")
        )
        glued = same["find"].to_list()
    words = hazm_rules.Labels.either(ctx.printed["label"], ctx.labels["label"], glued)
    return hazm_rules.find_fixes(ctx.labels, ctx.lex, ctx.guard, words)


FINDERS: tuple[tuple[str, Callable[[Context], pl.DataFrame]], ...] = (
    ("learned", _learned),
    ("folded", _folded),
    ("variant", _variant),
    ("hazm", _hazm),
)


def ordered(df: pl.DataFrame) -> pl.DataFrame:
    """Fixes in the order the build applies them: by kind, then the longest find first."""
    return df.sort(
        pl.col("kind").replace_strict(KINDS, range(len(KINDS))),
        pl.col("find").str.len_chars(),
        "find",
        descending=[False, True, False],
    )


def _apply(labels: pl.DataFrame, fixes: FixList, guard: FixList) -> pl.DataFrame:
    """``labels`` with ``fixes`` applied to each distinct label, as the build applies them."""
    distinct = labels["label"].unique()
    done = [fixes.settle(t, 0, None, guard) for t in distinct]
    return labels.with_columns(pl.col("label").replace_strict(distinct, done))


def bookkeeping(labels: pl.DataFrame, words: pl.DataFrame, guard: FixList) -> pl.DataFrame:
    """``words`` with what each fix matches when the whole list is applied to
    ``labels`` (``year``, ``label``) as the build applies it: ``uses`` (how many
    descriptions), ``years`` and the first ``example``; a fix that matches
    nothing is dropped."""
    fixes = FixList.from_frame(words)
    rows = list(fixes)
    distinct = labels.group_by("label", maintain_order=True).agg(pl.len().alias("n"), pl.col("year").unique())
    hits = []
    for label in distinct["label"]:
        h: list = []
        fixes.settle(label, 0, h, guard)
        # the hits come in list order, round after round: each is the next row
        # equal to it (a fix may be listed again, in a later pass)
        at, idx = 0, []
        for fx in h:
            nxt = next((i for i in range(at, len(rows)) if rows[i] == fx), None)
            at = rows.index(fx) if nxt is None else nxt  # a new round starts over
            idx.append(at)
            at += 1
        hits.append(sorted(set(idx)))
    matched = (
        distinct.with_columns(pl.Series("i", hits, dtype=pl.List(pl.UInt32)))
        .explode("i")
        .drop_nulls("i")
        .group_by("i", maintain_order=True)
        .agg(
            pl.col("n").sum().alias("uses"),
            pl.col("year").list.explode(keep_nulls=False, empty_as_null=False).unique().alias("years"),
            pl.col("label").first().alias("example"),
        )
    )
    return (
        words.with_row_index("i")
        .join(matched, on="i", maintain_order="left")
        .with_columns(pl.col("years").map_elements(years_text, return_dtype=pl.String))
        .select(COLUMNS)
    )


def find_words(
    labels: pl.DataFrame, variants: pl.DataFrame, lex: Lexicon, hand: FixList, guard: FixList
) -> pl.DataFrame:
    """``words.csv``: every finder in turn on ``labels`` (``year``, ``key``,
    ``label``, as the steps up to ``letters`` leave them), each on the labels
    as the fixes found before leave them, in passes until a pass adds nothing
    that changes a label; then the bookkeeping."""
    ctx = Context(labels, labels, variants, lex, hand, guard)
    found = pl.DataFrame(schema=_PROPOSAL)
    kept = None  # the bookkeeping of the fixes as the last pass left them
    for n in range(PASSES):
        for _, finder in FINDERS:
            proposed = finder(ctx).select(list(_PROPOSAL)).unique("find", keep="first", maintain_order=True)
            # a find an earlier fix writes otherwise is left to it; one it writes
            # alike stays, for the text the fixes between them made (و + انرژی درمانی)
            earlier = found.select("find", pl.col("replace").alias("earlier")).unique("find", keep="first")
            new = ordered(
                proposed.join(earlier, on="find", how="left")
                .filter(pl.col("earlier").is_null() | (pl.col("earlier") == pl.col("replace")))
                .drop("earlier")
            )
            if new.height:  # else the fixes, and so the labels, stay as they are
                found = pl.concat([found, new])
                ctx.labels = _apply(labels, FixList.from_frame(found), guard)
                ctx.found = found
        now = bookkeeping(labels, found, guard)
        if n and now.height == kept.height:
            return kept  # this pass changed nothing more
        kept = now
    return kept


def find_all(
    spelling: Path = SPELLING, words: Path = WORDS, canonical: Path = CANONICAL
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """``canonical.csv`` and ``words.csv`` as the finders make them today,
    each variant judged by the steps with the files at these paths."""
    lex = hazm_lexicon()
    fixes = Fixes.load(spelling, words, canonical)
    labels = step1_labels()

    def finish(texts: pl.Series) -> pl.Series:
        return trace(pl.DataFrame({"year": 0, "description": texts}), fixes)["spelling"]

    groups = choose_wordings(variant_groups(labels, finish), lex)
    learning = groups.with_columns(finish(groups["replace"]).alias("finished"))
    fixes = dataclasses.replace(fixes, variants=dict(zip(groups["find"], groups["replace"], strict=True)))
    at_letters = trace(labels, fixes, upto="letters").select("year", "key", pl.col("letters").alias("label"))
    return groups, find_words(at_letters, learning, lex, read_spelling(spelling), fixes.spelling)


def main(*, spelling: Path = SPELLING, canonical: Path = CANONICAL, words: Path = WORDS) -> None:
    """Write the automatic fixes (canonical.csv, words.csv) with hazm's word list.

    Needs hazm's data (``hiesir-codebook hazm download``).

    Parameters
    ----------
    spelling
        The hand decisions, which the automatic fixes leave alone.
    canonical
        One wording for each group of labels printed in several ways.
    words
        The automatic word fixes.
    """
    for n in range(1, ROUNDS + 1):  # noqa: B007 (n is reported below)
        groups, found = find_all(spelling, words, canonical)
        found = found.with_columns(pl.col("uses").cast(pl.String))
        settled = canonical.exists() and words.exists()
        settled = (
            settled and groups.equals(csv_io.read_frame(canonical)) and found.equals(csv_io.read_frame(words))
        )
        csv_io.write_frame(groups, canonical)
        csv_io.write_frame(found, words)
        if settled:
            break
    else:
        raise RuntimeError(f"the automatic fixes did not settle in {ROUNDS} rounds")
    print(f"settled after {n} rounds")
    print(
        f"{groups.height} labels written otherwise in their group -> {canonical.as_posix()} "
        f"({groups['uses'].cast(pl.Int64).sum()} rows)"
    )
    counts = found.group_by("kind").agg(pl.len(), pl.col("uses").cast(pl.Int64).sum())
    by_kind = {k: (n, u) for k, n, u in counts.iter_rows()}
    print(
        f"{found.height} word fixes -> {words.as_posix()}: "
        + ", ".join(f"{k} {by_kind[k][0]} ({by_kind[k][1]} uses)" for k in KINDS if k in by_kind)
    )
