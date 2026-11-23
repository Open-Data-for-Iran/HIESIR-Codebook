"""Rebuild extraction/data/glyph_db.json from PDFs whose text extracts correctly."""

from __future__ import annotations

import json
from pathlib import Path

from .glyph_db import DB_PATH, build
from .parse import pdf_path


def main(years: list[int] | None = None, *, data: Path = Path("data")) -> None:
    """Rebuild extraction/data/glyph_db.json from PDFs whose text extracts correctly.

    Parameters
    ----------
    years
        Years with a correct ToUnicode map (default: 1387 1397 1398 1400 1403).
    data
        The folder with pdf/.
    """
    db = build([pdf_path(y, data) for y in years or [1387, 1397, 1398, 1400, 1403]])
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    DB_PATH.write_text(
        json.dumps(db, ensure_ascii=False, sort_keys=True, indent=0), encoding="utf-8", newline="\n"
    )
    print(f"{len(db)} glyphs -> {DB_PATH}")
