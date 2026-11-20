import pytest

from hiesir_codebook import utils
from hiesir_codebook.utils import ZWNJ, standard_spelling, tidy_punctuation


def test_unify_letters():
    assert utils.unify_letters("علي كتاب") == "علی کتاب"


def test_digits_round_trip():
    assert utils.to_ascii_digits("۱۴۰۳ و ١٢") == "1403 و 12"
    assert utils.to_persian_digits("بخش 01") == "بخش ۰۱"


def test_canonical_folds_presentation_forms():
    assert utils.canonical("ﺑ") == "ب"
    assert utils.canonical("ﻼ") == "لا"
    assert utils.canonical("ي") == "ی"


def test_tidy_zwnj_and_whitespace():
    assert utils.tidy_zwnj(f"هزینه{ZWNJ}{ZWNJ}ها") == f"هزینه{ZWNJ}ها"
    assert utils.tidy_zwnj(f"هزینه {ZWNJ}ها") == "هزینه ها"
    assert utils.collapse_whitespace("  a \t b\n") == "a b"


def test_normalize_persian():
    assert utils.normalize_persian("علي  ـ ۱۲") == "علی 12"


def test_mirror_and_ltr_runs():
    assert utils.mirror_brackets(")گندم(") == "(گندم)"
    # Latin runs are reversed as a whole
    assert utils.fix_ltr_runs("واکمن، reyalP 4PM ,3PM") == "واکمن، MP3, MP4 Player"
    # each number is reversed, but a code pair keeps its right-to-left order
    assert utils.fix_ltr_runs("11 1110") == "11 0111"


def test_normalize_visual():
    # text as produced by sorting glyphs right-to-left
    assert utils.normalize_visual("11 1110 برنج طارم") == "11 0111 برنج طارم"
    assert utils.normalize_visual(")ﺭﻳﺎﻝ(") == "(ریال)"


def test_loose_key_ignores_spacing_and_punctuation():
    assert utils.loose_key(f"هزینه{ZWNJ}های (ریال)") == utils.loose_key("هزينه هاي ريال")
    assert utils.loose_key("آب") == utils.loose_key("اب")
    assert utils.loose_key("نان") != utils.loose_key("نام")


def test_classification():
    assert utils.has_persian("abc ب")
    assert not utils.has_persian("abc 123")
    assert utils.has_letters("MRI")
    assert not utils.has_letters("3 - 4")
    assert utils.joins_next("ب")
    assert not utils.joins_next("ا")


@pytest.mark.parametrize(
    ("raw", "tidy"),
    [
        ("آرد ، رشته ،غلات", "آرد، رشته، غلات"),
        ("نان ماشینی(لواش ،سنگک)", "نان ماشینی (لواش، سنگک)"),
        ("ورمیشل ( رشته فرنگی )", "ورمیشل (رشته فرنگی)"),
        ("هویج(ایرانی)چغندر", "هویج (ایرانی) چغندر"),
        ("ویزیت (دولتی) ، ویزیت", "ویزیت (دولتی)، ویزیت"),
        ("خردکردن و..... )", "خردکردن و ...)"),
        ("از قبیل:سبد", "از قبیل: سبد"),
        ("پارافین,وازلین", "پارافین، وازلین"),
        ("سینی، دیس،، کتری", "سینی، دیس، کتری"),
        ("(... نظایر)، سکه، ...", "(... نظایر)، سکه، ..."),
        ("دیس، ، کتری", "دیس، کتری"),
        ("1,000 ریال ساعت 10:30", "1,000 ریال ساعت 10:30"),
        ("انواع ویدئو (VHS)، سی دی", "انواع ویدئو (VHS)، سی دی"),
        ("کاهدان و. . .)", "کاهدان و ...)"),
        ("کله‌پاچه و...وسایر", "کله‌پاچه و ... وسایر"),
        ("در12ماه گذشته", "در 12 ماه گذشته"),
        ("پژو405", "پژو 405"),
        ("MP3، MP4 Player", "MP3، MP4 Player"),
        ("راهنمایی/ متوسطه1و2", "راهنمایی / متوسطه 1 و 2"),
        ("1/2 کیلو", "1/2 کیلو"),
    ],
)
def test_tidy_punctuation(raw, tidy):
    assert tidy_punctuation(raw) == tidy


def test_conjunction_after_zwnj_becomes_a_word():
    assert tidy_punctuation("وسایل‌و لوازم") == "وسایل و لوازم"
    assert tidy_punctuation("حمل‌ونقل") == "حمل‌ونقل"  # a compound, not a conjunction


@pytest.mark.parametrize(
    ("raw", "standard"),
    [
        ("دمپائی", "دمپایی"),
        ("روستائیان", "روستاییان"),
        ("خدمات هوائی و دریائی", "خدمات هوایی و دریایی"),
        (f"روستائی{ZWNJ}ها", f"روستایی{ZWNJ}ها"),
        ("گازوئیل", "گازوئیل"),  # a loanword, more letters follow
        ("موزائیک", "موزائیک"),
        ("ارائه", "ارائه"),
        ("جزئی", "جزئی"),  # not after a vowel
        ("پارچه ائی", "پارچه ائی"),  # ه + ای misprinted, left to the spelling fixes
    ],
)
def test_standard_spelling(raw, standard):
    assert standard_spelling(raw) == standard
