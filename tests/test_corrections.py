from pathlib import Path

import polars as pl
import pytest

from hiesir_codebook import SUPPORTED_YEARS
from hiesir_codebook.correction.corrections import (
    HeaderException,
    check_rows,
    check_structure,
    load_corrections,
    load_header_exceptions,
)

ROOT = Path(__file__).resolve().parents[1]


def _row(section, kind, code, sub="", desc="شرح"):
    return {
        "section": str(section),
        "kind": kind,
        "code": code,
        "sub": sub,
        "expenditure_code": f"{code}{sub}".replace(" ", "") if kind == "item" else "",
        "description": desc,
    }


GOOD = [
    _row(1, "section", "", desc="خوراکی"),
    _row(1, "header", "0111"),
    _row(1, "item", "0111", "11"),
    _row(1, "item", "0111", "12"),
    _row(1, "header", "01121, 01122"),
    _row(1, "item", "0112", "11"),
    _row(1, "item", "0112", "21"),
    _row(2, "section", "", desc=""),  # a heading printed as an image has no title
    _row(2, "header", "0211"),
    _row(2, "item", "0211", "11"),
]


def _frame(rows) -> pl.DataFrame:
    return pl.DataFrame(rows, schema=dict.fromkeys(rows[0], pl.String))


def _kinds(rows, exceptions=()):
    return sorted(f.kind for f in check_rows(1400, _frame(rows), list(exceptions)))


def test_clean_questionnaire():
    assert _kinds(GOOD) == []


@pytest.mark.parametrize(
    ("change", "kind"),
    [
        (lambda rs: rs.insert(4, _row(1, "item", "0111", "11")), "duplicate"),
        (lambda rs: rs.insert(4, _row(1, "item", "0111", "05")), "sub_order"),
        (lambda rs: rs.append(_row(1, "item", "0119", "11")), "section_order"),
        (lambda rs: rs[2].update(description=" "), "empty"),
        (lambda rs: rs[2].update(expenditure_code="011112"), "bad_code"),
        (lambda rs: rs.insert(4, _row(1, "item", "0113", "11")), "outside_header"),
    ],
)
def test_each_finding(change, kind):
    rows = [dict(r) for r in GOOD]
    change(rows)
    assert kind in _kinds(rows)


def test_header_exception():
    rows = [*GOOD[:4], _row(1, "item", "0113", "11"), *GOOD[4:]]
    exc = HeaderException("0111", "0113", frozenset({1400}), "as printed")
    used = set()
    assert check_rows(1400, _frame(rows), [exc], used) == []
    assert used == {exc}
    other_year = HeaderException("0111", "0113", frozenset({1399}), "as printed")
    assert _kinds(rows, [other_year]) == ["outside_header"]


def test_corrected_questionnaires_are_sound():
    """output/2_corrected/ has no structural problem, and every accepted
    header exception is still needed."""
    exceptions = load_header_exceptions()
    used = set()
    assert check_structure(SUPPORTED_YEARS, ROOT / "output" / "2_corrected", exceptions, used) == []
    assert [e for e in exceptions if e not in used] == []


def test_extracted_findings_are_corrected():
    """What the check finds in output/1_extracted/ are print errors that
    curated/2_corrected/corrections.csv fixes."""
    fixed = {(c.year, c.expenditure_code) for c in load_corrections()}
    findings = check_structure(SUPPORTED_YEARS, ROOT / "output" / "1_extracted")
    assert findings, "the 1386 print errors are expected here"
    unfixed = [
        f
        for f in findings
        if (f.year, f.code) not in fixed
        # an item under a header whose code is corrected (1386: 062 M -> 0562 M)
        and (f.year, f.detail.removeprefix("under header ")) not in fixed
    ]
    assert unfixed == []
