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


def test_compound_applies_only_when_printed_joined():
    printed = ["هزینه ثبت نام", f"ثبت{ZWNJ}نام"]
    s = {x.find: x for x in suggest([(1, "هزینه ثبت نام")], LEX, printed)}["ثبت نام"]
    assert (s.replace, s.kind, s.apply) == (f"ثبت{ZWNJ}نام", "compound", True)
    s = {x.find: x for x in suggest([(1, "هزینه ثبت نام")], LEX, ["هزینه ثبت نام"])}["ثبت نام"]
    assert s.apply is False  # never printed joined: a choice of style left to review


def test_no_compound_across_a_conjunction():
    assert "سر و" not in _find(["سر و صورت"])  # not سرو


def test_glued_word_before_a_spaced_plural():
    s = _find(["سایرهزینه های تازه"])["سایرهزینه های"]
    assert (s.replace, s.kind) == (f"سایر هزینه{ZWNJ}های", "glued")
