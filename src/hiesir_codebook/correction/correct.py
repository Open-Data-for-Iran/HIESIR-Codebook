"""The correction stage: ``output/1_extracted/`` -> ``output/2_corrected/``.

Each questionnaire goes through five steps, in this order:

1. :mod:`.corrections`: ``curated/2_corrected/corrections.csv`` fixes codes,
   rows and sections; the structure check, with
   ``curated/2_corrected/header_exceptions.csv``, says what must then hold
2. :mod:`.canonical`: ``output/2_corrected/autocorrect/canonical.csv`` gives
   labels that differ only in spaces, ZWNJs and letter forms one wording
3. :mod:`.rules`: the house style every description gets, with no word list
   (punctuation spacing, the Academy's spelling rules), and the letter fixes
   of spelling.csv
4. :mod:`.autocorrect`: ``output/2_corrected/autocorrect/hazm.csv``, the
   fixes found automatically with hazm's word list in the extracted labels
5. :mod:`.spelling`: ``curated/2_corrected/spelling.csv`` fixes the spellings
   hazm cannot settle

``--check`` adds the household occurrence tables
(``data/commodity_code_occurrence_*.csv``, 1383-1403): the evidence for each
correction, and the codes reported by households but missing from the
questionnaire, or printed but never reported.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

import polars as pl

from .. import CORRECTED, CSV_COLUMNS, EXTRACTED, SUPPORTED_YEARS, csv_io
from ..occurrence import occurrence_files
from ..utils import ZWNJ
from .autocorrect import HAZM_FIXES, fix_free, load_fixes
from .canonical import CANONICAL, CANONICAL_WORDS, load_variants, load_word_fixes
from .corrections import (
    CORRECTIONS,
    Correction,
    apply_corrections,
    check_occurrence,
    load_corrections,
    verify,
)
from .rules import house_style
from .spelling import LABELS, LabelFix, fix_label, load_label_fixes


def read_rows(path: Path) -> list[dict[str, str]]:
    return csv_io.read(path)


def write_rows(rows: Iterable[dict[str, str]], path: Path) -> None:
    csv_io.write(path, CSV_COLUMNS, rows)


@dataclass
class Steps:
    """Steps 2-5 for one description, from what step 1 leaves: the canonical
    wording of its group, the house style with the letter fixes of
    spelling.csv (its ``text`` rows), the automatic fixes, then the word fixes
    of spelling.csv; where a word row matches, the automatic fixes leave that
    stretch to it."""

    labels: list[LabelFix] = field(default_factory=list)
    auto: list[LabelFix] = field(default_factory=list)
    canonical: dict[str, str] = field(default_factory=dict)
    upto: int = 5  # the last step to run (3: what autocorrect reads)
    words: list[LabelFix] = field(default_factory=list)  # canonical_words.csv

    def __post_init__(self) -> None:
        self.letters = [fx for fx in self.labels if fx.match == "text"]
        self.decided = [fx for fx in self.labels if fx.match == "word"]
        # the finds of the rows bound to some years: a description holding one
        # of them is run once per year, every other once for all years
        self._dated = [fx.find.replace(ZWNJ, "") for fx in [*self.labels, *self.auto] if fx.years is not None]

    def dated(self, text: str) -> bool:
        bare = text.replace(ZWNJ, "")
        return any(f in bare for f in self._dated)

    def __call__(self, text: str, year: int, hits: dict | None = None, auto_hits: dict | None = None) -> str:
        text = self.canonical.get(text, text)
        # where a word row of spelling.csv matches, the word fixes leave that stretch to it
        text = fix_free(text, year, self.words, self.decided) if self.words else text
        if self.upto < 3:
            return text
        text = fix_label(house_style(text), year, self.letters, hits)
        if self.upto < 4:
            return text
        text = fix_free(text, year, self.auto, self.decided, auto_hits) if self.auto else text
        if self.upto < 5:
            return text
        return fix_label(text, year, self.decided, hits)


def run_steps(
    pairs: list[tuple[int, str]],
    steps: Steps,
    hits: dict[str, int] | None = None,
    auto_hits: dict[str, int] | None = None,
) -> list[str]:
    """``steps`` on every ``(year, description)``, once per distinct description
    (and year, for a description a dated row may touch): 27,000 rows hold
    about 3,500 distinct labels.  ``hits`` count rows, as if run row by row."""
    if not pairs:
        return []
    df = pl.DataFrame({"year": [y for y, _ in pairs], "text": [t for _, t in pairs]}, orient="col")
    texts = df.get_column("text").unique().to_list()
    dated = {t for t in texts if steps.dated(t)}
    df = df.with_columns(
        pl.when(pl.col("text").is_in(list(dated))).then(pl.col("year")).otherwise(0).alias("key")
    )
    unique = df.group_by(["text", "key"]).agg(pl.len().alias("n"))
    done: dict[tuple[str, int], str] = {}
    for text, key, n in unique.iter_rows():
        h: dict[str, int] = {}
        a: dict[str, int] = {}
        done[text, key] = steps(text, key, h, a)
        for into, got in ((hits, h), (auto_hits, a)):
            if into is not None:
                for k, v in got.items():
                    into[k] = into.get(k, 0) + v * n
    return [done[t, k] for t, k in df.select("text", "key").iter_rows()]


def apply(
    year: int,
    rows: list[dict[str, str]],
    corrections: list[Correction],
    extracted: Path,
    labels: list[LabelFix] = (),
    hits: dict[str, int] | None = None,
    auto: list[LabelFix] = (),
    auto_hits: dict[str, int] | None = None,
    canonical: dict[str, str] | None = None,
    words: list[LabelFix] = (),
) -> list[dict[str, str]]:
    """One questionnaire through the five steps (see :class:`Steps`)."""
    rows = apply_corrections(year, rows, corrections, extracted)
    steps = Steps(list(labels), list(auto), canonical or {}, words=list(words))
    for r, new in zip(
        rows, run_steps([(year, r["description"]) for r in rows], steps, hits, auto_hits), strict=True
    ):
        r["description"] = new
    return rows


def _after_step1(years: Iterable[int], extracted: Path, corrections: Path) -> dict[int, list[dict[str, str]]]:
    fixes = load_corrections(corrections)
    return {
        y: apply_corrections(y, read_rows(extracted / f"questionnaire_{y}.csv"), fixes, extracted)
        for y in years
    }


def labels_after_corrections(
    years: Iterable[int] = SUPPORTED_YEARS, extracted: Path = EXTRACTED, corrections: Path = CORRECTIONS
) -> list[tuple[int, str]]:
    """``(year, description)`` of every row as step 1 leaves it: what
    :mod:`.canonical` reads."""
    return [
        (y, r["description"]) for y, rows in _after_step1(years, extracted, corrections).items() for r in rows
    ]


def labels_for_autocorrect(
    years: Iterable[int] = SUPPORTED_YEARS,
    extracted: Path = EXTRACTED,
    corrections: Path = CORRECTIONS,
    labels: Path = LABELS,
    canonical: Path = CANONICAL,
    canonical_words: Path = CANONICAL_WORDS,
) -> list[tuple[int, str]]:
    """``(year, description)`` of every row through steps 1-3 (the structural
    corrections, the canonical wording and words, the house style and the
    letter fixes of spelling.csv): what :mod:`.autocorrect` reads, so it meets
    the print's own errors, not what the word fixes of spelling.csv leave."""
    pairs = labels_after_corrections(years, extracted, corrections)
    steps = Steps(
        load_label_fixes(labels), [], load_variants(canonical), upto=3, words=load_word_fixes(canonical_words)
    )
    return list(zip([y for y, _ in pairs], run_steps(pairs, steps), strict=True))


