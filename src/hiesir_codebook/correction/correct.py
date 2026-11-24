"""The correction stage: ``output/1_extracted/`` -> ``output/2_corrected/``.

Every questionnaire is read into one polars table (a ``year`` column added),
step 1 (:mod:`.corrections`: ``curated/2_corrected/corrections.csv``) fixes
its codes, rows and sections, and :func:`trace` then takes each description
through the label steps, adding one column per step:

=============== ======================================================== ==========
column          what the step does                                       per year
=============== ======================================================== ==========
``canonical``   a label printed in several ways gets its group's wording no
                (``canonical.csv``)
``house_style`` punctuation spacing and the Academy's spelling rules     no
                (:mod:`.rules`)
``letters``     the ``text`` rows of ``spelling.csv``: letters inside    yes
                words (تزئین -> تزیین)
``words``       the automatic word fixes (``words.csv``): learned from   no
                the groups, folded letter forms, variants, hazm's
                rules; applied until the label stops changing
``spelling``    the ``word`` rows of ``spelling.csv``: the hand          yes
                decisions, the corrected description
=============== ======================================================== ==========

(the files are described in :mod:`.fixes`).  A step runs once per distinct
text (and year, for a step whose rows may be bound to some years): 27,000
rows hold about 3,500 distinct labels.  The ``words`` step leaves the
stretches a ``word`` row of ``spelling.csv`` matches to that row, so a hand
decision always wins.

The ``autocorrect`` command (:mod:`.words`) writes ``canonical.csv`` and
``words.csv`` from this same table; ``metrics`` counts what each column changes.

``--check`` adds the code usage table
(``data/code_usage.csv``): the evidence for each
correction, and the codes reported by households but missing from the
questionnaire, or printed but never reported.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path
from typing import NamedTuple

import polars as pl

from .. import CORRECTED, CSV_COLUMNS, EXTRACTED, SUPPORTED_YEARS, csv_io
from ..usage import CODE_USAGE
from .corrections import CORRECTIONS, check_occurrence, corrected_questionnaires, load_corrections, verify
from .fixes import CANONICAL, SPELLING, WORDS, Fix, Fixes, read_spelling
from .rules import house_style


class Step(NamedTuple):
    name: str
    run: Callable[[str, int, list[Fix]], str]  # (text, year, hits) -> text
    per_year: bool  # does the year matter (rows bound to some years)?


def steps(fixes: Fixes) -> list[Step]:
    """The label steps, in order, with the fixes each applies."""
    return [
        Step("canonical", lambda text, year, hits: fixes.variants.get(text, text), False),
        Step("house_style", lambda text, year, hits: house_style(text), False),
        Step("letters", fixes.letters.apply, True),
        Step("words", lambda text, year, hits: fixes.words.settle(text, year, hits, fixes.spelling), False),
        Step("spelling", fixes.spelling.apply, True),
    ]


STEPS = [s.name for s in steps(Fixes())]


def trace(labels: pl.DataFrame, fixes: Fixes, upto: str = STEPS[-1]) -> pl.DataFrame:
    """``labels`` (``year``, ``description``) with a column for each label step
    up to ``upto``: the text as that step leaves it, and ``<step>_hits``, the
    finds of the fixes that matched it."""
    df, text = labels, "description"
    for step in steps(fixes)[: STEPS.index(upto) + 1]:
        keys = [text, "year"] if step.per_year else [text]
        todo = df.select(keys).unique(maintain_order=True)
        done, hits = [], []
        for row in todo.iter_rows():
            h: list[Fix] = []
            done.append(step.run(row[0], row[1] if step.per_year else 0, h))
            hits.append([fx.find for fx in h])
        todo = todo.with_columns(
            pl.Series(step.name, done, dtype=pl.String),
            pl.Series(f"{step.name}_hits", hits, dtype=pl.List(pl.String)),
        )
        df = df.join(todo, on=keys, how="left", maintain_order="left")
        text = step.name
    return df


# --- the stage ------------------------------------------------------------------


def corrected(
    years: Iterable[int] = SUPPORTED_YEARS,
    extracted: Path = EXTRACTED,
    corrections: Path = CORRECTIONS,
    fixes: Fixes | None = None,
    upto: str = STEPS[-1],
) -> pl.DataFrame:
    """Every row of every year after step 1, traced through the label steps
    up to ``upto`` (see :func:`trace`)."""
    rows = corrected_questionnaires(years, extracted, load_corrections(corrections))
    traced = trace(rows.select("year", "description"), fixes or Fixes.load(), upto)
    return pl.concat([rows.drop("description"), traced.drop("year")], how="horizontal")


def labels(
    years: Iterable[int] = SUPPORTED_YEARS, extracted: Path = EXTRACTED, corrections: Path = CORRECTIONS
) -> pl.DataFrame:
    """``year``, ``key`` (the item: its expenditure code; for a header or a
    section title, its kind, section and code) and ``description`` of every row
    as step 1 leaves it, before the label steps."""
    rows = corrected_questionnaires(years, extracted, load_corrections(corrections))
    key = (
        pl.when(pl.col("kind") == "item")
        .then(pl.col("expenditure_code"))
        .otherwise(pl.concat_str("kind", "section", "code", separator=" "))
    )
    return rows.select("year", key.alias("key"), "description")


def correct(
    years: Iterable[int] = SUPPORTED_YEARS,
    extracted: Path = EXTRACTED,
    out: Path = CORRECTED,
    corrections: Path = CORRECTIONS,
    spelling: Path = SPELLING,
    words: Path = WORDS,
    canonical: Path = CANONICAL,
) -> pl.DataFrame:
    """Write ``out/questionnaire_<year>.csv`` for every year; return the traced
    table (see :func:`corrected`)."""
    years = list(years)
    unknown = {c.year for c in load_corrections(corrections)} - set(years)
    if unknown:
        raise ValueError(f"corrections for years not processed: {sorted(unknown)}")
    fixes = Fixes.load(spelling, words, canonical)
    df = corrected(years, extracted, corrections, fixes)
    for (year,), rows in df.group_by("year", maintain_order=True):
        columns = [c for c in CSV_COLUMNS if c in rows.columns]
        csv_io.write_frame(
            rows.with_columns(pl.col("spelling").alias("description")).select(columns),
            out / f"questionnaire_{year}.csv",
        )
    return df


def spelling_hits(df: pl.DataFrame) -> dict[str, int]:
    """How many descriptions each row of spelling.csv matched, from a traced table."""
    hits = pl.concat([df.select(h=c).explode("h") for c in ("letters_hits", "spelling_hits")]).drop_nulls()
    counts = hits.group_by("h").len()
    return dict(zip(counts["h"], counts["len"], strict=True))


def main(
    *,
    extracted: Path = EXTRACTED,
    out: Path = CORRECTED,
    corrections: Path = CORRECTIONS,
    spelling: Path = SPELLING,
    check: bool = False,
    usage: Path = CODE_USAGE,
) -> int:
    """Apply curated/2_corrected/ to output/1_extracted/ -> output/2_corrected/.

    Parameters
    ----------
    extracted
        The questionnaires as printed.
    out
        Where the corrected questionnaires go.
    corrections
        The row corrections.
    spelling
        The spelling fixes.
    check
        Also compare with the code usage table; fails when the raw data
        contradicts a correction or a corrected questionnaire.
    usage
        The code usage table.
    """
    df = correct(SUPPORTED_YEARS, extracted, out, corrections, spelling)
    fixes = load_corrections(corrections)
    by_year = {y: sum(c.year == y for c in fixes) for y in SUPPORTED_YEARS}
    print(
        f"{sum(by_year.values())} row corrections applied: "
        + ", ".join(f"{y}: {n}" for y, n in by_year.items() if n)
    )
    hits = spelling_hits(df)
    rows = read_spelling(spelling)
    print(f"{len(rows)} label fixes changed {sum(hits.values())} descriptions")
    if check:
        for fx in rows:
            print(f"    {hits.get(fx.find, 0):4}  {fx.find} -> {fx.replace}")
    unused = [fx.find for fx in rows if fx.find not in hits]
    if unused:
        # such a row may still work through the automatic fixes: it decides the
        # wording of a canonical group, or teaches a learned word fix
        print("label fixes that change no description themselves: " + ", ".join(unused))
    if not check:
        return 0
    print("\nEvidence for each correction (households reporting the code):")
    contradicted = verify(fixes, extracted, usage)
    print("\nCorrected questionnaires against the raw data:")
    failed = check_occurrence(SUPPORTED_YEARS, out, usage)
    return 1 if contradicted or failed else 0
