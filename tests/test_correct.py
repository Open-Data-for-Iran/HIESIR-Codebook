from pathlib import Path

import polars as pl
import pytest

from hiesir_codebook import CSV_COLUMNS, SUPPORTED_YEARS, csv_io
from hiesir_codebook.correction.correct import correct
from hiesir_codebook.correction.corrections import Correction, apply_corrections
from hiesir_codebook.correction.fixes import Fix, FixList, read_spelling
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


def _frame(rows) -> pl.DataFrame:
    return pl.DataFrame(rows, schema=dict.fromkeys(rows[0], pl.String))


ROWS = _frame(
    [
        _row(4, "item", "0412", "11", "براورد اجارهبهای مسکن شخصی"),
        _row(4, "item", "0412", "11", "براورد اجارهبهای مسکن شخصی اقامتگاههای بعدی"),
        _row(4, "item", "0114", "32", "تخم مرغ غیر ماشینی"),
    ]
)


def test_recode_picks_the_row_by_description():
    fix = Correction(1, "recode", "041211", "براورد اجارهبهای مسکن شخصی اقامتگاههای بعدی", "042211", "typo")
    out = apply_corrections(1, ROWS, [fix], Path())
    assert out["expenditure_code"].to_list() == ["041211", "042211", "011432"]
    assert (out["code"][1], out["sub"][1]) == ("0422", "11")
    assert ROWS["expenditure_code"][1] == "041211"  # input untouched


def test_retext():
    fix = Correction(1, "retext", "011432", "", "پنیر پیتزا", "typo")
    assert apply_corrections(1, ROWS, [fix], Path())["description"][2] == "پنیر پیتزا"


def test_corrections_of_other_years_are_left_alone():
    fix = Correction(2, "retext", "011432", "", "پنیر پیتزا", "typo")
    assert apply_corrections(1, ROWS, [fix], Path()).equals(ROWS)


def test_header_corrections():
    rows = _frame(
        [
            {**_row(5, "header", "062 M", "", "خدمات خانگی و مراقبت از منزل (خدمت)"), "level": "2"},
            {**_row(6, "header", "0622", "", "خدمات پزشکی"), "level": "3"},
            _row(6, "item", "0622", "11", "ویزیت دندانپزشک (دولتی)"),
        ]
    )
    fixes = [
        Correction(1386, "recode_header", "062 M", "", "0562 M", "typo"),
        Correction(1386, "retext_header", "0622", "خدمات پزشکی", "خدمات دندانپزشکی", "typo"),
    ]
    out = apply_corrections(1386, rows, fixes, Path())
    assert (out["code"][0], out["level"][0]) == ("0562 M", "3")  # the level follows the code
    assert out["description"][1] == "خدمات دندانپزشکی"
    assert out.row(2) == rows.row(2)  # an item with the same code is not a header


def test_ambiguous_or_missing_target_fails():
    with pytest.raises(ValueError, match="2 matching rows"):
        apply_corrections(1, ROWS, [Correction(1, "recode", "041211", "", "042111", "typo")], Path())
    with pytest.raises(ValueError, match="0 matching rows"):
        apply_corrections(1, ROWS, [Correction(1, "retext", "011432", "پنیر", "x", "typo")], Path())


def test_description_match_ignores_spacing():
    fix = Correction(1, "retext", "011432", "  تخم مرغ   غیر ماشینی ", "تخم‌مرغ", "typo")
    assert apply_corrections(1, ROWS, [fix], Path())["description"][2] == "تخم‌مرغ"


def test_add_section(tmp_path):
    csv_io.write(
        tmp_path / "questionnaire_2.csv",
        CSV_COLUMNS,
        [_row(2, "section", "", "", "دخانیات"), _row(2, "item", "0221", "12", "سیگار بهمن")],
    )
    rows = _frame([_row(1, "item", "0111", "11", "برنج"), _row(3, "item", "0312", "11", "پیراهن")])
    out = apply_corrections(1, rows, [Correction(1, "add_section", "", "2", "2", "page blank")], tmp_path)
    assert out["section"].to_list() == ["1", "2", "2", "3"]
    assert out["page"][2] == ""
    with pytest.raises(ValueError, match="already present"):
        apply_corrections(1, out, [Correction(1, "add_section", "", "2", "2", "page blank")], tmp_path)


