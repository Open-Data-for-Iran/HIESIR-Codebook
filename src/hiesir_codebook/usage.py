"""The code usage table: how much households used each code, year by year.

``data/code_usage.csv`` is in long format, one row per year and code
(1363-1403):

=====================  =========================================================
``year``               survey year
``expenditure_code``   the code as the raw data's ``Commodity_Code`` stores it,
                       a number without its leading zero (11111); ``011111``
                       reads the same
``occurrence``         households that reported the code that year
``expenditure_share``  the code's percent of that year's expenditure; may be
                       empty
=====================  =========================================================

:func:`read_usage` gives it as a typed polars table; :func:`load_occurrence`
and :func:`load_share` as ``{year: {code: value}}`` for lookups.  It is the
evidence for corrections and for the corrected codes (``correct --check``)
and for the changes between items (``changes``).

Some codes in the raw data are wrong: ``curated/data/code_corrections.csv``
(``year``, ``data_code`` as the data stores it, the ``expenditure_code`` it
stands for, ``reason``) lists them; an empty ``expenditure_code`` marks a
code that stands for no item (noise: a few households under a code the
questionnaire never printed).  :func:`correct_codes` moves their households to
the right code, or drops them; for now only the household checks of
``correct`` use it (1383 stores 023111 as 231, the group code 0231).
"""

from __future__ import annotations

from pathlib import Path

import polars as pl

from . import CURATED_DATA, DATA_DIR, csv_io

Occurrence = dict[int, dict[int, int]]  # {year: {code: households}}
Share = dict[int, dict[int, float]]  # {year: {code: percent of expenditure}}

SCHEMA = {
    "year": pl.Int64,
    "expenditure_code": pl.Int64,
    "occurrence": pl.Int64,
    "expenditure_share": pl.Float64,
}
COLUMNS = tuple(SCHEMA)
CODE_USAGE = DATA_DIR / "code_usage.csv"
CODE_CORRECTIONS = CURATED_DATA / "code_corrections.csv"


def read_usage(path: Path = CODE_USAGE) -> pl.DataFrame:
    """The table with its columns typed (an empty cell is null); a missing
    column, a value of the wrong type or a year and code twice is an error."""
    missing = [c for c in COLUMNS if c not in csv_io.columns(path)]
    if missing:
        raise ValueError(f"{path.name}: no column {', '.join(missing)} (expected {', '.join(COLUMNS)})")
    df = pl.read_csv(path, columns=list(COLUMNS), schema_overrides=SCHEMA).select(COLUMNS)
    twice = df.filter(pl.struct("year", "expenditure_code").is_duplicated())
    if not twice.is_empty():
        y, c = twice.row(0)[:2]
        raise ValueError(f"{path.name}: {len(twice)} rows repeat a year and code, e.g. {y} {c}")
    return df


def _nested(df: pl.DataFrame, column: str) -> dict:
    out: dict = {}
    for y, c, v in df.select("year", "expenditure_code", column).drop_nulls().iter_rows():
        out.setdefault(y, {})[c] = v
    return out


def load_occurrence(path: Path = CODE_USAGE) -> Occurrence:
    """{year: {code: households}}."""
    return _nested(read_usage(path), "occurrence")


def load_share(path: Path = CODE_USAGE) -> Share:
    """{year: {code: percent of expenditure}}."""
    return _nested(read_usage(path), "expenditure_share")


CodeCorrections = dict[int, dict[int, int | None]]  # {year: {code in the data: right code or None}}


def load_code_corrections(path: Path = CODE_CORRECTIONS) -> CodeCorrections:
    """{year: {code in the data: the code it stands for, None for noise}};
    none without the file."""
    if not path.exists():
        return {}
    out: CodeCorrections = {}
    for r in csv_io.read_frame(path).iter_rows(named=True):
        right = r["expenditure_code"].strip()
        out.setdefault(int(r["year"]), {})[int(r["data_code"])] = int(right) if right else None
    return out


def correct_codes(occ: Occurrence, corrections: CodeCorrections) -> Occurrence:
    """``occ`` with each wrong code's households added to the code it stands
    for, or dropped when it stands for none."""
    out = {y: dict(codes) for y, codes in occ.items()}
    for y, fixes in corrections.items():
        codes = out.get(y)
        if codes is None:
            continue
        for wrong, right in fixes.items():
            if wrong not in codes:
                continue
            n = codes.pop(wrong)
            if right is not None:
                codes[right] = codes.get(right, 0) + n
    return out
