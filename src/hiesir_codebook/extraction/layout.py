"""The questionnaires' table layout and the print quirks of particular years.

What a new year may need changed lives here, not in ``parse.py``:

- :class:`Distances`: how far apart the parts of a table row may be, in
  points, with :data:`DISTANCES_BY_YEAR` for a year whose tables are drawn
  differently (none so far).  They are not relative to the font size: the
  12 pt text of 1382-1385 sits in table rows as tall as the 11 pt text of
  later years, and distances scaled by the font size pulled column headings
  into descriptions there ("(ریال)", "تهیه گرم کیلو").
- :data:`CELL_LABELS`: field labels printed inside description cells, which
  are not part of the description.
- :data:`QUIRKS`: the repairs ``parse.py`` makes for print quirks, with the
  years each is seen in.  Every repair it applies is listed in
  ``output/1_extracted/reports/report_<year>.csv``, and a test fails when one turns up in a
  year not listed here: look at the PDF there, then add the year (or fix the
  parser if the repair was wrong).
- :data:`LAST_OLD_SCHEME_YEAR`: the last year of the pre-COICOP code scheme.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..utils import parse_years

# 1382 and earlier use the pre-COICOP 3+2 digit code scheme
LAST_OLD_SCHEME_YEAR = 1382


@dataclass(frozen=True)
class Distances:
    """Distances in a table row, in points (the same in every year so far)."""

    row_rule: float = 14  # a table rule this close to a row's text is its border
    border: float = 15  # a wrapped description line ends this close to its column border
    wrap: float = 30  # a wrapped description line is this close to its code line
    code_column: float = 10  # ... and ends this far left of the code column
    tail_adjacent: float = 25  # a code list's continuation joins a code-only header this close
    tail_above: float = 30  # ... else the header this far above it
    head: float = 25  # the two lines of a header code list split around its text
    split_code: float = 20  # a sub-code line above its centred code
    table_width: float = 100  # vertical rules this far apart frame a table


DISTANCES = Distances()

# a year whose tables are drawn differently: Distances(wrap=..., ...)
DISTANCES_BY_YEAR: dict[int, Distances] = {}


def distances(year: int) -> Distances:
    return DISTANCES_BY_YEAR.get(year, DISTANCES)


# field labels inside description cells (1386-1403: the insurance and loan rows)
CELL_LABELS = ("تعداد افراد بیمه شده", "مبلغ وام", "محل اخذ وام", "محل اخذوام", "مبلغ رهن", "مبلغ رهن (ریال)")


def _years(spec: str) -> frozenset[int]:
    """'1384-1385 1390' -> {1384, 1385, 1390}; '' -> no year."""
    return parse_years(spec) or frozenset()


@dataclass(frozen=True)
class Quirk:
    note: str  # the reason in the extraction report
    years: frozenset[int]  # the years it is seen in


QUIRKS = {
    "stray_comma": Quirk(
        "repaired: a stray comma inside the code, read right to left (69 312,0 = 0312 69)",
        _years("1384-1385"),
    ),
    "code_tail": Quirk(
        "repaired: a header code list wrapped onto the next line (و01184), joined",
        _years("1386-1400 1402-1403"),
    ),
    "code_head": Quirk(
        "repaired: a header code list split around its text (06312 و / 06313 M), joined",
        _years("1383-1386 1391-1394"),
    ),
    "split_code": Quirk(
        "repaired: a sub-code printed above its code in a tall cell (13 / 0623), joined",
        _years("1391-1394"),
    ),
    "page_break": Quirk(
        "repaired: an item continued on the next page with its code repeated, joined",
        _years("1384-1385"),
    ),
    # never seen so far: a safeguard for a page whose heading is not text
    "image_heading": Quirk(
        "repaired: a section heading printed as an image, the section taken from the codes",
        _years(""),
    ),
    "source_note": Quirk(
        "left out: a note of the allowed source codes (3 یا 4)",
        _years("1382 1386-1400 1402-1403"),
    ),
    "cell_label": Quirk(
        "left out: a field label inside a description cell",
        _years("1386-1400 1402-1403"),
    ),
}
