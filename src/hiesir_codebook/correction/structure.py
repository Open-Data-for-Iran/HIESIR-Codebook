"""Structure check: what must hold in every questionnaire CSV, from the CSV alone.

No PDFs or raw data needed, so it runs everywhere (and in CI).  For each year:

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
"""

from __future__ import annotations

import argparse
import csv
import re
from collections import Counter
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path

from .. import CORRECTED, CURATED_CORRECTED, SUPPORTED_YEARS
from ..utils import parse_years
from .correct import read_rows

HEADER_EXCEPTIONS = CURATED_CORRECTED / "header_exceptions.csv"


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
    with open(path, encoding="utf-8-sig") as f:
        return [
            HeaderException(r["header"].strip(), r["item_code"].strip(), parse_years(r["years"]), r["reason"])
            for r in csv.DictReader(f)
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


def check(
    years: list[int],
    folder: Path,
    exceptions: list[HeaderException] | None = None,
    used: set[HeaderException] | None = None,
) -> list[Finding]:
    """The findings of every year's ``questionnaire_<year>.csv`` in ``folder``."""
    exc = load_header_exceptions() if exceptions is None else exceptions
    return [f for y in years for f in check_rows(y, read_rows(folder / f"questionnaire_{y}.csv"), exc, used)]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m hiesir_codebook.correction.structure", description=__doc__.split("\n")[0]
    )
    ap.add_argument(
        "folder", nargs="?", type=Path, default=CORRECTED, help=f"default: {CORRECTED.as_posix()}/"
    )
    ap.add_argument("--exceptions", type=Path, default=HEADER_EXCEPTIONS)
    args = ap.parse_args(argv)
    exceptions = load_header_exceptions(args.exceptions)
    used: set[HeaderException] = set()
    findings = check(SUPPORTED_YEARS, args.folder, exceptions, used)
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
