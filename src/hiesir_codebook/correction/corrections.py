"""Correction step 1: the structure of each questionnaire.

``output/1_extracted/`` holds each questionnaire exactly as printed, typos
included.  ``curated/2_corrected/corrections.csv`` lists every deviation from
the print in codes, rows and sections, one row each, with the reason;
:func:`apply_corrections` applies them.  The descriptions are then styled by
:mod:`.rules` (step 2), fixed with hazm's word list by :mod:`.autocorrect`
(step 3) and spelled by :mod:`.spelling` (step 4).

Columns of ``corrections.csv``:

========== ===================================================================
year       questionnaire year
action     ``recode``: set the expenditure code of an item
           ``retext``: set the description of an item
           ``delete``: remove an item (and group headers left without items)
           ``add_section``: copy a section missing from the PDF from another
           year (``description`` = section number, ``value`` = source year)
           ``recode_header`` / ``retext_header``: set the code / description
           of a group header (its level follows the new code)
expenditure_code  the item's code as printed (for a header: its code as in
                  ``1_extracted``, e.g. ``062 M`` or ``01121, 01122``)
description       the item's description as printed (identifies the row
                  when a code is printed twice)
value      the corrected code or description (empty for ``delete``)
reason     why: evidence from neighbouring years, the raw data, ...
========== ===================================================================

The structure check (:func:`check_structure`) says what must hold in every
questionnaire CSV, from the CSV alone (no PDFs or raw data, so it runs
everywhere, in CI too):

================ ============================================================
kind             what it finds
================ ============================================================
duplicate        an expenditure code printed twice
sub_order        a sub-code not above the one before it in the same code
section_order    a section heading out of order or repeated, or a row whose
                 section is below the row before it
empty            a header or item with no description
bad_code         an item whose ``expenditure_code`` is not its code digits
                 followed by a two-digit ``sub``
outside_header   an item that its header's code does not cover (0631 31
                 under the header 06312), unless
                 ``curated/2_corrected/header_exceptions.csv`` accepts it as
                 printed
================ ============================================================

The corrected questionnaires (``output/2_corrected/``) must have none: a test
checks it.  In ``output/1_extracted/`` the findings are the print errors that
``corrections.csv`` fixes (1386: 041211-041213 and 073611 printed twice, the
header 062 M; 1384: 102216), which a test checks too.

Against the household occurrence tables (``data/commodity_code_occurrence_*.csv``),
:func:`verify` gives the evidence for each correction and
:func:`check_occurrence` the codes that households report but the
questionnaire lacks, or the reverse (``correct --check``).
"""

from __future__ import annotations

import argparse
import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path

from .. import CORRECTED, CURATED_CORRECTED, SUPPORTED_YEARS, csv_io
from ..extraction.parse import LAST_OLD_SCHEME_YEAR, header_level
from ..occurrence import load_occurrence
from ..utils import collapse_whitespace, parse_years

CORRECTIONS = CURATED_CORRECTED / "corrections.csv"
HEADER_EXCEPTIONS = CURATED_CORRECTED / "header_exceptions.csv"
ACTIONS = ("recode", "retext", "delete", "add_section", "recode_header", "retext_header")


# --- corrections.csv -----------------------------------------------------------


@dataclass
class Correction:
    year: int
    action: str
    expenditure_code: str
    description: str
    value: str
    reason: str


def load_corrections(path: Path = CORRECTIONS) -> list[Correction]:
    out = [
        Correction(
            int(r["year"]),
            r["action"],
            r["expenditure_code"],
            r["description"],
            r["value"],
            r["reason"],
        )
        for r in csv_io.read(path)
    ]
    for c in out:
        if c.action not in ACTIONS:
            raise ValueError(f"unknown action {c.action!r} in {path}")
        if not c.reason.strip():
            raise ValueError(f"correction without a reason: {c}")
    return out


