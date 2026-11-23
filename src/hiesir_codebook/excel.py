"""The corrected questionnaires as Excel workbooks, for a GitHub release.

One workbook per year, ``dist/excel/questionnaire_<year>.xlsx``, written from
``output/2_corrected/questionnaire_<year>.csv`` and nothing else, so a
workbook never says anything the tracked CSV does not:

=================  ==========================================================
sheet              what it holds
=================  ==========================================================
``About``          what the file is, its figures, its sections (each a link
                   to its first row), and what every column means
``Questionnaire``  every row of the CSV in the order of the form: sections,
                   group headers and items, shaded and indented by level,
                   with an outline to fold the groups
``Items``          the items only, one per row, each with its section and
                   its group headers at levels 2-4, and the code as the
                   number the raw data stores
=================  ==========================================================

The header is the first row of both data sheets and the columns keep their
CSV names, so ``pandas.read_excel(path, sheet_name="Items", dtype=str)``
gives a table at once.  Codes are written as text: they keep their leading
zero.  The workbooks are not tracked (``dist/`` is ignored): they are made
from ``output/`` whenever a release needs them.

    uv run hiesir-codebook excel 1403
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import polars as pl

from . import CORRECTED, SUPPORTED_YEARS, csv_io

EXCEL = Path("dist") / "excel"
SITE = "https://open-data-for-iran.github.io/HIESIR-Codebook/"
REPOSITORY = "https://github.com/Open-Data-for-Iran/HIESIR-Codebook"

FONT = "Segoe UI"
INK = "#1B2A41"  # text
NAVY = "#1F3A5F"  # section bands, header rows
MUTED = "#5B6B7F"  # secondary text
RULE = "#D5DCE5"  # the lines between rows
LINK = "#1F5FA8"
BAND = "#EEF2F7"  # every other row of the Items sheet
# the fill of a row of the questionnaire, by level: a section (1) down to an item (5);
# a level 4 header is bold on white, its indent tells it from level 3
FILLS = {1: NAVY, 2: "#C5D5E8", 3: "#E3EBF5", 4: "#FFFFFF", 5: "#FFFFFF"}

# (column, width, how its cells are set: "code" monospace, from the start of
# the cell; "word" centred; "long" wrapped and indented by level; "line" one
# line, cut at the edge of its cell; "number" a centred number).  Tables read
# left to right and their text is set from the left, Persian included.
QUESTIONNAIRE = [
    ("code", 20, "code"),
    ("sub", 9, "code"),
    ("expenditure_code", 20, "code"),
    ("description", 78, "long"),
    ("kind", 11, "word"),
    ("level", 11, "number"),
    ("section", 11, "number"),
    ("page", 11, "number"),
]
# the item, then the groups it is printed under from the nearest out
ITEMS = [
    ("expenditure_code", 20, "code"),
    ("commodity_code", 19, "number"),
    ("description", 48, "long"),
    ("page", 11, "number"),
    ("level_4_code", 22, "code"),
    ("level_4", 34, "line"),
    ("level_3_code", 16, "code"),
    ("level_3", 38, "line"),
    ("level_2_code", 14, "code"),
    ("level_2", 34, "line"),
    ("section", 11, "number"),
    ("section_title", 46, "line"),
]
PRINTED_ITEMS = 4  # the Items sheet prints its first columns only: the item and its page
# what the About sheet says of each column: (column, sheet, English, Persian)
COLUMNS = [
    ("section", "both", "Section (بخش) number of the form", "شماره بخش پرسشنامه"),
    ("kind", "Questionnaire", "section, header (a group row) or item", "نوع سطر: بخش، سرگروه یا قلم"),
    (
        "level",
        "Questionnaire",
        "2–4 for group headers, 5 for items",
        "سطح: ۲ تا ۴ برای سرگروه‌ها، ۵ برای اقلام",
    ),
    ("code", "Questionnaire", "Code as printed: 0111, 091 A, 01111, 01112", "کد، همان‌گونه که چاپ شده است"),
    ("sub", "Questionnaire", "Two-digit item sub-code", "کد دو رقمی قلم"),
    (
        "expenditure_code",
        "both",
        "Full code of an item: code + sub (0111 + 11 → 011111), as text",
        "کد کامل قلم: کد گروه و کد قلم پشت سر هم، به صورت متن",
    ),
    (
        "commodity_code",
        "Items",
        "The same code as a number, as the raw data stores it (11111)",
        "همان کد به صورت عدد، مانند داده‌های خام",
    ),
    ("description", "both", "Corrected description of the row", "شرح اصلاح‌شده سطر"),
    ("section_title", "Items", "Full title of the item's section", "عنوان کامل بخش"),
    (
        "level_2 … level_4",
        "Items",
        "The group headers the item is printed under, with their codes; "
        "a header printed with two codes has both (01111, 01112)",
        "سرگروه‌هایی که قلم زیر آن‌ها چاپ شده است، با کد هر یک",
    ),
    ("page", "both", "Page of the PDF form (1-based)", "شماره صفحه در فایل PDF پرسشنامه"),
]


def read_year(year: int, source: Path = CORRECTED) -> pl.DataFrame:
    """The corrected questionnaire of ``year``, every column text."""
    return csv_io.read_frame(source / f"questionnaire_{year}.csv")


def items_table(rows: pl.DataFrame) -> list[dict[str, Any]]:
    """The items of a questionnaire, each with the section and the group
    headers it is printed under: a header holds until the next one of its
    level or of a level above it."""
    out: list[dict[str, Any]] = []
    title = ""
    groups: dict[int, tuple[str, str]] = {}
    for r in rows.iter_rows(named=True):
        if r["kind"] == "section":
            title, groups = r["description"], {}
        elif r["kind"] == "header":
            level = int(r["level"])
            groups = {k: v for k, v in groups.items() if k < level} | {level: (r["code"], r["description"])}
        else:
            item = {
                "expenditure_code": r["expenditure_code"],
                "commodity_code": int(r["expenditure_code"]),
                "description": r["description"],
                "section": int(r["section"]),
                "section_title": title,
                "page": r["page"],  # empty where the form gives none (1383, section 2)
            }
            for level in (2, 3, 4):
                item[f"level_{level}_code"], item[f"level_{level}"] = groups.get(level, ("", ""))
            out.append(item)
    return out


# Persian in 10 pt Segoe UI fits about this many letters in one unit of column
# width (the width of a "0" in the default font): measured on the Items
# sheet, where a 70-wide cell breaks after 76-78 letters.  Kept low: a row a
# little too tall is better than one that cuts its last line.
LETTERS_PER_UNIT = 1.05


def _height(cells: list[tuple[str, float]], line: float = 18.0) -> float:
    """The height of a row whose wrapped cells are ``(text, column width)``:
    Excel does not fit a row to its text until someone edits it."""
    lines = max(
        (math.ceil(len(text) / (width * LETTERS_PER_UNIT)) for text, width in cells if text), default=1
    )
    return line * max(lines, 1) + 4


def _indent(level: int) -> int:
    """The indent of a description, by level: two steps a level from level 2."""
    return 2 * max(level - 2, 0)


class _Formats:
    """The cell formats of a workbook, made once each."""

    def __init__(self, book: Any) -> None:
        self.book = book
        self.made: dict[tuple, Any] = {}

    def __call__(self, **props: Any) -> Any:
        key = tuple(sorted(props.items()))
        if key not in self.made:
            base = {"font_name": FONT, "font_size": 10, "font_color": INK, "valign": "vcenter"}
            self.made[key] = self.book.add_format(base | props)
        return self.made[key]

    def header(self) -> Any:
        """A header row cell: set from the left, clear of the filter button at
        the right of the cell."""
        return self(bold=True, font_color="#FFFFFF", bg_color=NAVY, align="left", indent=1, border=0)

    def cell(self, how: str, level: int = 5, banded: bool = False) -> Any:
        """A data cell: ``level`` shades and weights a row of the questionnaire."""
        props: dict[str, Any] = {"bottom": 1, "bottom_color": RULE}
        if level == 1:
            # a white line above keeps the first section apart from the header row
            props |= {"bold": True, "font_color": "#FFFFFF", "bg_color": NAVY, "font_size": 11}
            props |= {"top": 2, "top_color": "#FFFFFF"}
        elif level < 5:
            # a header's description and code are bold, not its numbers
            props |= {"bold": how in ("long", "line", "code"), "bg_color": FILLS[level]}
        elif banded:
            props |= {"bg_color": BAND}
        if how in ("long", "line"):
            # set from the left like the rest of the table; reading order 2 keeps
            # the Persian right to left, whatever its first character is
            props |= {"align": "left", "reading_order": 2, "indent": 1 + _indent(level)}
            props |= {"text_wrap": how == "long"}
        elif how == "code":
            # codes from their first digit, so 011, 0111 and 01111 line up
            props |= {"align": "left", "indent": 1, "num_format": "@", "font_name": "Consolas"}
        elif how == "word":
            props |= {"align": "left", "indent": 1}
        else:
            props |= {"align": "center"}
        return self(**props)


def _sheet(book: Any, name: str, columns: list[tuple[str, int, str]], fmt: _Formats, rows: int) -> Any:
    """A data sheet: its header row frozen and filtered, set to print on A4."""
    ws = book.add_worksheet(name)
    ws.hide_gridlines(2)
    ws.set_row(0, 30)
    for i, (column, width, _) in enumerate(columns):
        ws.set_column(i, i, width)
        ws.write_string(0, i, column, fmt.header())
    ws.freeze_panes(1, 0)
    ws.autofilter(0, 0, rows, len(columns) - 1)
    # a code is text on purpose: no green corner on every cell
    ws.ignore_errors({"number_stored_as_text": f"A1:{chr(64 + len(columns))}{rows + 1}"})
    ws.set_landscape()
    ws.set_paper(9)  # A4
    ws.fit_to_pages(1, 0)
    ws.repeat_rows(0)
    ws.set_footer(f"&L&8{name}&C&8&P / &N")
    return ws


def _write(ws: Any, row: int, columns: list[tuple[str, int, str]], values: dict[str, Any], fmt: Any) -> None:
    for i, (column, _, how) in enumerate(columns):
        value = values.get(column)
        if value is None or value == "":
            ws.write_blank(row, i, None, fmt(how))
        elif how == "number":
            ws.write_number(row, i, int(value), fmt(how))
        else:
            ws.write_string(row, i, str(value), fmt(how))


def _questionnaire(book: Any, fmt: _Formats, rows: pl.DataFrame) -> dict[str, int]:
    """The Questionnaire sheet; returns the sheet row (1-based) of each section."""
    ws = _sheet(book, "Questionnaire", QUESTIONNAIRE, fmt, rows.height)
    ws.outline_settings(symbols_below=False)  # a header is above the rows it folds
    width = {c: w for c, w, _ in QUESTIONNAIRE}["description"]
    sections: dict[str, int] = {}
    for n, r in enumerate(rows.iter_rows(named=True), start=1):
        level = 1 if r["kind"] == "section" else int(r["level"])
        if level == 1:
            sections[r["section"]] = n + 1
        # an indent step is about one unit of column width
        ws.set_row(n, _height([(r["description"], width - _indent(level))]), None, {"level": level - 1})
        _write(ws, n, QUESTIONNAIRE, r, lambda how, level=level: fmt.cell(how, level))
    return sections


def _items(book: Any, fmt: _Formats, items: list[dict[str, Any]]) -> None:
    """The Items sheet: a lookup table, so only the description wraps; the
    titles of the groups and the section are cut at the edge of their cell
    (they are whole in the formula bar)."""
    ws = _sheet(book, "Items", ITEMS, fmt, len(items))
    ws.freeze_panes(1, 3)  # the code and the description stay while the groups scroll
    # on paper all twelve columns would be too small to read
    ws.print_area(0, 0, len(items), PRINTED_ITEMS - 1)
    ws.set_portrait()
    width = {c: w for c, w, _ in ITEMS}["description"]
    for n, item in enumerate(items, start=1):
        ws.set_row(n, _height([(item["description"], width)]))
        _write(ws, n, ITEMS, item, lambda how, banded=n % 2 == 0: fmt.cell(how, banded=banded))


def _about(ws: Any, fmt: _Formats, year: int, rows: pl.DataFrame, sections: dict[str, int]) -> None:
    """The About sheet, left to right: B-D hold the text and the tables, E the
    page of a section, E-F (merged) the Persian of a column."""
    ws.hide_gridlines(2)
    for column, width in enumerate((3, 22, 16, 62, 12, 50)):
        ws.set_column(column, column, width)
    last = 5
    label = fmt(bold=True, font_color=MUTED)
    text = fmt(text_wrap=True, valign="top")
    heading = fmt(bold=True, font_size=12, font_color=NAVY)
    head = fmt(bold=True, font_color="#FFFFFF", bg_color=NAVY, align="left", indent=1)
    ruled = {"bottom": 1, "bottom_color": RULE}
    line = fmt(**ruled, text_wrap=True, indent=1)
    line_fa = fmt(**ruled, text_wrap=True, align="left", reading_order=2, indent=1)
    mono = fmt(**ruled, font_name="Consolas", bold=True, indent=1)
    centred = fmt(**ruled, align="center")  # numbers
    word = fmt(**ruled, align="left", indent=1)
    link = fmt(font_color=LINK, underline=1, valign="top")

    ws.set_row(1, 34)
    ws.merge_range(1, 1, 1, last, f"Questionnaire {year}", fmt(bold=True, font_size=20, font_color=NAVY))
    ws.set_row(2, 24)
    ws.merge_range(
        2,
        1,
        2,
        last,
        f"اقلام هزینه پرسشنامه هزینه و درآمد خانوار، سال {year}",
        fmt(font_size=13, font_color=MUTED, reading_order=2, align="left"),
    )
    ws.set_row(4, 48)
    ws.merge_range(
        4,
        1,
        4,
        last,
        "The expenditure items of the Household Income and Expenditure Survey of Iran (HIES) "
        f"questionnaire of {year}: extracted from the PDF form of the Statistical Centre of Iran, then "
        "corrected (codes, rows and spelling). This workbook is generated from "
        f"output/2_corrected/questionnaire_{year}.csv of the HIESIR Codebook; it is not edited by hand.",
        text,
    )

    kinds = rows["kind"].to_list()
    figures = [
        ("Sections", kinds.count("section")),
        ("Group headers", kinds.count("header")),
        ("Items", kinds.count("item")),
    ]
    row = 6
    for name, value in figures:
        ws.write_string(row, 1, name, label)
        ws.write_number(row, 2, value, fmt(bold=True, font_size=12, font_color=NAVY, align="left"))
        row += 1
    for name, url in (("Documentation", SITE), ("Explorer", SITE + "explorer/"), ("Source", REPOSITORY)):
        ws.write_string(row, 1, name, label)
        ws.write_url(row, 2, url, link, string=url)
        row += 1
    ws.write_string(row, 1, "License", label)
    ws.write_string(row, 2, "MIT", fmt())

    row += 2
    ws.write_string(row, 1, "Sheets", heading)
    sheets = {
        "Questionnaire": "Every row in the order of the form: sections, group headers and items. "
        "Use the outline buttons (1–5, beside the column letters) to fold it to a level.",
        "Items": "The items only, one per row, with the section and group headers of each: "
        "the sheet to filter or join.",
    }
    for name, what in sheets.items():
        row += 1
        ws.set_row(row, 32)
        ws.write_url(row, 1, f"internal:'{name}'!A1", link, string=name)
        ws.merge_range(row, 2, row, last, what, text)

    row += 2
    ws.write_string(row, 1, "Sections", heading)
    row += 1
    for i, name in enumerate(("section", "items", "title", "first page"), start=1):
        ws.write_string(row, i, name, head)
    counts = dict(rows.filter(pl.col("kind") == "item").group_by("section").len().iter_rows())
    for r in rows.filter(pl.col("kind") == "section").iter_rows(named=True):
        row += 1
        ws.set_row(row, _height([(r["description"], 62)]))
        ws.write_url(
            row,
            1,
            f"internal:'Questionnaire'!A{sections[r['section']]}",
            fmt(**ruled, font_color=LINK, underline=1, align="left", indent=1),
            string=f"بخش {r['section']}",
        )
        # a section can be a title alone, with no expenditure items under it
        items = counts.get(r["section"], 0)
        if items:
            ws.write_number(row, 2, items, centred)
        else:
            ws.write_string(row, 2, "—", centred)
        ws.write_string(row, 3, r["description"], line_fa)
        if r["page"]:
            ws.write_number(row, 4, int(r["page"]), centred)
        else:
            ws.write_blank(row, 4, None, centred)
    if any(not counts.get(section) for section in sections):
        row += 1
        ws.write_string(row, 1, "— a title only, with no expenditure items under it", fmt(font_color=MUTED))

    row += 2
    ws.write_string(row, 1, "Columns", heading)
    row += 1
    for i, name in enumerate(("column", "sheet", "meaning"), start=1):
        ws.write_string(row, i, name, head)
    ws.merge_range(row, 4, row, last, "توضیح", head)
    for column, sheet, english, persian in COLUMNS:
        row += 1
        ws.set_row(row, _height([(english, 62)], line=16))
        ws.write_string(row, 1, column, mono)
        ws.write_string(row, 2, sheet, word)
        ws.write_string(row, 3, english, line)
        ws.merge_range(row, 4, row, last, persian, line_fa)

    row += 2
    ws.set_row(row, 32)
    muted = fmt(text_wrap=True, valign="top", font_color=MUTED)
    ws.merge_range(
        row,
        1,
        row,
        last,
        "Codes are text and keep their leading zero (011111): COICOP divisions 01–09 start with 0. "
        "The raw data stores them as numbers (11111): join on commodity_code. "
        "In pandas, read with dtype=str:",
        muted,
    )
    row += 1
    ws.merge_range(
        row, 1, row, last, 'pd.read_excel(path, sheet_name="Items", dtype=str)', fmt(font_name="Consolas")
    )
    ws.set_paper(9)
    ws.fit_to_pages(1, 0)


def write_workbook(year: int, source: Path = CORRECTED, out: Path = EXCEL) -> Path:
    """Write the workbook of ``year``; returns its path."""
    import xlsxwriter

    rows = read_year(year, source).with_columns(pl.col(pl.String).replace("", None))
    path = out / f"questionnaire_{year}.xlsx"
    path.parent.mkdir(parents=True, exist_ok=True)
    # written under another name and renamed once whole: a build that fails
    # half way leaves no workbook a release could pick up by mistake
    part = path.with_name(f"{path.stem}.part.xlsx")
    try:
        _write_book(xlsxwriter.Workbook(part), year, rows)
    except BaseException:
        part.unlink(missing_ok=True)
        raise
    part.replace(path)
    return path


def _write_book(workbook: Any, year: int, rows: pl.DataFrame) -> None:
    with workbook as book:
        book.set_properties(
            {
                "title": f"HIES questionnaire {year}: expenditure items",
                "subject": "Household Income and Expenditure Survey of Iran",
                "author": "HIESIR Codebook",
                "comments": f"Generated from output/2_corrected/questionnaire_{year}.csv ({REPOSITORY})",
            }
        )
        fmt = _Formats(book)
        about = book.add_worksheet("About")  # first, though it needs the rows of the next one
        sections = _questionnaire(book, fmt, rows)
        _items(book, fmt, items_table(rows.fill_null("")))
        _about(about, fmt, year, rows, sections)
        about.activate()


def main(years: list[int] | None = None, *, source: Path = CORRECTED, out: Path = EXCEL) -> None:
    """The corrected questionnaires as Excel workbooks -> dist/excel/.

    Parameters
    ----------
    years
        Survey years (default: all supported).
    source
        The yearly CSVs.
    out
        Where the workbooks go.
    """
    for year in years or SUPPORTED_YEARS:
        print(write_workbook(year, source, out).as_posix(), flush=True)
