import pytest

from hiesir_codebook.extraction.parse import (
    DROP_NO_CODE,
    DROP_PAGE_NUMBER,
    DROP_UNALIGNED,
    FOOTNOTE_TAIL_RE,
    NOT_DESC_RE,
    Row,
    _assign_levels,
    _classify,
    _page_entries,
    normalize_code,
)
from hiesir_codebook.extraction.pdf_text import Line, Notes, Rule, Segment, VRule, glyph_name_to_text


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("0111", "0111"),
        ("01112 و 01111", "01111, 01112"),
        ("01182،01183 و 01184", "01182, 01183, 01184"),
        ("A091", "091 A"),
        ("091A", "091 A"),
        ("M0540", "0540 M"),
        ("342و341", "341, 342"),
    ],
)
def test_normalize_code(raw, expected):
    assert normalize_code(raw) == expected


def test_expenditure_code_keeps_leading_zero():
    assert Row("item", 1, "0111", "11", "برنج", 0).expenditure_code == "011111"
    assert Row("item", 1, "111", "10", "آرد گندم", 0).expenditure_code == "11110"  # 1382 scheme
    assert Row("item", 13, "091 A", "11", "تلویزیون", 0).expenditure_code == "09111"
    assert Row("header", 1, "0111", None, "غلات", 0).expenditure_code is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("11 0111 برنج صدری", ("item", "0111", "11", "برنج صدری")),
        ("17 0911", ("item", "0911", "17", "")),  # description wraps around the code
        ("0111 غلات، نان", ("header", "0111", None, "غلات، نان")),
        ("01112 و 01111 غلات", ("header", "01112 و 01111", None, "غلات")),
        ("01182،01183", ("header", "01182،01183", None, "")),
        # a code list continued on the next code line (1386, 1391-1394)
        ("06312 و", ("head", "06312", None, "")),
        ("01193و چاشنی‌ها", ("head", "01193", None, "چاشنی‌ها")),
        ("01193و 01192 چاشنی‌ها", ("header", "01193و 01192", None, "چاشنی‌ها")),
        ("019999 تعداد سطرهای تکمیل شده در بخش 1", None),
        ("1 2 3 4 5 6 7", None),
        ("انواع نان", None),
    ],
)
def test_classify(text, expected):
    assert _classify(text) == expected


def _line(text: str, y: float, x1: float = 550) -> Line:
    return Line(text, y, x1 - 100, x1, segments=[Segment(text, x1 - 100, x1)])


@pytest.mark.parametrize(
    ("lines", "code", "desc"),
    [
        # 1391-1394: "06312 و" / description / "06313 M"
        (
            [_line("06312 و", 485.0), _line("خدمات بیمارستانهای تخصصی", 493.9, 450), _line("06313 M", 501.0)],
            "06312, 06313 M",
            "خدمات بیمارستانهای تخصصی",
        ),
        # 1386: "01193و <description>" / "01192"
        ([_line("01193و چاشنی‌ها", 203.7), _line("01192", 222.8)], "01193, 01192", "چاشنی‌ها"),
    ],
)
def test_split_code_list_is_one_header(lines, code, desc):
    (e,) = _page_entries(lines, [], [])
    assert (e.kind, e.code, e.desc) == ("header", code, desc)
    assert normalize_code(e.code) == normalize_code(code.replace(", ", " و "))


def test_assign_levels():
    rows = [
        Row("header", 1, "011", None, "", 0),
        Row("header", 1, "0111", None, "", 0),
        Row("header", 1, "01111, 01112", None, "", 0),
        Row("item", 1, "0111", "11", "", 0),
        Row("header", 14, "33", None, "", 0),
        Row("header", 14, "331, 332", None, "", 0),
    ]
    _assign_levels(rows, old_scheme=False)
    assert [r.level for r in rows] == [2, 3, 4, 5, 2, 3]

    old = [Row("header", 1, "11", None, "", 0), Row("header", 1, "111", None, "", 0)]
    _assign_levels(old, old_scheme=True)
    assert [r.level for r in old] == [2, 3]


