from hiesir_codebook.correction.check import Label, check, known, read_labels, write_report
from hiesir_codebook.correction.spelling import Lexicon
from hiesir_codebook.utils import ZWNJ

LEX = Lexicon(
    {"سایر": 6_000_000, "حق": 9_000_000, "بیمه": 3_000_000, "سر": 9_000_000, "و": 1, "صورت": 9_000_000}
)


def _check(rows):
    return {(f.kind, f.find): f for f in check([Label(y, k, t) for y, k, t in rows], LEX)}


def test_known_forms():
    assert known("بیمه", LEX)
    assert known(f"بیمه{ZWNJ}های", LEX)  # plural with ZWNJ
    assert known("بیمهای", LEX)  # suffix without ZWNJ
    assert known(f"حق{ZWNJ}بیمه", LEX)  # compound of known words
    assert not known("سایرحق", LEX)


def test_unknown_word_and_other_years():
    got = _check(
        [(1383, "item 1", "سایرحق بیمه"), (1386, "item 1", "سایر حق بیمه"), (1384, "item 2", "بتادین")]
    )
    s = got[("unknown", "سایرحق")]
    assert (s.other, s.years, s.other_years) == ("سایر حق", {1383}, {1386})
    assert got[("unknown", "بتادین")].other == ""


def test_variant_across_years():
    rows = [(y, "item 1", "سر و صورت") for y in (1390, 1391, 1392)] + [(1402, "item 1", "سرو صورت")]
    s = _check(rows)[("variant", "سرو")]
    assert (s.other, s.years, s.other_years) == ("سر و", {1402}, {1390, 1391, 1392})


def test_without_hazm_only_variants():
    rows = [Label(1383, "item 1", "سایرحق"), Label(1386, "item 1", "سایر حق")]
    assert {f.kind for f in check(rows, None)} == {"variant"}


def test_report_round_trip(tmp_path):
    (tmp_path / "questionnaire_1390.csv").write_text(
        "section,kind,level,code,sub,expenditure_code,description\n1,item,5,0111,11,011111,سایرحق\n",
        encoding="utf-8-sig",
    )
    labels = read_labels(tmp_path)
    assert [(lb.year, lb.key) for lb in labels] == [(1390, "item 011111")]
    write_report(check(labels, LEX), tmp_path / "out.csv")
    assert "unknown,سایرحق" in (tmp_path / "out.csv").read_text(encoding="utf-8-sig")
