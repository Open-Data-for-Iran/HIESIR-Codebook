"""Check the extracted questionnaires against the codes that occur in the raw data.

It reads ``output/1_extracted/`` (which the regression test keeps equal to
what the PDFs extract to), so it needs the occurrence tables but not the PDFs.
``correct --check`` does the same for the corrected questionnaires.
"""

from __future__ import annotations

import csv
from pathlib import Path

from ..occurrence import load_occurrence, occurrence_files


def item_codes(csv_path: Path) -> set[int]:
    """The item codes of an extracted questionnaire, as numbers (011111 -> 11111)."""
    with open(csv_path, encoding="utf-8-sig") as f:
        return {int(r["expenditure_code"]) for r in csv.DictReader(f) if r["kind"] == "item"}


def compare_counts(codes: set[int], counts: dict[int, int]) -> dict[str, list[int]]:
    """Codes in the raw data but not extracted, and extracted codes never used.

    Codes are compared as numbers: the raw data drops the leading zero
    ('011111' -> 11111).
    """
    return {
        "in_data_not_pdf": sorted(counts.keys() - codes),
        "in_pdf_not_data": sorted(codes - counts.keys()),
    }


def main(years: list[int], extracted: Path, data: Path, verbose: bool = False) -> None:
    occ = load_occurrence(occurrence_files(data))
    for y in years:
        path = extracted / f"questionnaire_{y}.csv"
        codes = item_codes(path)
        cc = compare_counts(codes, occ.get(y, {}))
        print(
            f"{y}: items={len(codes)}"
            f" | data: not_in_pdf={len(cc['in_data_not_pdf'])} not_in_data={len(cc['in_pdf_not_data'])}",
            flush=True,
        )
        if verbose:
            for k, v in cc.items():
                if v:
                    print(f"   {k}: {v}")


if __name__ == "__main__":
    import argparse

    from .. import DATA_DIR, EXTRACTED, SUPPORTED_YEARS

    ap = argparse.ArgumentParser(prog="python -m hiesir_codebook.extraction.validate", description=__doc__)
    ap.add_argument("years", nargs="*", type=int, help="years to check (default: all supported)")
    ap.add_argument("-v", "--verbose", action="store_true", help="list the codes that differ")
    ap.add_argument("--extracted", type=Path, default=EXTRACTED, help="folder with the extracted CSVs")
    ap.add_argument("--data", type=Path, default=DATA_DIR, help="folder with the occurrence CSVs")
    args = ap.parse_args()
    main(args.years or SUPPORTED_YEARS, args.extracted, args.data, args.verbose)
