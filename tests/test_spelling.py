from pathlib import Path

import pytest

from hiesir_codebook.correction.correct import LabelFix, apply
from hiesir_codebook.correction.spelling import (
    Decision,
    Lexicon,
    accepted,
    load_decisions,
    suggest,
    write_suggestions,
    years_text,
)
from hiesir_codebook.utils import ZWNJ

ROOT = Path(__file__).resolve().parents[1]

# a small stand-in for hazm's word list (word -> frequency)
LEX = Lexicon(
    {
        "سبزی": 600_000,
        "کتاب": 13_000_000,
        "تن": 900_000,
        "تنها": 90_000_000,
        "کالا": 2_000_000,
        "جاده": 3_000_000,
        "جاد": 0,
        "پودر": 24_000_000,
        "پیاز": 300_000,
        "در": 200_000_000,
        "درو": 3_600_000,
        "پنجره": 2_200_000,
        "انواع": 15_000_000,
        "رادیو": 9_000_000,
        "تازه": 5_000_000,
        "هزینه": 9_000_000,
        "تعمیر": 2_400_000,
        "سایر": 6_000_000,
        "پارچه": 2_000_000,
        "ثبت": 5_000_000,
        "نام": 9_000_000,
        f"ثبت{ZWNJ}نام": 800_000,
        "خریداری": 900_000,
        "شده": 90_000_000,
        f"خریداری{ZWNJ}شده": 190_000,
        "اجاره": 2_000_000,
        "بها": 3_000_000,
        "بهای": 1_000_000,
        f"اجاره{ZWNJ}بها": 600_000,
        "قطب": 500_000,
        f"حشره{ZWNJ}کش": 90_000,
        "کیف": 2_000_000,
        "وکیف": 1_000,
        "نما": 2_000_000,
        f"قطب{ZWNJ}نما": 90_000,
        "سر": 9_000_000,
        "سرو": 400_000,
        "صورت": 9_000_000,
    }
)


def _find(labels):
    return {s.find: s for s in suggest(((1, x) for x in labels), LEX)}


def test_plural():
    got = _find(["سبزیهای تازه", "کتابهای درسی", "کت تنها", "کالاهای بادوام"])
    s = got["سبزیهای"]
    assert (s.replace, s.kind, s.apply) == (f"سبزی{ZWNJ}های", "plural", True)
    assert got["کتابهای"].replace == f"کتاب{ZWNJ}های"
    assert "تنها" not in got  # a word of its own
    assert "کالاهای" not in got  # ا does not join the next letter: no ZWNJ needed


def test_spaced_plural_after_a_non_joining_letter_joins():
    got = _find(["سبزی های تازه", "کالا های بادوام"])
    assert got["سبزی های"].replace == f"سبزی{ZWNJ}های"
    assert got["کالا های"].replace == "کالاهای"


def test_he_ye():
    s = _find(["حمل و نقل جادهای"])["جادهای"]
    assert (s.replace, s.kind, s.apply) == (f"جاده{ZWNJ}ای", "he_ye", False)


def test_broken_word():
    s = _find(["ا نواع پنیر"])["ا نواع"]
    assert (s.replace, s.kind, s.apply) == ("انواع", "broken", True)


def test_glued_words():
    got = _find(["پودرپیاز", "تعمیرپنجره"])
    assert (got["پودرپیاز"].replace, got["پودرپیاز"].kind) == ("پودر پیاز", "glued")
    assert got["تعمیرپنجره"].replace == "تعمیر پنجره"


def test_glued_cut_follows_the_questionnaires():
    # درو + پنجره and در + و + پنجره are both words; the labels write در و پنجره elsewhere
    got = _find(["هزینه دروپنجره", "تعمیر در و پنجره", "تعمیر در و پنجره"])
    assert got["دروپنجره"].replace == "در و پنجره"


def test_stray_zwnj_before_a_suffix_stays():
    got = _find([f"هزینه{ZWNJ}هایتعمیر"])
    assert got[f"هزینه{ZWNJ}هایتعمیر"].replace == f"هزینه{ZWNJ}های تعمیر"


