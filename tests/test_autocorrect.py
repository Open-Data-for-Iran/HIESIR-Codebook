"""Correction step 3: the automatic fixes from hazm's word list."""

from pathlib import Path

import pytest

from hiesir_codebook import csv_io
from hiesir_codebook.correction import autocorrect
from hiesir_codebook.correction.autocorrect import (
    Lexicon,
    find_fixes,
    glued_vav,
    joined_plural,
    spaced_suffix,
)

ROOT = Path(__file__).resolve().parents[1]

# known: met in the corpus or given a part of speech; listed only: bare headwords
LEX = Lexicon(
    freq={
        "یخ": 714221,
        "نخ": 437077,
        "الک": 109007,
        "ویخ": 0,
        "سنگی": 0,
        "ورنی": 0,
        "رنی": 0,
        "وام": 900,
        "پلاستیک": 627087,
        "کالا": 2212284,
        "پارچه": 1000,
        "ورود": 15401712,
        "رود": 223000773,
        "لایی": 32101,
        "ولا": 2250020,
        "نمایش": 12602746,
        "پودر": 24000151,
        "تن": 5000000,
        "تنها": 90000000,
        "سالن": 1810894,
        "سیب‌زمینی": 300000,
        "وب": 0,
        "بها": 2000000,
    },
    words={
        "یخ",
        "نخ",
        "الک",
        "وام",
        "پلاستیک",
        "کالا",
        "پارچه",
        "ورود",
        "رود",
        "لایی",
        "ولا",
        "نمایش",
        "پودر",
        "تن",
        "تنها",
        "سالن",
        "سیب‌زمینی",
        "وب",
        "بها",
    },
)


@pytest.mark.parametrize(
    ("word", "fixed"),
    [
        ("ویخ", "و یخ"),  # listed only, its rest a word
        ("ونخ", "و نخ"),  # not listed, its rest a word
        ("وسنگی", "و سنگی"),  # not listed, its rest listed
        ("ورنی", None),  # listed, its rest only listed: no higher
        ("وام", None),  # a word of its own
        ("وپلاستیکی", "و پلاستیکی"),  # its rest a known word + ی
        ("وکالاهای", "و کالاهای"),  # + های
        ("وپارچه‌ای", "و پارچه‌ای"),  # + ای, after a ZWNJ
        ("ورودی", None),  # ورود + ی and رود + ی: a tie keeps it
        ("ولایی", "و لایی"),  # ولا + یی, but لایی is a word itself
        ("یخ", None),  # no و
        ("و", None),
    ],
)
def test_glued_vav(word, fixed):
    fix = glued_vav(word, LEX)
    assert (fix.replace if fix else None) == fixed


@pytest.mark.parametrize(
    ("word", "suffix", "fixed"),
    [
        ("نمایش", "های", "نمایش‌های"),
        ("پارچه", "ای", "پارچه‌ای"),  # ای after ه
        ("پودر", "های", "پودرهای"),  # no ZWNJ after ر
        ("کالا", "ها", "کالاها"),  # nor after ا
        ("نمایش", "ای", None),  # ای only after ه
        ("تن", "ها", None),  # تنها is a word of its own
        ("رنی", "ها", None),  # not a known word
    ],
)
def test_spaced_suffix(word, suffix, fixed):
    fix = spaced_suffix(word, suffix, LEX)
    assert (fix.replace if fix else None) == fixed


@pytest.mark.parametrize(
    ("word", "fixed"),
    [
        ("سالنهای", "سالن‌های"),
        ("سالنها", "سالن‌ها"),
        ("سیب‌زمینیها", "سیب‌زمینی‌ها"),  # the last piece of a ZWNJ compound
        ("وامهای", "وام‌های"),
        ("کالاها", None),  # no ZWNJ after ا
        ("تنها", None),  # hazm vouches for it as written
        ("وبهای", None),  # وب + های, or و + بهای
        ("سالن‌های", None),  # already right
    ],
)
def test_joined_plural(word, fixed):
    fix = joined_plural(word, LEX)
    assert (fix.replace if fix else None) == fixed


def test_word_passes_chain():
    """وسالنهای: glued_vav gives و سالنهای, then joined_plural سالن‌های."""
    found = {f.fix.find: f.fix.replace for f in find_fixes([(1383, "اجاره وسالنهای ورزشی")], LEX)}
    assert found == {"وسالنهای": "و سالنهای", "سالنهای": "سالن‌های"}


def test_spaced_suffix_after_a_glued_vav():
    """The pair rule reads the label as the word rules leave it: ونمایش های
    gives و نمایش (glued_vav) and نمایش‌های (spaced_suffix)."""
    found = {f.fix.find: f.fix.replace for f in find_fixes([(1383, "فیلم ونمایش های سینما")], LEX)}
    assert found == {"ونمایش": "و نمایش", "نمایش های": "نمایش‌های"}


def test_find_fixes_counts_uses_and_years():
    labels = [
        (1383, "ماهی تازه ویخ زده"),
        (1384, "ماهی تازه ویخ زده"),
        (1384, "خلال ونخ دندان"),
        (1390, "وام"),
    ]
    found = {f.fix.find: f for f in find_fixes(labels, LEX)}
    assert set(found) == {"ویخ", "ونخ"}
    assert (found["ویخ"].uses, found["ویخ"].years) == (2, {1383, 1384})
    assert found["ونخ"].example == "خلال ونخ دندان"


