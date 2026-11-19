"""Check extracted questionnaires against the codes that occur in the raw data."""

from __future__ import annotations

import csv
from pathlib import Path

from .parse import Row, extract_year


def load_counts(csv_paths: list[Path], year: int) -> dict[int, int]:
    """Occurrences per code in the raw data, keyed by the numeric code (11111)."""
    counts: dict[int, int] = {}
    for p in csv_paths:
        with open(p, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            if str(year) not in (reader.fieldnames or []):
                continue
            for rec in reader:
                v = rec[str(year)]
                if v:
                    counts[int(rec["Commodity_Code"])] = int(float(v))
    return counts


def compare_counts(rows: list[Row], counts: dict[int, int]) -> dict[str, list[int]]:
    """Codes in the raw data but not extracted, and extracted codes never used.

    Codes are compared as numbers: the raw data drops the leading zero
    ('011111' -> 11111).
    """
    keys = {int(r.expenditure_code) for r in rows if r.kind == "item" and r.expenditure_code}
    return {
        "in_data_not_pdf": sorted(counts.keys() - keys),
        "in_pdf_not_data": sorted(keys - counts.keys()),
    }


def main(years: list[int], data: Path = Path("data"), verbose: bool = False) -> None:
    csvs = sorted(data.glob("commodity_code_occurrence_*.csv"))
    for y in years:
        rows = extract_year(y, data)
        n = {k: sum(r.kind == k for r in rows) for k in ("section", "header", "item")}
        cc = compare_counts(rows, load_counts(csvs, y))
        print(
            f"{y}: sections={n['section']} headers={n['header']} items={n['item']}"
            f" | data: not_in_pdf={len(cc['in_data_not_pdf'])} not_in_data={len(cc['in_pdf_not_data'])}",
            flush=True,
        )
        if verbose:
            for k, v in cc.items():
                if v:
                    print(f"   {k}: {v}")


if __name__ == "__main__":
    import argparse

    from . import DATA_DIR, SUPPORTED_YEARS

    ap = argparse.ArgumentParser(prog="python -m hiesir_codebook.validate", description=__doc__)
    ap.add_argument("years", nargs="*", type=int, help="years to check (default: all supported)")
    ap.add_argument("-v", "--verbose", action="store_true", help="list the codes that differ")
    ap.add_argument("--data", type=Path, default=DATA_DIR, help="folder with pdf/ and the occurrence CSVs")
    args = ap.parse_args()
    main(args.years or SUPPORTED_YEARS, args.data, args.verbose)
