"""Apply hand-kept corrections to the extracted questionnaires.

``output/1_extracted/`` holds each questionnaire exactly as printed, typos
included. ``curated/source.csv`` lists every deviation from the print, one
row each, with the reason; this module applies them and writes the result to
``output/2_corrected/``, which the matcher reads.

Columns of ``source.csv``:

========== ===================================================================
year       questionnaire year
action     ``recode``: set the expenditure code of an item
           ``retext``: set the description of an item
           ``delete``: remove an item (and group headers left without items)
           ``add_section``: copy a section missing from the PDF from another
           year (``description`` = section number, ``value`` = source year)
expenditure_code  the item's code as printed
description       the item's description as printed (identifies the row
                  when a code is printed twice)
value      the corrected code or description (empty for ``delete``)
reason     why: evidence from neighbouring years, the raw data, ...
========== ===================================================================

After the listed corrections, every description gets the same punctuation
spacing (:func:`hiesir_codebook.utils.tidy_punctuation`): "،" and ":"
attach to the word before them, brackets hug their content, "..." has three
dots.

Then ``curated/labels.csv`` fixes spellings that recur across rows and
years (typos, joined words, missing ZWNJs), applied to every description in
file order:

========== ===================================================================
find       the wrong form (may be several words), as it reads after the
           punctuation clean-up
replace    the right form
match      ``word``: only as whole words (not inside a longer word);
           ``text``: anywhere in the label
years      empty for all years, else years and ranges: ``1386``,
           ``1383-1385``, ``1383-1385 1390``
reason     why
========== ===================================================================

``--check`` compares the corrected item codes with the household
occurrence table (``data/commodity_code_occurrence_1383-1403.csv``): a code
reported by households but missing from the questionnaire, or printed but
never reported, is worth a look.
"""

from __future__ import annotations

import argparse
import csv
import re
from collections.abc import Iterable
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

from . import CORRECTED, CSV_COLUMNS, CURATED, DATA_DIR, EXTRACTED, SUPPORTED_YEARS
from .utils import ZWNJ, collapse_whitespace, tidy_punctuation

CORRECTIONS = CURATED / "source.csv"
LABELS = CURATED / "labels.csv"
# a letter or digit of a word (Arabic-script letters, not punctuation such as "،")
_WORD_CHAR = f"[ء-ٟٮ-ۓە۰-۹{ZWNJ}A-Za-z0-9]"
OCCURRENCE = DATA_DIR / "commodity_code_occurrence_1383-1403.csv"
ACTIONS = ("recode", "retext", "delete", "add_section")


@dataclass
class Correction:
    year: int
    action: str
    expenditure_code: str
    description: str
    value: str
    reason: str


def load_corrections(path: Path = CORRECTIONS) -> list[Correction]:
    with open(path, encoding="utf-8-sig") as f:
        out = [
            Correction(
                int(r["year"]),
                r["action"],
                r["expenditure_code"],
                r["description"],
                r["value"],
                r["reason"],
            )
            for r in csv.DictReader(f)
        ]
    for c in out:
        if c.action not in ACTIONS:
            raise ValueError(f"unknown action {c.action!r} in {path}")
        if not c.reason.strip():
            raise ValueError(f"correction without a reason: {c}")
    return out


@dataclass
class LabelFix:
    find: str
    replace: str
    match: str  # "word" | "text"
    years: frozenset[int] | None  # None = all years
    reason: str

    @cached_property
    def pattern(self) -> re.Pattern:
        p = re.escape(self.find)
        if self.match == "word":
            edge = _WORD_CHAR  # letters and digits, not "،" or "؛"
            p = f"(?<!{edge}){p}(?!{edge})"
        return re.compile(p)


def _years(spec: str) -> frozenset[int] | None:
    """'' -> None (all years); '1383-1385 1390' -> {1383, 1384, 1385, 1390}."""
    if not spec.strip():
        return None
    out: set[int] = set()
    for part in re.split(r"[\s,]+", spec.strip()):
        lo, _, hi = part.partition("-")
        out.update(range(int(lo), int(hi or lo) + 1))
    return frozenset(out)


def load_label_fixes(path: Path = LABELS) -> list[LabelFix]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8-sig") as f:
        out = [
            LabelFix(r["find"], r["replace"], r["match"] or "word", _years(r["years"]), r["reason"])
            for r in csv.DictReader(f)
        ]
    for fx in out:
        if fx.match not in ("word", "text"):
            raise ValueError(f"{path}: match must be 'word' or 'text', got {fx.match!r} ({fx.find})")
        if not fx.find or not fx.reason.strip():
            raise ValueError(f"{path}: every row needs find and reason ({fx.find})")
    return out


