"""The Excel workbooks: they say what the corrected CSV says, and nothing else."""

import polars as pl
import pytest
from openpyxl import load_workbook

from hiesir_codebook import CORRECTED, GROUPS, SUPPORTED_YEARS, csv_io
from hiesir_codebook.excel import ITEMS, QUESTIONNAIRE, items_table, read_year, write_workbook

YEAR = 1403


@pytest.fixture(scope="module")
def book(tmp_path_factory):
    return load_workbook(write_workbook(YEAR, CORRECTED, tmp_path_factory.mktemp("excel")))


def _rows(sheet):
    header, *rows = sheet.iter_rows(values_only=True)
    return [dict(zip(header, row, strict=True)) for row in rows]


def test_sheets(book):
    assert book.sheetnames == ["About", "Questionnaire", "Items"]
    assert not book["Questionnaire"].sheet_view.rightToLeft  # tables read left to right
    assert book["Questionnaire"].freeze_panes == "A2"


def test_questionnaire_is_the_csv(book):
    """Every row and cell of the CSV, in its order; codes are text with their leading zero."""
    numbers = {c for c, _, how in QUESTIONNAIRE if how == "number"}
    expected = [
        {c: (int(r[c]) if c in numbers else r[c]) if r[c] else None for c, _, _ in QUESTIONNAIRE}
        for r in read_year(YEAR).iter_rows(named=True)
    ]
    assert _rows(book["Questionnaire"]) == expected
    assert expected[4]["expenditure_code"] == "011111"


def test_items_have_their_groups(book):
    """The Items sheet is the items of the CSV, and the group codes found by
    walking the form are those the groups stage gives the same items."""
    items = _rows(book["Items"])
    csv_items = read_year(YEAR).filter(pl.col("kind") == "item")
    assert [i["expenditure_code"] for i in items] == csv_items["expenditure_code"].to_list()
    assert [i["description"] for i in items] == csv_items["description"].to_list()
    assert all(i["commodity_code"] == int(i["expenditure_code"]) for i in items)
    assert list(items[0]) == [c for c, _, _ in ITEMS]

    code = {g["group_id"]: g["code"] for g in csv_io.read(GROUPS / "groups.csv")}
    members = {
        m["expenditure_code"]: m for m in csv_io.read(GROUPS / "members.csv") if m["year"] == str(YEAR)
    }
    for i in items:
        m = members[i["expenditure_code"]]
        for level in (2, 3, 4):
            assert (i[f"level_{level}_code"] or "") == code.get(m[f"level_{level}"], ""), i


@pytest.mark.parametrize("year", SUPPORTED_YEARS)
def test_every_year_has_its_items(year):
    """Each year's items table builds, whatever its CSV leaves empty (1383
    gives no page for section 2)."""
    rows = read_year(year)
    items = items_table(rows)
    assert len(items) == rows.filter(pl.col("kind") == "item").height


def test_failed_build_leaves_no_workbook(tmp_path):
    source = tmp_path / "csv"
    source.mkdir()
    rows = read_year(YEAR).with_columns(
        pl.when(pl.col("kind") == "item")
        .then(pl.lit("not a code"))
        .otherwise("expenditure_code")
        .alias("expenditure_code")
    )
    rows.write_csv(source / f"questionnaire_{YEAR}.csv")
    with pytest.raises(ValueError):
        write_workbook(YEAR, source, tmp_path / "out")
    assert not list((tmp_path / "out").iterdir())


def test_groups_reset_with_the_level_above():
    rows = pl.DataFrame(
        {
            "section": ["1"] * 6,
            "kind": ["section", "header", "header", "item", "header", "item"],
            "level": ["", "2", "3", "5", "2", "5"],
            "code": ["", "011", "0111", "0111", "012", "0121"],
            "expenditure_code": ["", "", "", "011111", "", "012111"],
            "description": ["s", "a", "b", "x", "c", "y"],
            "page": ["6"] * 6,
        }
    )
    first, second = items_table(rows)
    assert (first["level_2"], first["level_3"], first["section_title"]) == ("a", "b", "s")
    assert (second["level_2"], second["level_3"], second["level_3_code"]) == ("c", "", "")