def test_delete_removes_empty_group_headers():
    rows = _frame(
        [
            _row(2, "header", "022", "", "دخانیات"),
            _row(2, "header", "0221", "", "دخانیات"),
            _row(2, "item", "0221", "12", "سیگار بهمن"),
            _row(2, "header", "023", "", "سایر مواد دخانی"),
            _row(2, "header", "0231", "", "سایر مواد دخانی"),
            _row(2, "item", "0231", "11", "سایر مواد دخانی"),
        ]
    )
    out = apply_corrections(1, rows, [Correction(1, "delete", "023111", "", "", "not asked")], Path())
    assert out["code"].to_list() == ["022", "0221", "0221"]


def test_corrected_is_up_to_date(tmp_path):
    """output/2_corrected/ must equal output/1_extracted/ + curated/; if this
    fails, run `uv run hiesir-codebook correct`."""
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


def test_build_applies_the_canonical_word_fixes(tmp_path):
    """correct() runs the word fixes of words.csv on every label (a
    label printed only once included), not just the canonical step itself."""
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
        words=tmp_path / "words.csv",
        canonical=tmp_path / "no_canonical.csv",
    )
    assert csv_io.read(out / "questionnaire_1383.csv")[0]["description"] == "سایر وسایل"


# --- the fixes of spelling.csv ---------------------------------------------------


def _fix(find, replace, match="word", years=""):
    return Fix(find, replace, match, parse_years(years), "test")


def _apply(text, year, *fixes):
    return FixList(fixes).apply(text, year)


def test_fix_whole_words():
    fixes = [_fix("بجز", "به جز"), _fix("هزینه های", "هزینه‌های")]
    assert _apply("ویزیت پزشک بجز روانپزشک", 1390, *fixes) == "ویزیت پزشک به جز روانپزشک"
    assert _apply("(بجز کره)، شیر", 1390, *fixes) == "(به جز کره)، شیر"
    assert _apply("بجزروانی", 1390, *fixes) == "بجزروانی"  # not inside a longer word
    assert _apply("هزینه های، سایرهزینه های", 1390, *fixes) == "هزینه‌های، سایرهزینه های"


def test_fix_text_and_years():
    assert _apply("آّبرنگ", 1386, _fix("آّ", "آ", "text")) == "آبرنگ"
    fix = _fix("دیبرستان", "دبیرستان", years="1383-1385 1402")
    assert _apply("دیبرستان", 1384, fix) == "دبیرستان"
    assert _apply("دیبرستان", 1402, fix) == "دبیرستان"
    assert _apply("دیبرستان", 1390, fix) == "دیبرستان"


def test_fix_is_blind_to_zwnj():
    z = "‌"
    fixes = [_fix("شدهباشد", "شده باشد"), _fix(f"چربی{z}ها ی", f"چربی{z}های")]
    assert _apply(f"پرداخت شده{z}باشد", 1390, *fixes) == "پرداخت شده باشد"
    assert _apply("پرداخت شدهباشد", 1390, *fixes) == "پرداخت شده باشد"
    assert _apply("چربیها ی حیوانی", 1390, *fixes) == f"چربی{z}های حیوانی"
    assert _apply(f"شده{z}باشدن", 1390, *fixes) == f"شده{z}باشدن"  # still whole words only


def test_fix_counts_hits():
    hits = []
    FixList([_fix("بجز", "به جز")]).apply("بجز کره بجز شیر", 1390, hits)
    assert [fx.find for fx in hits] == ["بجز"]  # descriptions changed, not occurrences
    FixList([_fix("به جز", "به جز")]).apply("به جز کره", 1390, hits)
    assert len(hits) == 1  # a fix that changes nothing is no hit


def test_guard_leaves_a_hand_decision_alone():
    words = FixList([_fix("سی دی", "سی‌دی"), _fix("نوار", "نوارها")])
    guard = FixList([_fix("سی دی", "سی دی")])
    assert words.apply("انواع سی دی و نوار", 0, None, guard) == "انواع سی دی و نوارها"


def test_spelling_rows_need_a_reason_and_a_known_match(tmp_path):
    path = tmp_path / "spelling.csv"
    columns = ["find", "replace", "match", "years", "reason"]
    csv_io.write(
        path, columns, [{"find": "بجز", "replace": "به جز", "match": "", "years": "", "reason": " "}]
    )
    with pytest.raises(ValueError, match="reason"):
        read_spelling(path)
    csv_io.write(
        path, columns, [{"find": "بجز", "replace": "به جز", "match": "all", "years": "", "reason": "x"}]
    )
    with pytest.raises(ValueError, match="'word' or 'text'"):
        read_spelling(path)
    csv_io.write(
        path, columns, [{"find": "بجز", "replace": "به جز", "match": "", "years": "1390", "reason": "x"}]
    )
    (fx,) = read_spelling(path)
    assert (fx.match, fx.years, fx.kind) == ("word", frozenset({1390}), "x")


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
