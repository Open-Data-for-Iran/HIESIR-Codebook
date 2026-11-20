"""Extraction: the questionnaire PDFs -> ``output/1_extracted/`` (as printed).

``pdfs`` stages the PDFs, ``pdf_text`` reads their text layer (``glyph_db``
repairs broken fonts, rebuilt by ``build_glyph_db``), ``parse`` turns the lines
into rows and ``validate`` checks the codes against the raw data.
"""

from __future__ import annotations

import csv
from pathlib import Path

from .. import DATA_DIR, EXTRACTED
from .parse import Row, extract, extract_year

__all__ = ["CSV_COLUMNS", "Row", "build", "extract", "extract_year", "write_csv"]

CSV_COLUMNS = [
    "section",
    "kind",
    "level",
    "code",
    "sub",
    "expenditure_code",
    "description",
    "page",
    "top",
    "bottom",
    "left",
    "right",
]


def write_csv(rows: list[Row], path: Path) -> None:
    """One row per section / group header / item, in questionnaire order.

    The section rows carry the full PDF title in ``description``; ``page``
    is the 1-based PDF page.  UTF-8 with BOM so Excel shows Persian text.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, lineterminator="\n")  # LF: tracked data diffs cleanly on every OS
        w.writerow(CSV_COLUMNS)
        for r in rows:
            w.writerow(
                [
                    r.section,
                    r.kind,
                    r.level or "",
                    r.code,
                    r.sub or "",
                    r.expenditure_code or "",
                    r.desc,
                    r.page + 1,
                    "" if r.top is None else f"{r.top:.1f}",
                    "" if r.bottom is None else f"{r.bottom:.1f}",
                    "" if r.left is None else f"{r.left:.1f}",
                    "" if r.right is None else f"{r.right:.1f}",
                ]
            )


def build(year: int, data: Path = DATA_DIR, csv_dir: Path = EXTRACTED) -> Path:
    """Extract one year's questionnaire and write ``<csv_dir>/questionnaire_<year>.csv``."""
    rows = extract_year(year, data)
    out = csv_dir / f"questionnaire_{year}.csv"
    write_csv(rows, out)
    return out