def correct(
    years: Iterable[int] = SUPPORTED_YEARS,
    extracted: Path = EXTRACTED,
    out: Path = CORRECTED,
    corrections: Path = CORRECTIONS,
    labels: Path = LABELS,
    hits: dict[str, int] | None = None,
    autocorrect: Path = HAZM_FIXES,
    auto_hits: dict[str, int] | None = None,
    canonical: Path = CANONICAL,
    canonical_words: Path = CANONICAL_WORDS,
) -> dict[int, int]:
    """Write ``out/questionnaire_<year>.csv`` for every year; return the
    number of row corrections applied per year.  ``hits`` collects how many
    descriptions each label fix changed, ``auto_hits`` each automatic fix."""
    years = list(years)
    fixes = load_corrections(corrections)
    unknown = {c.year for c in fixes} - set(years)
    if unknown:
        raise ValueError(f"corrections for years not processed: {sorted(unknown)}")
    by_year = _after_step1(years, extracted, corrections)
    steps = Steps(
        load_label_fixes(labels),
        load_fixes(autocorrect),
        load_variants(canonical),
        words=load_word_fixes(canonical_words),
    )
    pairs = [(y, r["description"]) for y, rows in by_year.items() for r in rows]
    new = iter(run_steps(pairs, steps, hits, auto_hits))
    for y, rows in by_year.items():
        for r in rows:
            r["description"] = next(new)
        write_rows(rows, out / f"questionnaire_{y}.csv")
    return {y: sum(c.year == y for c in fixes) for y in years}


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(
        description="Apply curated/2_corrected/ to output/1_extracted/ -> output/2_corrected/."
    )
    ap.add_argument("--extracted", type=Path, default=EXTRACTED)
    ap.add_argument("--out", type=Path, default=CORRECTED)
    ap.add_argument("--corrections", type=Path, default=CORRECTIONS)
    ap.add_argument("--check", action="store_true", help="compare with the household occurrence table")
    ap.add_argument("--labels", type=Path, default=LABELS)
    ap.add_argument(
        "--occurrence",
        type=Path,
        nargs="+",
        default=occurrence_files(),
        help="default: data/commodity_code_occurrence_*.csv",
    )
    args = ap.parse_args(argv)
    hits: dict[str, int] = {}
    counts = correct(SUPPORTED_YEARS, args.extracted, args.out, args.corrections, args.labels, hits)
    print(
        f"{sum(counts.values())} row corrections applied: "
        + ", ".join(f"{y}: {n}" for y, n in counts.items() if n)
    )
    label_fixes = load_label_fixes(args.labels)
    print(f"{len(label_fixes)} label fixes changed {sum(hits.values())} descriptions")
    unused = [fx.find for fx in label_fixes if fx.find not in hits]
    if args.check:
        for fx in label_fixes:
            print(f"    {hits.get(fx.find, 0):4}  {fx.find} -> {fx.replace}")
    if unused:
        print("label fixes that matched nothing: " + ", ".join(unused))
    if args.check:
        years = SUPPORTED_YEARS
        print("\nEvidence for each correction (households reporting the code):")
        contradicted = verify(load_corrections(args.corrections), args.extracted, args.occurrence)
        print("\nCorrected questionnaires against the raw data:")
        failed = check_occurrence(years, args.out, args.occurrence)
        raise SystemExit(1 if contradicted or failed else 0)


if __name__ == "__main__":
    main()