def test_footnote_tail_is_stripped():
    assert FOOTNOTE_TAIL_RE.sub("", "حق بیمه عمر 3 یا 4") == "حق بیمه عمر"
    assert FOOTNOTE_TAIL_RE.sub("", "حق بیمه (سهم دولت) 8") == "حق بیمه (سهم دولت)"
    # an ordinary trailing number is kept
    assert FOOTNOTE_TAIL_RE.sub("", "متوسطه 1 و 2") == "متوسطه 1 و 2"


def test_cell_labels_are_not_descriptions():
    assert NOT_DESC_RE.match("تعداد افراد بیمه شده")
    assert NOT_DESC_RE.match("یا 8")
    assert not NOT_DESC_RE.match("خاک قند)")


@pytest.mark.parametrize(
    ("name", "text"),
    [
        ("pehisolated", "پ"),
        ("gafinitial", "گ"),
        ("lamwithalefisolated", "لا"),
        ("arabicindicdigitseven", "7"),
        ("uni0628", "ب"),
        ("parenleft", "("),
        ("glyph00042", None),
    ],
)
def test_glyph_name_to_text(name, text):
    assert glyph_name_to_text(name) == text


def test_stray_comma_in_code():
    # 1384/1385 print "0312" as "312,0" (read right-to-left)
    assert _classify("69 312,0 سایر انواع پوشاک بچگانه") == ("item", "0312", "69", "سایر انواع پوشاک بچگانه")


def test_left_out_text_is_reported():
    notes = Notes(page=4)
    lines = [
        _line("11 0111 برنج", 100),
        _line("انواع برنج ایرانی", 110, 450),  # wraps the item above: kept
        _line("یادداشت پایین جدول", 300, 450),  # no code line within 30 pt
        _line("33", 790),  # a page number that reads as investment group 33 (1386)
    ]
    vrules = [VRule(560, 0, 800)]  # the right border of the code column
    lines.append(_line("برچسب", 105, 300))  # far from its column border (450)
    vrules.append(VRule(460, 0, 800))
    (e,) = _page_entries(lines, [], vrules, notes)
    assert (e.code, [s.text for s in e.after]) == ("0111", ["انواع برنج ایرانی"])
    assert {(n.page, n.y, n.reason, n.text) for n in notes.items} == {
        (4, 105, DROP_UNALIGNED, "برچسب"),
        (4, 300, DROP_NO_CODE, "یادداشت پایین جدول"),
        (4, 790, DROP_PAGE_NUMBER, "33"),
    }


def test_third_line_of_a_tall_cell_stays_with_its_item():
    # 1389 p. 52: the third line of 093124 is 32.6 pt below its code line
    # (beyond Distances.wrap) and nearer the next item, across a row rule
    lines = [
        _line("24 0931 اقلام و ملزومات", 163.1),
        _line("نمونه‌های مربوط به جانورشناسی", 179.4, 486),
        _line("تمبر و ..)", 195.7, 486),
        _line("25 0931 انواع نرم‌افزارهای بازی", 214.5),
    ]
    rules = [Rule(y, 44, 553) for y in (152.6, 204.0, 222.8)]
    e24, e25 = _page_entries(lines, rules, [])
    assert [s.text for s in e24.after] == ["نمونه‌های مربوط به جانورشناسی", "تمبر و ..)"]
    assert (e25.before, e25.after) == ([], [])


def test_notes_are_optional():
    assert _page_entries([_line("یادداشت", 300, 450)], [], []) == []


def test_quirks_are_reported():
    from hiesir_codebook.extraction.layout import QUIRKS

    notes = [q.note for q in QUIRKS.values()]
    assert len(set(notes)) == len(notes)
    assert all(n.startswith(("repaired: ", "left out: ")) for n in notes)

    notes = Notes(page=2)
    lines = [
        _line("69 312,0 سایر انواع پوشاک بچگانه", 100),  # 1384/1385: stray comma
        _line("مبلغ وام", 110, 450),  # a field label in the cell
        _line("3 یا 4", 120, 450),  # a source-code note
    ]
    (e,) = _page_entries(lines, [], [], notes)
    assert (e.code, e.sub) == ("0312", "69")
    assert sorted(n.reason for n in notes.items) == sorted(
        QUIRKS[k].note for k in ("stray_comma", "cell_label", "source_note")
    )


