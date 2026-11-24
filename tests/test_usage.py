import polars as pl
import pytest

from hiesir_codebook.usage import (
    SCHEMA,
    correct_codes,
    load_code_corrections,
    load_occurrence,
    load_share,
    read_usage,
)

HEADER = "year,expenditure_code,occurrence,expenditure_share\n"


def _table(tmp_path, text):
    path = tmp_path / "code_usage.csv"
    path.write_text(text, encoding="utf-8")
    return path


def test_long_table_gives_occurrence_and_share(tmp_path):
    path = _table(
        tmp_path,
        HEADER + "1383,11111,1302,0.0125\n"
        "1383,011112,2168,\n"  # a leading zero reads the same; no share
        "1384,11111,1515,0.011\n",
    )
    assert load_occurrence(path) == {1383: {11111: 1302, 11112: 2168}, 1384: {11111: 1515}}
    assert load_share(path) == {1383: {11111: 0.0125}, 1384: {11111: 0.011}}


def test_read_usage_is_typed_and_in_column_order(tmp_path):
    path = _table(tmp_path, "expenditure_share,note,occurrence,expenditure_code,year\n,x,5,11111,1383\n")
    df = read_usage(path)
    assert df.schema == pl.Schema(SCHEMA)
    assert df.columns == ["year", "expenditure_code", "occurrence", "expenditure_share"]
    assert df.row(0) == (1383, 11111, 5, None)


def test_a_wide_table_is_refused(tmp_path):
    path = _table(tmp_path, "expenditure_code,1383,1384\n11111,1302,1515\n")
    with pytest.raises(ValueError, match="no column year, occurrence, expenditure_share"):
        read_usage(path)


def test_a_year_and_code_twice_is_refused(tmp_path):
    path = _table(tmp_path, HEADER + "1383,11111,1,\n1383,011111,2,\n")
    with pytest.raises(ValueError, match=r"2 rows repeat a year and code, e\.g\. 1383 11111"):
        read_usage(path)


def test_a_count_that_is_not_a_whole_number_is_refused(tmp_path):
    path = _table(tmp_path, HEADER + "1383,11111,12.5,\n")
    with pytest.raises(pl.exceptions.ComputeError):
        read_usage(path)


def test_wrong_data_codes_move_their_households(tmp_path):
    path = tmp_path / "code_corrections.csv"
    text = "year,data_code,expenditure_code,reason\n1383,231,023111,group code 0231\n1388,45415,,noise\n"
    path.write_text(text, encoding="utf-8")
    fixes = load_code_corrections(path)
    assert fixes == {1383: {231: 23111}, 1388: {45415: None}}
    occ = {1383: {231: 172, 22111: 2449}, 1384: {231: 5, 23111: 429}, 1388: {45414: 83, 45415: 1}}
    assert correct_codes(occ, fixes) == {
        1383: {22111: 2449, 23111: 172},
        1384: {231: 5, 23111: 429},
        1388: {45414: 83},
    }
    assert load_code_corrections(tmp_path / "none.csv") == {}