def fix_label(text: str, year: int, fixes: list[LabelFix], hits: dict[str, int] | None = None) -> str:
    """Apply the label fixes for ``year`` to one description, in order."""
    for fx in fixes:
        if fx.find not in text or (fx.years is not None and year not in fx.years):
            continue  # the substring test is a cheap filter before the regex
        new, n = fx.pattern.subn(fx.replace, text)
        if n and hits is not None:
            hits[fx.find] = hits.get(fx.find, 0) + 1
        text = new
    return text


def read_rows(path: Path) -> list[dict[str, str]]:
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write_rows(rows: Iterable[dict[str, str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, CSV_COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def _find(rows: list[dict[str, str]], c: Correction) -> dict[str, str]:
    hits = [
        r
        for r in rows
        if r["kind"] == "item"
        and r["expenditure_code"] == c.expenditure_code
        and (not c.description or collapse_whitespace(r["description"]) == collapse_whitespace(c.description))
    ]
    if len(hits) != 1:
        raise ValueError(f"{c.year} {c.action} {c.expenditure_code}: {len(hits)} matching rows, expected 1")
    return hits[0]


def _header_codes(r: dict[str, str]) -> list[str]:
    return [re.sub(r"\D", "", c) for c in r["code"].split(",")]


def _orphan_header(r: dict[str, str], gone: dict[str, str], rows: list[dict[str, str]]) -> bool:
    """A group header that covered the deleted item and now covers none."""
    if r["kind"] != "header" or r["section"] != gone["section"]:
        return False
    codes = _header_codes(r)
    if not any(gone["expenditure_code"].startswith(c) for c in codes):
        return False
    return not any(
        x["kind"] == "item" and x["section"] == r["section"] and x["expenditure_code"].startswith(c)
        for x in rows
        for c in codes
    )


def apply(
    year: int,
    rows: list[dict[str, str]],
    corrections: list[Correction],
    extracted: Path,
    labels: list[LabelFix] = (),
    hits: dict[str, int] | None = None,
) -> list[dict]:
    """The rows of one questionnaire with its corrections applied."""
    rows = [dict(r) for r in rows]
    for c in corrections:
        if c.year != year:
            continue
        if c.action == "recode":
            r = _find(rows, c)
            r["expenditure_code"], r["code"], r["sub"] = c.value, c.value[:-2], c.value[-2:]
        elif c.action == "retext":
            _find(rows, c)["description"] = c.value
        elif c.action == "delete":
            gone = _find(rows, c)
            rows = [r for r in rows if r is not gone]
            rows = [r for r in rows if not _orphan_header(r, gone, rows)]
        elif c.action == "add_section":
            section = c.description
            if any(r["section"] == section for r in rows):
                raise ValueError(f"{year}: section {section} already present")
            src = [
                r for r in read_rows(extracted / f"questionnaire_{c.value}.csv") if r["section"] == section
            ]
            added = [{**r, "page": "", "top": "", "bottom": "", "left": "", "right": ""} for r in src]
            at = next((i for i, r in enumerate(rows) if int(r["section"]) > int(section)), len(rows))
            rows[at:at] = added
    # house style for every description, then the recurring spelling fixes
    for r in rows:
        r["description"] = fix_label(tidy_punctuation(r["description"]), year, list(labels), hits)
    return rows


def correct(
    years: Iterable[int] = SUPPORTED_YEARS,
    extracted: Path = EXTRACTED,
    out: Path = CORRECTED,
    corrections: Path = CORRECTIONS,
    labels: Path = LABELS,
    hits: dict[str, int] | None = None,
) -> dict[int, int]:
    """Write ``out/questionnaire_<year>.csv`` for every year; return the
    number of row corrections applied per year.  ``hits`` collects how many
    descriptions each label fix changed."""
    fixes = load_corrections(corrections)
    label_fixes = load_label_fixes(labels)
    counts = {}
    for year in years:
        rows = read_rows(extracted / f"questionnaire_{year}.csv")
        rows = apply(year, rows, fixes, extracted, label_fixes, hits)
        write_rows(rows, out / f"questionnaire_{year}.csv")
        counts[year] = sum(c.year == year for c in fixes)
    unknown = {c.year for c in fixes} - set(years)
    if unknown:
        raise ValueError(f"corrections for years not processed: {sorted(unknown)}")
    return counts


# --- check against the raw data ----------------------------------------------


def load_occurrence(path: Path = OCCURRENCE) -> dict[int, dict[int, int]]:
    """{year: {code: households}} from the occurrence table."""
    out: dict[int, dict[int, int]] = {}
    with open(path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            code = int(r["Commodity_Code"])
            for k, v in r.items():
                if k != "Commodity_Code" and v:
                    out.setdefault(int(k), {})[code] = int(v)
    return out


def check(years: Iterable[int], corrected: Path, occurrence: Path, min_households: int = 5) -> int:
    """Print codes that disagree with the raw data; return the number of
    years with a code reported by households but missing from the
    questionnaire (the strong signal of a typo or an extraction miss)."""
    occ = load_occurrence(occurrence)
    bad = 0
    for year in years:
        if year not in occ:
            continue
        items = [r for r in read_rows(corrected / f"questionnaire_{year}.csv") if r["kind"] == "item"]
        codes = [int(r["expenditure_code"]) for r in items]
        dup = sorted({c for c in codes if codes.count(c) > 1})
        # codes shorter than the 5-6 digit item codes are noise in the raw data
        invalid = sorted((c, n) for c, n in occ[year].items() if c < 10000)
        missing = sorted(
            (c, n) for c, n in occ[year].items() if c >= 10000 and c not in codes and n >= min_households
        )
        unused = sorted(c for c in set(codes) if c not in occ[year])
        print(
            f"{year}: {len(items)} items, {len(missing)} codes in the data but not printed, "
            f"{len(unused)} printed but not reported, {len(dup)} duplicated"
        )
        for c, n in missing:
            print(f"    in data, not printed: {c:06d} ({n} households)")
        for c in dup:
            print(f"    printed twice: {c:06d}")
        for c, n in invalid:
            print(f"    not an item code, ignored: {c} ({n} households)")
        bad += bool(missing or dup)
    return bad


def verify(corrections: list[Correction], extracted: Path, occurrence: Path) -> int:
    """Print the household evidence for each code-level correction; return
    the number that the raw data contradicts (a recode to a code nobody
    reports, a deleted or copied item that households do / do not report)."""
    occ = load_occurrence(occurrence)

    def n(year: int, code: str) -> int:
        return occ.get(year, {}).get(int(code), 0)

    bad = 0
    for c in corrections:
        if c.year not in occ:
            continue
        if c.action == "recode":
            ok = n(c.year, c.value) > 0
            print(
                f"{c.year} recode {c.expenditure_code} -> {c.value}: households "
                f"{n(c.year, c.expenditure_code)} -> {n(c.year, c.value)}"
                + ("" if ok else "  <-- not reported")
            )
        elif c.action == "delete":
            ok = n(c.year, c.expenditure_code) == 0
            print(
                f"{c.year} delete {c.expenditure_code}: {n(c.year, c.expenditure_code)} households"
                + ("" if ok else "  <-- reported")
            )
        elif c.action == "add_section":
            src = read_rows(extracted / f"questionnaire_{c.value}.csv")
            codes = [
                r["expenditure_code"] for r in src if r["section"] == c.description and r["kind"] == "item"
            ]
            deleted = {d.expenditure_code for d in corrections if d.year == c.year and d.action == "delete"}
            unreported = [x for x in codes if n(c.year, x) == 0 and x not in deleted]
            ok = not unreported
            print(
                f"{c.year} add section {c.description} from {c.value}: "
                + ", ".join(f"{x} ({n(c.year, x)})" for x in codes)
                + ("" if ok else f"  <-- not reported: {' '.join(unreported)}")
            )
        else:
            continue
        bad += not ok
    return bad


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Apply curated/ to output/1_extracted/ -> output/2_corrected/.")
    ap.add_argument("--extracted", type=Path, default=EXTRACTED)
    ap.add_argument("--out", type=Path, default=CORRECTED)
    ap.add_argument("--corrections", type=Path, default=CORRECTIONS)
    ap.add_argument("--check", action="store_true", help="compare with the household occurrence table")
    ap.add_argument("--labels", type=Path, default=LABELS)
    ap.add_argument("--occurrence", type=Path, default=OCCURRENCE)
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
        years = [y for y in SUPPORTED_YEARS if y >= 1383]
        print("\nEvidence for each correction (households reporting the code):")
        contradicted = verify(load_corrections(args.corrections), args.extracted, args.occurrence)
        print("\nCorrected questionnaires against the raw data:")
        failed = check(years, args.out, args.occurrence)
        raise SystemExit(1 if contradicted or failed else 0)


if __name__ == "__main__":
    main()
