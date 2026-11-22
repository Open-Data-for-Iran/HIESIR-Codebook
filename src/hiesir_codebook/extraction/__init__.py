"""Extraction: the questionnaire PDFs -> ``output/1_extracted/`` (as printed).

``pdfs`` lists, checks and downloads the PDFs, ``pdf_text`` reads their text
layer (``glyph_db`` repairs broken fonts, rebuilt by ``build_glyph_db``),
``parse`` turns the lines into rows, with the layout and the print quirks of
particular years in ``layout``.

For each ``questionnaire_<year>.csv``, ``reports/report_<year>.csv`` lists what
the extraction left out, the glyphs it could not read and the print quirks it
repaired, for review; both are tracked, so a change shows in the diff.
"""

from __future__ import annotations

from pathlib import Path

from .. import DATA_DIR, EXTRACTED, csv_io
from .parse import Row, extract, extract_year
from .pdf_text import Note, Notes

__all__ = [
    "CSV_COLUMNS",
    "Note",
    "Notes",
    "Row",
    "build",
    "extract",
    "extract_year",
    "write_csv",
    "write_report",
]

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
    with csv_io.writer(path, CSV_COLUMNS) as w:
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


REPORT_COLUMNS = ["page", "y", "reason", "text", "count", "pages"]


def _page_ranges(pages: list[int]) -> str:
    """[3, 4, 5, 9] -> '3-5 9'."""
    out: list[list[int]] = []
    for p in sorted(set(pages)):
        if out and p == out[-1][1] + 1:
            out[-1][1] = p
        else:
            out.append([p, p])
    return " ".join(str(a) if a == b else f"{a}-{b}" for a, b in out)


def write_report(notes: list[Note], path: Path) -> None:
    """The extraction report, one row per reason and text, in the order first
    met (``page`` and ``y`` where): a table heading repeated on every page is
    one row.  ``count`` is how often it happened (for unreadable glyphs, how
    many glyphs), ``pages`` on which pages.  Pages are 1-based, as in the
    questionnaire CSV."""
    groups: dict[tuple[str, str], list[Note]] = {}
    for n in notes:
        groups.setdefault((n.reason, n.text), []).append(n)
    with csv_io.writer(path, REPORT_COLUMNS) as w:
        for (reason, text), ds in groups.items():
            first = ds[0]
            w.writerow(
                [
                    first.page + 1,
                    "" if first.y is None else f"{first.y:.1f}",
                    reason,
                    text,
                    sum(d.count for d in ds),
                    _page_ranges([d.page + 1 for d in ds]),
                ]
            )


def build(year: int, data: Path = DATA_DIR, csv_dir: Path = EXTRACTED) -> Path:
    """Extract one year's questionnaire to ``<csv_dir>/questionnaire_<year>.csv``
    and its report to ``<csv_dir>/reports/report_<year>.csv``."""
    notes = Notes()
    rows = extract_year(year, data, notes)
    out = csv_dir / f"questionnaire_{year}.csv"
    write_csv(rows, out)
    write_report(notes.items, csv_dir / "reports" / f"report_{year}.csv")
    return out