def test_zwnj_joined_phrase_is_split_per_zwnj():
    # a phrase joined with ZWNJs repeats every year; only the ZWNJ between two
    # pieces the questionnaires write as a token of their own stays (house style)
    labels = [f"هزینه{ZWNJ}تعمیر{ZWNJ}پنجره"] * 5 + [f"پودر{ZWNJ}پیاز"] * 5
    got = _find(labels)
    assert got[f"هزینه{ZWNJ}تعمیر{ZWNJ}پنجره"].replace == "هزینه تعمیر پنجره"
    assert f"پودر{ZWNJ}پیاز" not in got
    got = _find([*labels, f"تعمیر{ZWNJ}پنجره"] + [f"تعمیر{ZWNJ}پنجره"] * 4)
    assert got[f"هزینه{ZWNJ}تعمیر{ZWNJ}پنجره"].replace == f"هزینه تعمیر{ZWNJ}پنجره"


def test_years_follow_the_form_written_most():
    def years(labels):
        keys = ["item 1"] * len(labels)
        return {s.find: s for s in suggest(labels, LEX, keys=keys) if s.kind == "years"}

    # the other years write known words: applied on its own
    got = years([(1383, "هزینه پودرپیازی"), (1386, "هزینه پودر پیازی"), (1387, "هزینه پودر پیازی")])
    s = got["پودرپیازی"]
    assert (s.replace, s.apply, s.years) == ("پودر پیازی", True, {1383})
    # two spellings of known words (درو / در و): only suggested
    got = years([(1383, "تعمیر درو پنجره"), (1386, "تعمیر در و پنجره"), (1387, "تعمیر در و پنجره")])
    assert (got["درو"].replace, got["درو"].apply) == ("در و", False)
    # the rest of the labels differs: the other year still shows how to write the word
    got = years([(1383, "هزینه پودرپیازی کهنه"), (1386, "انواع پودر پیازی")])
    assert (got["پودرپیازی"].replace, got["پودرپیازی"].apply) == ("پودر پیازی", True)
    # without keys, no years suggestions
    assert all(s.kind != "years" for s in suggest([(1383, "پودرپیازی"), (1386, "پودر پیازی")], LEX))


def test_typo_is_only_suggested():
    s = _find(["رایو"])["رایو"]
    assert (s.replace, s.kind, s.apply) == ("رادیو", "typo", False)


def test_known_words_are_left_alone():
    assert _find(["سبزی تازه", "انواع کتاب"]) == {}


def test_years_and_uses():
    s = {x.find: x for x in suggest([(1383, "سبزیهای تازه"), (1384, "سبزیهای تازه"), (1390, "سبزیهای")], LEX)}
    assert (s["سبزیهای"].uses, len(s["سبزیهای"].labels), years_text(s["سبزیهای"].years)) == (
        3,
        2,
        "1383-1384 1390",
    )


def test_decisions_override_apply():
    rows = [
        {"find": "a", "replace": "A", "apply": "yes"},
        {"find": "b", "replace": "B", "apply": "yes"},
        {"find": "c", "replace": "C", "apply": "no"},
        {"find": "dd", "replace": "D", "apply": "no"},
        {"find": "e", "replace": "E", "apply": "no"},
    ]
    decisions = [
        Decision("b", "reject", "", "wrong"),
        Decision("c", "confirm", "", "right"),
        Decision("dd", "change", "X", "better"),
        Decision("gone", "reject", "", "no longer suggested"),
    ]
    pairs, stale = accepted(rows, decisions)
    assert pairs == [("dd", "X"), ("a", "A"), ("c", "C")]  # longest first; e not applied
    assert [d.find for d in stale] == ["gone"]


def test_decisions_need_a_reason(tmp_path):
    path = tmp_path / "d.csv"
    path.write_text("find,decision,replace,reason\nx,reject,,\n", encoding="utf-8")
    with pytest.raises(ValueError, match="reason"):
        load_decisions(path)
    path.write_text("find,decision,replace,reason\nx,change,,because\n", encoding="utf-8")
    with pytest.raises(ValueError, match="replace"):
        load_decisions(path)


def test_suggestions_come_after_the_spelling_list():
    row = {"section": "1", "kind": "item", "description": "سبزیهای  تازه", "code": "", "sub": ""}
    spelling = [LabelFix("تازه", "تازه و خشک", "word", None, "test")]
    sugg = [LabelFix("سبزیهای", f"سبزی{ZWNJ}های", "word", None, "spelling suggestion")]
    (out,) = apply(1, [row], [], Path(), spelling, None, sugg, None)
    assert out["description"] == f"سبزی{ZWNJ}های تازه و خشک"