def test_write_and_load(tmp_path):
    path = tmp_path / "hazm.csv"
    autocorrect.write_fixes(find_fixes([(1383, "ماهی ویخ زده")], LEX), path)
    assert csv_io.read(path)[0] | {"evidence": ""} == {
        "find": "ویخ",
        "replace": "و یخ",
        "rule": "glued_vav",
        "uses": "1",
        "years": "1383",
        "evidence": "",
        "example": "ماهی ویخ زده",
    }
    (fx,) = autocorrect.load_fixes(path)
    assert (fx.find, fx.replace, fx.match) == ("ویخ", "و یخ", "word")


def test_curated_words_need_a_reason(tmp_path):
    path = tmp_path / "words.csv"
    csv_io.write(path, ["word", "reason"], [{"word": "والک", "reason": ""}])
    with pytest.raises(ValueError, match="reason"):
        autocorrect.load_words(path)


def test_hazm_fixes_are_up_to_date():
    """output/2_corrected/autocorrect/hazm.csv is what the rules find now; if
    this fails, run `uv run python -m hiesir_codebook.correction.autocorrect`."""
    from hiesir_codebook import hazm_data
    from hiesir_codebook.correction.correct import labels_for_autocorrect

    if not (hazm_data.HAZM_DIR / "words.dat").exists():
        pytest.skip("hazm data not downloaded (uv run hiesir-codebook hazm download)")
    found = find_fixes(labels_for_autocorrect(), autocorrect.hazm_lexicon(), autocorrect.protected_finds())
    assert [(f.fix.find, f.fix.replace) for f in found] == [
        (r["find"], r["replace"]) for r in csv_io.read(autocorrect.HAZM_FIXES)
    ]


# --- glued_words: the cutter ---------------------------------------------------

CUT_LEX = Lexicon(
    freq={
        "پودر": 24000151,
        "پیاز": 5000000,
        "لباس": 4270916,
        "زیر": 90000000,
        "اطو": 200000,
        "کش": 2740051,
        "کشی": 0,
        "ترک": 3471389,
        "بند": 39900928,
        "مؤسسات": 900000,
    },
    words={"پودر", "پیاز", "لباس", "زیر", "اطو", "کش", "ترک", "بند", "مؤسسات"},
    stems=frozenset({"کش", "بند"}),
)


def _cutter(*labels):
    return autocorrect.Cutter(CUT_LEX, autocorrect.Labels.of(labels))


def test_glued_words_cuts_two_common_words():
    fix = autocorrect.glued_words("پودرپیاز", CUT_LEX, _cutter("ادویه، پودرپیاز"))
    assert fix.replace == "پودر پیاز"


def test_glued_words_keeps_a_compound_with_a_verb_stem():
    """اطو + کشی and ترک + بند are compounds (کش, بند are present stems)."""
    cutter = _cutter("اطوکشی", "ترکبند")
    assert autocorrect.glued_words("اطوکشی", CUT_LEX, cutter) is None
    assert autocorrect.glued_words("ترکبند", CUT_LEX, cutter) is None


def test_lookups_ignore_hamza():
    assert CUT_LEX.known("موسسات")  # hazm writes مؤسسات


def test_free_parts_leave_a_matched_stretch_to_its_row():
    from hiesir_codebook.correction.spelling import LabelFix

    rows = [LabelFix("سی دی", "سی دی", "word", None, "")]
    assert autocorrect.free_parts("انواع سی دی و نوار", rows) == [
        ("انواع ", True),
        ("سی دی", False),
        (" و نوار", True),
    ]


# --- compound ---------------------------------------------------------------------

COMP_LEX = Lexicon(
    freq={
        "تخم": 1,
        "مرغ": 1,
        "تخم\u200cمرغ": 1,
        "نمک": 1,
        "سود": 1,
        "نمک\u200cسود": 1,
        "پرداخت": 1,
        "شده": 1,
        "پرداخت\u200cشده": 1,
        "قابل": 1,
        "حمل": 1,
        "قابل\u200cحمل": 1,
    },
    words={"تخم\u200cمرغ", "نمک\u200cسود", "پرداخت\u200cشده", "قابل\u200cحمل"},
)


@pytest.mark.parametrize(
    ("a", "b", "fixed"),
    [
        ("تخم", "مرغ", "تخم\u200cمرغ"),  # hazm lists it, the labels write it joined
        ("نمک", "سود", "نمک‌سود"),  # hazm lists it, though the labels always write it apart
        ("پرداخت", "شده", None),  # a verb phrase
        ("قابل", "حمل", None),  # a head the house style writes apart
    ],
)
def test_compound(a, b, fixed):
    labels = autocorrect.Labels.of(["تخم مرغ", "تخم\u200cمرغ محلی", "نمک سود", "پرداخت شده", "قابل حمل"])
    fix = autocorrect.compound(a, b, COMP_LEX, labels)
    assert (fix.replace if fix else None) == fixed