def test_row_box_snaps_to_the_table_row():
    from hiesir_codebook.extraction.parse import _Entry, _row_box
    from hiesir_codebook.extraction.pdf_text import Glyph, Rule

    ln = Line(
        "11 0111 برنج",
        100,
        400,
        550,
        [Glyph("ب", 400, 550, 95, 105, 11)],
        [Segment("11 0111 برنج", 400, 550)],
    )
    e = _Entry(ln, "item", "0111", "11", "برنج")
    rules = [Rule(88, 50, 560), Rule(112, 50, 560), Rule(140, 50, 560)]  # the row is 88-112
    vrules = [VRule(50, 0, 800), VRule(560, 0, 800), VRule(300, 0, 800)]
    assert _row_box(e, rules, vrules) == (88, 112, 50, 560)
    far = [Rule(60, 50, 560), Rule(140, 50, 560)]  # no rule within 14 pt: the text's extent
    assert _row_box(e, far, []) == (95, 105, None, None)


def test_split_code_is_joined_and_stray_two_digits_dropped():
    from hiesir_codebook.extraction.layout import QUIRKS
    from hiesir_codebook.extraction.parse import DROP_STRAY_TWO_DIGIT, _join_split_codes

    lines = [
        _line("13 رادیولوژی، سونوگرافی", 100),  # 1391-1394: the sub-code on the first line
        _line("0623", 112),  # ... the code centred a line below
        _line("47 متن بیرون از جدول", 400),  # two digits and text, no code below: stray text
    ]
    notes = Notes(page=3)
    entries = _join_split_codes(_page_entries(lines, [], [], notes), notes)
    assert [(e.kind, e.code, e.sub, e.desc) for e in entries] == [
        ("item", "0623", "13", "رادیولوژی، سونوگرافی")
    ]
    assert [n.reason for n in notes.items] == [QUIRKS["split_code"].note, DROP_STRAY_TWO_DIGIT]


def test_item_continued_on_the_next_page_is_joined():
    from hiesir_codebook.extraction.layout import QUIRKS
    from hiesir_codebook.extraction.parse import _merge_page_breaks

    rows = [
        Row("item", 9, "0932", "51", "ملزومات جمع آوری تمبر(... آلبوم تمبر", 40),
        Row("item", 9, "0932", "51", "واقلام دیگر)", 41, top=60),
        Row("item", 9, "0932", "52", "اسباب بازی", 41),
    ]
    notes = Notes()
    out = _merge_page_breaks(rows, notes)
    assert [(r.sub, r.desc) for r in out] == [
        ("51", "ملزومات جمع آوری تمبر(... آلبوم تمبر واقلام دیگر)"),
        ("52", "اسباب بازی"),
    ]
    assert [(n.page, n.reason) for n in notes.items] == [(41, QUIRKS["page_break"].note)]


def test_report_groups_repeated_notes(tmp_path):
    from hiesir_codebook import csv_io
    from hiesir_codebook.extraction import Note, write_report

    notes = [
        Note(5, 98.9, "left out", "کد"),
        Note(6, 98.9, "left out", "کد"),
        Note(7, 98.9, "left out", "کد"),
    ]
    notes += [
        Note(9, None, "glyph", "ا", 40),
        Note(5, 300.0, "left out", "یادداشت"),
        Note(10, None, "glyph", "ا", 2),
    ]
    path = tmp_path / "report.csv"
    write_report(notes, path)
    rows = csv_io.read(path)
    assert [(r["page"], r["y"], r["text"], r["count"], r["pages"]) for r in rows] == [
        ("6", "98.9", "کد", "3", "6-8"),  # 1-based, first met, one row for the heading on every page
        ("10", "", "ا", "42", "10-11"),
        ("6", "300.0", "یادداشت", "1", "6"),
    ]