def test_written_file_round_trips(tmp_path):
    path = tmp_path / "s.csv"
    write_suggestions(suggest([(1, "سبزیهای تازه")], LEX), path)
    text = path.read_text(encoding="utf-8-sig").splitlines()
    assert text[0] == "find,replace,kind,apply,uses,labels,years,evidence,example"
    assert text[1].startswith(f"سبزیهای,سبزی{ZWNJ}های,plural,yes,1,1,1,")


def test_curated_decisions_are_not_stale():
    from hiesir_codebook.correction.spelling import load_suggestions

    _, stale = accepted(
        load_suggestions(ROOT / "output" / "2_corrected" / "spelling_suggestions.csv"),
        load_decisions(ROOT / "curated" / "2_corrected" / "spelling_suggestions.csv"),
    )
    assert not stale, [d.find for d in stale]


def test_suggestions_are_up_to_date(tmp_path):
    """output/2_corrected/spelling_suggestions.csv must match the labels and
    hazm; if this fails, run
    `uv run --python 3.13 --extra hazm python -m hiesir_codebook.correction.spelling`."""
    pytest.importorskip("hazm")
    from hiesir_codebook.correction import spelling

    spelling.main(["--extracted", str(ROOT / "output" / "1_extracted"), "--out", str(tmp_path / "s.csv")])
    assert (tmp_path / "s.csv").read_bytes() == (
        ROOT / "output" / "2_corrected" / "spelling_suggestions.csv"
    ).read_bytes()


def test_spaced_ye_and_prefix():
    got = _find(["پارچه ای", "پرداخت می شود"])
    assert (got["پارچه ای"].replace, got["پارچه ای"].kind, got["پارچه ای"].apply) == (
        f"پارچه{ZWNJ}ای",
        "he_ye",
        True,
    )
    assert (got["می شود"].replace, got["می شود"].kind) == (f"می{ZWNJ}شود", "prefix")


def test_compound_hazm_knows_applies():
    s = _find(["هزینه ثبت نام"])["ثبت نام"]
    assert (s.replace, s.kind, s.apply) == (f"ثبت{ZWNJ}نام", "compound", True)
    # with a suffix on the second word, whose stem makes the compound
    s = _find(["برآورد اجاره بهای ماهانه"])["اجاره بهای"]
    assert (s.replace, s.apply) == (f"اجاره{ZWNJ}بهای", True)
    # followed by a spaced plural suffix: one suggestion, the suffix joined too
    s = _find(["انواع قطب نما ها"])["قطب نما ها"]
    assert (s.replace, s.apply) == (f"قطب{ZWNJ}نماها", True)


def test_compound_hazm_lists_only_with_zwnj():
    # hazm lists حشره‌کش, never حشرهکش: applied when the questionnaires write it apart
    s = {x.find: x for x in suggest([(1, "حشرهکش")], LEX, ["حشرهکش", "سم حشره کش"])}["حشرهکش"]
    assert (s.replace, s.kind, s.apply) == (f"حشره{ZWNJ}کش", "compound", True)
    s = {x.find: x for x in suggest([(1, "حشرهکش")], LEX, ["حشرهکش"])}["حشرهکش"]
    assert s.apply is False  # never written apart: their joined style, left to review


def test_glued_and_before_a_common_word_hazm_also_lists():
    s = _find(["کفش وکیف"])["وکیف"]  # hazm lists وکیف, but کیف is far more common
    assert (s.replace, s.kind, s.apply) == ("و کیف", "glued", True)


def test_compound_verb_phrase_applies_only_when_printed_joined():
    s = {x.find: x for x in suggest([(1, "کالای خریداری شده")], LEX)}["خریداری شده"]
    assert (s.replace, s.apply) == (f"خریداری{ZWNJ}شده", False)  # Persian writes it apart
    printed = ["کالای خریداری شده", f"خریداری{ZWNJ}شده"]
    s = {x.find: x for x in suggest([(1, "کالای خریداری شده")], LEX, printed)}["خریداری شده"]
    assert s.apply is True  # the questionnaires print it joined: their style


def test_no_compound_across_a_conjunction():
    assert "سر و" not in _find(["سر و صورت"])  # not سرو


def test_glued_word_before_a_spaced_plural():
    s = _find(["سایرهزینه های تازه"])["سایرهزینه های"]
    assert (s.replace, s.kind) == (f"سایر هزینه{ZWNJ}های", "glued")
