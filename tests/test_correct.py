from pathlib import Path

import pytest

from hiesir_codebook import SUPPORTED_YEARS
from hiesir_codebook.correction.correct import apply, correct, write_rows
from hiesir_codebook.correction.corrections import Correction
from hiesir_codebook.correction.spelling import LabelFix, fix_label
from hiesir_codebook.utils import parse_years

ROOT = Path(__file__).resolve().parents[1]


def _row(section, kind, code, sub, desc):
    return {
        "section": str(section),
        "kind": kind,
        "level": "5" if kind == "item" else "",
        "code": code,
        "sub": sub,
        "expenditure_code": code + sub if kind == "item" else "",
        "description": desc,
        "page": "1",
    }


ROWS = [
    _row(4, "item", "0412", "11", "براورد اجارهبهای مسکن شخصی"),
    _row(4, "item", "0412", "11", "براورد اجارهبهای مسکن شخصی اقامتگاههای بعدی"),
    _row(4, "item", "0114", "32", "تخم مرغ غیر ماشینی"),
]


def test_recode_picks_the_row_by_description():
    fix = Correction(1, "recode", "041211", "براورد اجارهبهای مسکن شخصی اقامتگاههای بعدی", "042211", "typo")
    out = apply(1, ROWS, [fix], Path())
    assert [r["expenditure_code"] for r in out] == ["041211", "042211", "011432"]
    assert (out[1]["code"], out[1]["sub"]) == ("0422", "11")
    assert ROWS[1]["expenditure_code"] == "041211"  # input untouched


def test_retext():
    fix = Correction(1, "retext", "011432", "", "پنیر پیتزا", "typo")
    assert apply(1, ROWS, [fix], Path())[2]["description"] == "پنیر پیتزا"


def test_header_corrections():
    rows = [
        {**_row(5, "header", "062 M", "", "خدمات خانگی و مراقبت از منزل (خدمت)"), "level": "2"},
        {**_row(6, "header", "0622", "", "خدمات پزشکی"), "level": "3"},
        _row(6, "item", "0622", "11", "ویزیت دندانپزشک (دولتی)"),
    ]
    fixes = [
        Correction(1386, "recode_header", "062 M", "", "0562 M", "typo"),
        Correction(1386, "retext_header", "0622", "خدمات پزشکی", "خدمات دندانپزشکی", "typo"),
    ]
    out = apply(1386, rows, fixes, Path())
    assert (out[0]["code"], out[0]["level"]) == ("0562 M", "3")  # the level follows the code
    assert out[1]["description"] == "خدمات دندانپزشکی"
    assert out[2] == rows[2]  # an item with the same code is not a header


def test_ambiguous_or_missing_target_fails():
    with pytest.raises(ValueError, match="2 matching rows"):
        apply(1, ROWS, [Correction(1, "recode", "041211", "", "042111", "typo")], Path())
    with pytest.raises(ValueError, match="0 matching rows"):
        apply(1, ROWS, [Correction(1, "retext", "011432", "پنیر", "x", "typo")], Path())


def test_add_section(tmp_path):
    write_rows(
        [_row(2, "section", "", "", "دخانیات"), _row(2, "item", "0221", "12", "سیگار بهمن")],
        tmp_path / "questionnaire_2.csv",
    )
    rows = [_row(1, "item", "0111", "11", "برنج"), _row(3, "item", "0312", "11", "پیراهن")]
    out = apply(1, rows, [Correction(1, "add_section", "", "2", "2", "page blank")], tmp_path)
    assert [r["section"] for r in out] == ["1", "2", "2", "3"]
    assert out[2]["page"] == ""


def test_corrected_is_up_to_date(tmp_path):
    """output/2_corrected/ must equal output/1_extracted/ + curated/; if this
    fails, run `uv run python -m hiesir_codebook.correction.correct`."""
    correct(
        SUPPORTED_YEARS,
        ROOT / "output" / "1_extracted",
        tmp_path,
        ROOT / "curated" / "2_corrected" / "corrections.csv",
        ROOT / "curated" / "2_corrected" / "spelling.csv",
    )
    for year in SUPPORTED_YEARS:
        name = f"questionnaire_{year}.csv"
        assert (tmp_path / name).read_bytes() == (ROOT / "output" / "2_corrected" / name).read_bytes(), name


def test_delete_removes_empty_group_headers():
    rows = [
        _row(2, "header", "022", "", "دخانیات"),
        _row(2, "header", "0221", "", "دخانیات"),
        _row(2, "item", "0221", "12", "سیگار بهمن"),
        _row(2, "header", "023", "", "سایر مواد دخانی"),
        _row(2, "header", "0231", "", "سایر مواد دخانی"),
        _row(2, "item", "0231", "11", "سایر مواد دخانی"),
    ]
    out = apply(1, rows, [Correction(1, "delete", "023111", "", "", "not asked")], Path())
    assert [r["code"] for r in out] == ["022", "0221", "0221"]


