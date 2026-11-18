import pytest

from hbsir_questionnaire.parse import (
    FOOTNOTE_TAIL_RE,
    NOT_DESC_RE,
    Row,
    _assign_levels,
    _classify,
    normalize_code,
)
from hbsir_questionnaire.pdf_text import glyph_name_to_text


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
        ("019999 تعداد سطرهای تکمیل شده در بخش 1", None),
        ("1 2 3 4 5 6 7", None),
        ("انواع نان", None),
    ],
)
def test_classify(text, expected):
    assert _classify(text) == expected


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
