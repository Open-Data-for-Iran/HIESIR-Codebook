"""Rebuild data/glyph_db.json from PDFs whose text extracts correctly."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .glyph_db import DB_PATH, build


def main() -> None:
    ap = argparse.ArgumentParser(
        prog="python -m hiesir_codebook.extraction.build_glyph_db", description=__doc__
    )
    ap.add_argument(
        "years",
        nargs="*",
        type=int,
        default=[1397, 1398, 1400, 1403],
        help="years with a correct ToUnicode map (default: 1397 1398 1400 1403)",
    )
    ap.add_argument("--data", type=Path, default=Path("data"), help="folder with pdf/ (default: data/)")
    args = ap.parse_args()
    db = build([args.data / "pdf" / f"Questionnaire {y}.pdf" for y in args.years])
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    DB_PATH.write_text(json.dumps(db, ensure_ascii=False, sort_keys=True, indent=0), encoding="utf-8")
    print(f"{len(db)} glyphs -> {DB_PATH}")


if __name__ == "__main__":
    main()
