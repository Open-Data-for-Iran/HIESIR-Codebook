"""Extract HBSIR (household budget survey) questionnaires from the PDF forms."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from .parse import Row, extract, extract_year

__all__ = ["extract", "extract_year", "main", "write_csv"]

# years whose PDF has a usable text layer (1363-1381 are scans; the 1401 PDF
# is a data dictionary, not the questionnaire)
SUPPORTED_YEARS = [1382, *range(1383, 1401), 1402, 1403]

# PDFs and occurrence CSVs (kept out of git)
DATA_DIR = Path("data")

CSV_COLUMNS = ["section", "kind", "level", "code", "sub", "expenditure_code", "description", "page"]


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
                ]
            )


def build(year: int, data: Path = DATA_DIR, csv_dir: Path = Path("extracted")) -> Path:
    """Extract one year's questionnaire and write ``<csv_dir>/questionnaire_<year>.csv``."""
    rows = extract_year(year, data)
    out = csv_dir / f"questionnaire_{year}.csv"
    write_csv(rows, out)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(prog="hbsir-questionnaire", description=__doc__)
    ap.add_argument("years", nargs="+", help="survey years (e.g. 1382 1403) or 'all'")
    ap.add_argument("--data", type=Path, default=DATA_DIR, help="folder with pdf/ (default: data/)")
    ap.add_argument(
        "--csv-dir",
        type=Path,
        default=Path("extracted"),
        help="where to write the CSV extracts (default: extracted/)",
    )
    args = ap.parse_args()
    years = SUPPORTED_YEARS if args.years == ["all"] else [int(y) for y in args.years]
    for y in years:
        print(build(y, args.data, args.csv_dir), flush=True)
