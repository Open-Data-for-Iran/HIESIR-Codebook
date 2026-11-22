"""The household occurrence tables: how many households reported each code.

``data/commodity_code_occurrence_1363-1382.csv`` and ``..._1383-1403.csv``
have one row per ``Commodity_Code`` (the expenditure code as a number,
without its leading zero: 11111) and one column per year.  They are the
evidence for corrections and for the corrected codes (``correct --check``)
and for links between items (``relations``).
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from . import DATA_DIR, csv_io

Occurrence = dict[int, dict[int, int]]  # {year: {code: households}}

OCCURRENCE = DATA_DIR / "commodity_code_occurrence_1383-1403.csv"  # the COICOP years


def occurrence_files(data: Path = DATA_DIR) -> list[Path]:
    """Both tables (1363-1382 and 1383-1403) in ``data``."""
    return sorted(data.glob("commodity_code_occurrence_*.csv"))


def load_occurrence(paths: Path | Iterable[Path] = OCCURRENCE) -> Occurrence:
    """{year: {code: households}} from one table or several (later ones win)."""
    out: Occurrence = {}
    for path in [paths] if isinstance(paths, Path) else paths:
        for r in csv_io.read(path):
            code = int(r["Commodity_Code"])
            for k, v in r.items():
                if k != "Commodity_Code" and v:
                    out.setdefault(int(k), {})[code] = int(float(v))
    return out
