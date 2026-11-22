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
from hiesir_codebook.extraction.pdf_text import Line, Segment, VRule, glyph_name_to_text


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
    discards = []
    lines = [
        _line("11 0111 برنج", 100),
        _line("انواع برنج ایرانی", 110, 450),  # wraps the item above: kept
        _line("یادداشت پایین جدول", 300, 450),  # no code line within 30 pt
        _line("33", 790),  # a page number that reads as investment group 33 (1386)
    ]
    vrules = [VRule(560, 0, 800)]  # the right border of the code column
    lines.append(_line("برچسب", 105, 300))  # far from its column border (450)
    vrules.append(VRule(460, 0, 800))
    (e,) = _page_entries(lines, [], vrules, discards, page=4)
    assert (e.code, [s.text for s in e.after]) == ("0111", ["انواع برنج ایرانی"])
    assert {(d.page, d.y, d.reason, d.text) for d in discards} == {
        (4, 105, DROP_UNALIGNED, "برچسب"),
        (4, 300, DROP_NO_CODE, "یادداشت پایین جدول"),
        (4, 790, DROP_PAGE_NUMBER, "33"),
    }


def test_discards_are_optional():
    assert _page_entries([_line("یادداشت", 300, 450)], [], []) == []


def test_quirks_are_reported():
    from hiesir_codebook.extraction.layout import QUIRKS

    notes = [q.note for q in QUIRKS.values()]
    assert len(set(notes)) == len(notes)
    assert all(n.startswith(("repaired: ", "left out: ")) for n in notes)

    discards = []
    lines = [
        _line("69 312,0 سایر انواع پوشاک بچگانه", 100),  # 1384/1385: stray comma
        _line("مبلغ وام", 110, 450),  # a field label in the cell
        _line("3 یا 4", 120, 450),  # a source-code note
    ]
    (e,) = _page_entries(lines, [], [], discards, page=2)
    assert (e.code, e.sub) == ("0312", "69")
    assert sorted(d.reason for d in discards) == sorted(
        QUIRKS[k].note for k in ("stray_comma", "cell_label", "source_note")
    )
