"""The correction stage: ``output/1_extracted/`` -> ``output/2_corrected/``.

Each questionnaire goes through four steps, in this order:

1. :mod:`.corrections`: ``curated/2_corrected/corrections.csv`` fixes codes,
   rows and sections; the structure check, with
   ``curated/2_corrected/header_exceptions.csv``, says what must then hold
2. :mod:`.rules`: the house style every description gets, with no word list
   (punctuation spacing, the Academy's spelling rules)
3. :mod:`.autocorrect`: ``output/2_corrected/autocorrect/hazm.csv``, the
   fixes found automatically with hazm's word list in the extracted labels
4. :mod:`.spelling`: ``curated/2_corrected/spelling.csv`` fixes the spellings
   hazm cannot settle

``--check`` adds the household occurrence tables
(``data/commodity_code_occurrence_*.csv``, 1382-1403): the evidence for each
correction, and the codes reported by households but missing from the
questionnaire, or printed but never reported.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable
from pathlib import Path

from .. import CORRECTED, CSV_COLUMNS, EXTRACTED, SUPPORTED_YEARS, csv_io
from ..occurrence import occurrence_files
from .autocorrect import HAZM_FIXES, fix_free, load_fixes
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


def apply(
    year: int,
    rows: list[dict[str, str]],
    corrections: list[Correction],
    extracted: Path,
    labels: list[LabelFix] = (),
    hits: dict[str, int] | None = None,
    auto: list[LabelFix] = (),
    auto_hits: dict[str, int] | None = None,
) -> list[dict[str, str]]:
    """One questionnaire through the four steps: its corrections, the house
    style of every description (with the letter fixes of spelling.csv, its
    ``text`` rows: تزئین -> تزیین, هزنیه -> هزینه), the automatic fixes, then
    the word fixes of spelling.csv."""
    rows = apply_corrections(year, rows, corrections, extracted)
    labels, auto = list(labels), list(auto)
    letters = [fx for fx in labels if fx.match == "text"]
    # where a word row matches, the automatic fixes leave that stretch to it
    decided = [fx for fx in labels if fx.match == "word"]
    for r in rows:
        text = fix_label(house_style(r["description"]), year, letters, hits)
        text = fix_free(text, year, auto, decided, auto_hits) if auto else text
        r["description"] = fix_label(text, year, decided, hits)
    return rows


def labels_for_autocorrect(
    years: Iterable[int] = SUPPORTED_YEARS,
    extracted: Path = EXTRACTED,
    corrections: Path = CORRECTIONS,
    labels: Path = LABELS,
) -> list[tuple[int, str]]:
    """``(year, description)`` of every row as extracted, with only steps 1-2
    (the structural corrections, the house style and the letter fixes of
    spelling.csv): what :mod:`.autocorrect` reads, so it meets the print's own
    errors, not what the word fixes of spelling.csv leave."""
    fixes = load_corrections(corrections)
    letters = [fx for fx in load_label_fixes(labels) if fx.match == "text"]
    return [
        (year, r["description"])
        for year in years
        for r in apply(year, read_rows(extracted / f"questionnaire_{year}.csv"), fixes, extracted, letters)
    ]


def correct(
    years: Iterable[int] = SUPPORTED_YEARS,
    extracted: Path = EXTRACTED,
    out: Path = CORRECTED,
    corrections: Path = CORRECTIONS,
    labels: Path = LABELS,
    hits: dict[str, int] | None = None,
    autocorrect: Path = HAZM_FIXES,
    auto_hits: dict[str, int] | None = None,
) -> dict[int, int]:
    """Write ``out/questionnaire_<year>.csv`` for every year; return the
    number of row corrections applied per year.  ``hits`` collects how many
    descriptions each label fix changed, ``auto_hits`` each automatic fix."""
    fixes = load_corrections(corrections)
    label_fixes = load_label_fixes(labels)
    auto = load_fixes(autocorrect)
    counts = {}
    for year in years:
        rows = read_rows(extracted / f"questionnaire_{year}.csv")
        rows = apply(year, rows, fixes, extracted, label_fixes, hits, auto, auto_hits)
        write_rows(rows, out / f"questionnaire_{year}.csv")
        counts[year] = sum(c.year == year for c in fixes)
    unknown = {c.year for c in fixes} - set(years)
    if unknown:
        raise ValueError(f"corrections for years not processed: {sorted(unknown)}")
    return counts


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
        years = SUPPORTED_YEARS  # 1382 from the 1363-1382 table
        print("\nEvidence for each correction (households reporting the code):")
        contradicted = verify(load_corrections(args.corrections), args.extracted, args.occurrence)
        print("\nCorrected questionnaires against the raw data:")
        failed = check_occurrence(years, args.out, args.occurrence)
        raise SystemExit(1 if contradicted or failed else 0)


if __name__ == "__main__":
    main()
