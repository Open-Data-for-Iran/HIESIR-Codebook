"""Reading and writing the project's CSV files, all in one way.

Every CSV is written as UTF-8 with a BOM, so Excel shows the Persian text,
and with LF line endings, so the tracked files diff alike on every OS.
Reading skips a BOM when there is one, and every field stays a string: a
code keeps its leading zeros (``011111``) and an empty cell stays ``""``.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path

import polars as pl

ENCODING = "utf-8-sig"


def read(path: Path) -> list[dict[str, str]]:
    """Every row of ``path``, as a dict from column name to text."""
    with open(path, encoding=ENCODING, newline="") as f:
        return list(csv.DictReader(f))


def columns(path: Path) -> list[str]:
    """The column names of ``path`` (its first row)."""
    with open(path, encoding=ENCODING, newline="") as f:
        return next(csv.reader(f), [])


@contextmanager
def writer(path: Path, header: Sequence[str], bom: bool = True) -> Iterator[csv.writer]:
    """A ``csv.writer`` on ``path`` with ``header`` already written; the
    folder is created if needed.  ``bom`` False writes plain UTF-8."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding=ENCODING if bom else "utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        yield w


def read_frame(path: Path) -> pl.DataFrame:
    """``path`` as a polars table, every column text, an empty cell ``""``."""
    return pl.read_csv(path, infer_schema=False, empty_string_is_null=False)


def write_frame(df: pl.DataFrame, path: Path) -> None:
    """Write ``df`` as :func:`write` would: a BOM, LF line endings, quotes
    only where needed; the folder is created if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    # polars quotes "" to tell it from a missing value; the csv module writes both bare
    df = df.with_columns(
        pl.when(pl.col(c) != "").then(c).alias(c) for c, t in df.schema.items() if t == pl.String
    )
    df.write_csv(path, include_bom=True, line_terminator="\n", quote_style="necessary")


def write(path: Path, header: Sequence[str], rows: Iterable[Mapping[str, object]], bom: bool = True) -> None:
    """Write dict rows to ``path`` in the order of ``header``; a key not in
    ``header`` is an error, a missing one an empty cell."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding=ENCODING if bom else "utf-8", newline="") as f:
        w = csv.DictWriter(f, header, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