def _find(rows: list[dict[str, str]], c: Correction) -> dict[str, str]:
    header = c.action.endswith("_header")
    hits = [
        r
        for r in rows
        if r["kind"] == ("header" if header else "item")
        and r["code" if header else "expenditure_code"] == c.expenditure_code
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


def apply_corrections(
    year: int, rows: list[dict[str, str]], corrections: list[Correction], extracted: Path
) -> list[dict[str, str]]:
    """The rows of one questionnaire with that year's corrections applied
    (a copy: ``rows`` stay as they are)."""
    rows = [dict(r) for r in rows]
    for c in corrections:
        if c.year != year:
            continue
        if c.action == "recode":
            r = _find(rows, c)
            r["expenditure_code"], r["code"], r["sub"] = c.value, c.value[:-2], c.value[-2:]
        elif c.action in ("retext", "retext_header"):
            _find(rows, c)["description"] = c.value
        elif c.action == "recode_header":
            r = _find(rows, c)
            r["code"], r["level"] = c.value, str(header_level(c.value, year <= LAST_OLD_SCHEME_YEAR))
        elif c.action == "delete":
            gone = _find(rows, c)
            rows = [r for r in rows if r is not gone]
            rows = [r for r in rows if not _orphan_header(r, gone, rows)]
        elif c.action == "add_section":
            section = c.description
            if any(r["section"] == section for r in rows):
                raise ValueError(f"{year}: section {section} already present")
            src = [
                r for r in csv_io.read(extracted / f"questionnaire_{c.value}.csv") if r["section"] == section
            ]
            added = [{**r, "page": "", "top": "", "bottom": "", "left": "", "right": ""} for r in src]
            at = next((i for i, r in enumerate(rows) if int(r["section"]) > int(section)), len(rows))
            rows[at:at] = added
    return rows


# --- the structure check and header_exceptions.csv ----------------------------


@dataclass(frozen=True)
class Finding:
    year: int
    kind: str
    code: str
    detail: str


@dataclass(frozen=True)
class HeaderException:
    header: str  # the header's code as in the CSV ("01192, 01193")
    item_code: str  # the item's code as in the CSV ("0119")
    years: frozenset[int] | None  # None: every year
    reason: str


def load_header_exceptions(path: Path = HEADER_EXCEPTIONS) -> list[HeaderException]:
    if not path.exists():
        return []
    return [
        HeaderException(r["header"].strip(), r["item_code"].strip(), parse_years(r["years"]), r["reason"])
        for r in csv_io.read(path)
    ]


def _digits(code: str) -> str:
    return re.sub(r"\D", "", code)


def check_rows(
    year: int,
    rows: list[dict[str, str]],
    exceptions: list[HeaderException],
    used: set[HeaderException] | None = None,
) -> list[Finding]:
    """The structure findings of one questionnaire (rows as read from its CSV).
    The header exceptions that accepted something are added to ``used``."""
    out: list[Finding] = []
    items = [r for r in rows if r["kind"] == "item"]

    for code, n in Counter(r["expenditure_code"] for r in items).items():
        if n > 1:
            out.append(Finding(year, "duplicate", code, f"printed {n} times"))

    for a, b in pairwise(items):
        same = (a["section"], a["code"]) == (b["section"], b["code"])
        if same and b["sub"].isdigit() and a["sub"].isdigit() and int(b["sub"]) <= int(a["sub"]):
            out.append(Finding(year, "sub_order", b["expenditure_code"], f"after {a['expenditure_code']}"))

    headings = [int(r["section"]) for r in rows if r["kind"] == "section"]
    if headings != sorted(set(headings)):
        out.append(Finding(year, "section_order", "", f"section headings {headings}"))
    for a, b in pairwise(rows):
        if int(b["section"]) < int(a["section"]):
            out.append(
                Finding(year, "section_order", b["expenditure_code"] or b["code"], "below the row before")
            )

    for r in rows:
        if r["kind"] != "section" and not r["description"].strip():
            out.append(
                Finding(year, "empty", r["expenditure_code"] or r["code"], f"{r['kind']} with no text")
            )

    for r in items:
        if not re.fullmatch(r"\d{2}", r["sub"]) or r["expenditure_code"] != _digits(r["code"]) + r["sub"]:
            out.append(
                Finding(year, "bad_code", r["expenditure_code"], f"code {r['code']!r} sub {r['sub']!r}")
            )

    def accepted(header: str, item_code: str) -> bool:
        for e in exceptions:
            if e.header == header and e.item_code == item_code and (e.years is None or year in e.years):
                if used is not None:
                    used.add(e)
                return True
        return False

    header: dict[str, str] | None = None
    for r in rows:
        if r["kind"] == "section":
            header = None
        elif r["kind"] == "header":
            header = r
        elif header is not None:
            covers = [_digits(c) for c in header["code"].split(",")]
            if not any(r["expenditure_code"].startswith(c) for c in covers) and not accepted(
                header["code"], r["code"]
            ):
                out.append(
                    Finding(year, "outside_header", r["expenditure_code"], f"under header {header['code']}")
                )
    return out


def check_structure(
    years: list[int],
    folder: Path,
    exceptions: list[HeaderException] | None = None,
    used: set[HeaderException] | None = None,
) -> list[Finding]:
    """The findings of every year's ``questionnaire_<year>.csv`` in ``folder``."""
    exc = load_header_exceptions() if exceptions is None else exceptions
    return [
        f for y in years for f in check_rows(y, csv_io.read(folder / f"questionnaire_{y}.csv"), exc, used)
    ]


# --- against the raw data --------------------------------------------------------


def check_occurrence(
    years: Iterable[int], corrected: Path, occurrence: Path | list[Path], min_households: int = 5
) -> int:
    """Print codes that disagree with the raw data; return the number of
    years with a code reported by households but missing from the
    questionnaire (the strong signal of a typo or an extraction miss)."""
    occ = load_occurrence(occurrence)
    bad = 0
    for year in years:
        if year not in occ:
            continue
        items = [r for r in csv_io.read(corrected / f"questionnaire_{year}.csv") if r["kind"] == "item"]
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


def verify(corrections: list[Correction], extracted: Path, occurrence: Path | list[Path]) -> int:
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
            src = csv_io.read(extracted / f"questionnaire_{c.value}.csv")
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


def main(argv: list[str] | None = None) -> int:
    """The structure check of a folder of questionnaire CSVs."""
    ap = argparse.ArgumentParser(
        prog="python -m hiesir_codebook.correction.corrections",
        description="Structure check: what must hold in every questionnaire CSV, from the CSV alone.",
    )
    ap.add_argument(
        "folder", nargs="?", type=Path, default=CORRECTED, help=f"default: {CORRECTED.as_posix()}/"
    )
    ap.add_argument("--exceptions", type=Path, default=HEADER_EXCEPTIONS)
    args = ap.parse_args(argv)
    exceptions = load_header_exceptions(args.exceptions)
    used: set[HeaderException] = set()
    findings = check_structure(SUPPORTED_YEARS, args.folder, exceptions, used)
    for f in findings:
        print(f"    {f.year} {f.kind:14} {f.code:8} {f.detail}")
    stale = [e for e in exceptions if e not in used]
    for e in stale:
        print(f"    header exception that accepts nothing: {e.header} / {e.item_code}")
    print(
        f"structure check of {args.folder.as_posix()}: {len(findings)} findings"
        f" ({len(exceptions)} accepted header exceptions, {len(stale)} stale)"
    )
    return 1 if findings or stale else 0


if __name__ == "__main__":
    raise SystemExit(main())