def _fix(find, replace, match="word", years=""):
    return LabelFix(find, replace, match, parse_years(years), "test")


def test_label_fix_whole_words():
    fixes = [_fix("بجز", "به جز"), _fix("هزینه های", "هزینه‌های")]
    assert fix_label("ویزیت پزشک بجز روانپزشک", 1390, fixes) == "ویزیت پزشک به جز روانپزشک"
    assert fix_label("(بجز کره)، شیر", 1390, fixes) == "(به جز کره)، شیر"
    assert fix_label("بجزروانی", 1390, fixes) == "بجزروانی"  # not inside a longer word
    assert fix_label("هزینه های، سایرهزینه های", 1390, fixes) == "هزینه‌های، سایرهزینه های"


def test_label_fix_text_and_years():
    assert fix_label("آّبرنگ", 1386, [_fix("آّ", "آ", "text")]) == "آبرنگ"
    fixes = [_fix("دیبرستان", "دبیرستان", years="1383-1385 1402")]
    assert fix_label("دیبرستان", 1384, fixes) == "دبیرستان"
    assert fix_label("دیبرستان", 1402, fixes) == "دبیرستان"
    assert fix_label("دیبرستان", 1390, fixes) == "دیبرستان"


def test_label_fix_is_blind_to_zwnj():
    z = "‌"
    fixes = [_fix("شدهباشد", "شده باشد"), _fix(f"چربی{z}ها ی", f"چربی{z}های")]
    assert fix_label(f"پرداخت شده{z}باشد", 1390, fixes) == "پرداخت شده باشد"
    assert fix_label("پرداخت شدهباشد", 1390, fixes) == "پرداخت شده باشد"
    assert fix_label("چربیها ی حیوانی", 1390, fixes) == f"چربی{z}های حیوانی"
    assert fix_label(f"شده{z}باشدن", 1390, fixes) == f"شده{z}باشدن"  # still whole words only


def test_label_fix_counts_hits():
    hits = {}
    fix_label("بجز کره بجز شیر", 1390, [_fix("بجز", "به جز")], hits)
    assert hits == {"بجز": 1}  # descriptions changed, not occurrences


def test_corrected_codes_agree_with_the_raw_data(capsys):
    """Every code households report (5 or more) is printed, none twice, and
    the raw data supports every code-level correction.  Needs the occurrence
    table (data/, downloaded in CI)."""
    from hiesir_codebook.correction.corrections import check_occurrence, load_corrections, verify
    from hiesir_codebook.occurrence import occurrence_files

    path = occurrence_files(ROOT / "data")
    if len(path) < 2:
        pytest.skip("no occurrence tables in data/")
    years = SUPPORTED_YEARS
    contradicted = verify(
        load_corrections(ROOT / "curated" / "2_corrected" / "corrections.csv"),
        ROOT / "output" / "1_extracted",
        path,
    )
    failed = check_occurrence(years, ROOT / "output" / "2_corrected", path)
    out = capsys.readouterr().out
    assert (contradicted, failed) == (0, 0), "\n".join(
        ln for ln in out.splitlines() if "<--" in ln or "not printed:" in ln or "twice" in ln
    )


def test_build_applies_the_canonical_word_fixes(tmp_path):
    """correct() runs the word fixes of canonical_words.csv on every label (a
    label printed only once included), not just the canonical step itself."""
    from hiesir_codebook import CSV_COLUMNS, csv_io

    extracted = tmp_path / "extracted"
    row = dict.fromkeys(CSV_COLUMNS, "")
    row |= {"section": "1", "kind": "item", "code": "0111", "sub": "11", "expenditure_code": "011111"}
    csv_io.write(extracted / "questionnaire_1383.csv", CSV_COLUMNS, [row | {"description": "سایر وسائل"}])
    csv_io.write(
        tmp_path / "corrections.csv",
        ["year", "action", "expenditure_code", "description", "value", "reason"],
        [],
    )
    csv_io.write(
        tmp_path / "words.csv",
        ["find", "replace", "kind", "uses", "evidence"],
        [{"find": "وسائل", "replace": "وسایل", "kind": "folded", "uses": "1", "evidence": "test"}],
    )
    out = tmp_path / "out"
    correct(
        [1383],
        extracted,
        out,
        tmp_path / "corrections.csv",
        tmp_path / "no_spelling.csv",
        autocorrect=tmp_path / "no_hazm.csv",
        canonical=tmp_path / "no_canonical.csv",
        canonical_words=tmp_path / "words.csv",
    )
    assert csv_io.read(out / "questionnaire_1383.csv")[0]["description"] == "سایر وسایل"
