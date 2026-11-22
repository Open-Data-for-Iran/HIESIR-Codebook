"""The text layer: glyphs -> lines (spaces, ZWNJs, columns) and table rules,
on synthetic glyphs and a PDF drawn here, so no questionnaire PDF is needed."""

import pymupdf
import pytest

from hiesir_codebook.extraction.pdf_text import (
    Glyph,
    Rule,
    VRule,
    _needs_zwnj,
    group_lines,
    page_rules,
    page_vrules,
)
from hiesir_codebook.utils import ZWNJ

SIZE = 10.0  # font size: the gaps below are in tenths of it


def _glyphs(*spec, y: float = 100.0) -> list[Glyph]:
    """Glyphs in reading order (right to left), each 10 pt wide.

    ``spec`` alternates glyph text and the gap (points) to the next glyph on
    its left; a text ending in "$" is drawn in its final / isolated form.
    """
    out, x1 = [], 500.0
    for i, item in enumerate(spec):
        if i % 2:
            x1 -= item
            continue
        ends = item.endswith("$")
        out.append(Glyph(item.rstrip("$"), x1 - 10, x1, y - 5, y + 5, SIZE, ends))
        x1 -= 10
    return out


def _text(glyphs: list[Glyph]) -> str:
    (line,) = group_lines(glyphs)
    return line.text


@pytest.mark.parametrize(
    ("gap", "text"),
    [
        (0.2, "بن"),  # letters inside a word sit within 0.02 em
        (1.4, "بن"),  # 0.14 em: still one word (0.12 broke پزشک before the tuning)
        (1.6, "ب ن"),  # 0.16 em: a space (1402 sets spaces at 0.16-0.20)
        (2.5, "ب ن"),
    ],
)
def test_word_gap(gap, text):
    assert _text(_glyphs("ب", gap, "ن")) == text


def test_kerned_digits_stay_one_number():
    # digits get three times the word gap: "0 31" printed for 031
    assert _text(_glyphs("1", 0.3 * SIZE, "3", 0.3 * SIZE, "0")) == "031"
    assert " " in _text(_glyphs("1", 0.5 * SIZE, "3", 0, "0"))


def test_column_gap_splits_segments():
    (line,) = group_lines(_glyphs("ب", 0, "ن", 2.1 * SIZE, "م"))
    assert [s.text for s in line.segments] == ["بن", "م"]  # right-most first
    assert line.segments[0].x0 > line.segments[1].x1
    assert line.text == "بن م"
    (line,) = group_lines(_glyphs("ب", 1.9 * SIZE, "م"))
    assert len(line.segments) == 1


@pytest.mark.parametrize(
    ("spec", "text"),
    [
        (("ه$", 0, "گ"), f"ه{ZWNJ}گ"),  # میوه‌گیری: a final heh touching the next letter
        (("ه", 0, "گ"), "هگ"),  # medial form: the letters join
        (("ا$", 0, "گ"), "اگ"),  # alef never joins the next letter: no ZWNJ needed
        (("ه$", 2, "گ"), "ه گ"),  # a real gap is a space, not a ZWNJ
        (("ه$", 0, "1"), "ه1"),  # only before a letter
    ],
)
def test_zwnj(spec, text):
    assert _text(_glyphs(*spec)) == text


def test_needs_zwnj_reads_letter_forms():
    heh, gaf = _glyphs("ه$", 0, "گ")
    assert _needs_zwnj(heh, gaf)
    assert not _needs_zwnj(gaf, heh)


def test_lines_group_by_height():
    glyphs = [*_glyphs("ب", y=100), *_glyphs("ن", y=102.5), *_glyphs("م", y=120)]
    lines = group_lines(glyphs[::-1])
    assert [ln.text for ln in lines] == ["بن", "م"]  # top to bottom
    assert lines[0].y < lines[1].y


@pytest.fixture
def ruled_pdf(tmp_path):
    """A page with a table drawn the way the questionnaires draw them."""
    path = tmp_path / "ruled.pdf"
    doc = pymupdf.open()
    page = doc.new_page()
    page.draw_line((100, 50), (200, 50))  # one rule drawn one cell at a time
    page.draw_line((202, 50), (300, 50))
    page.draw_line((10, 60), (25, 60))  # too short to be a rule
    page.draw_rect(pymupdf.Rect(100, 100, 300, 120))  # a cell: two rules, two borders
    page.draw_line((400, 10), (400, 90))  # a column border
    page.draw_line((450, 10), (450, 15))  # too short to be one
    doc.save(path)
    return str(path)


def test_page_rules(ruled_pdf):
    rules = sorted(page_rules(ruled_pdf, 0), key=lambda r: r.y)
    assert rules == [Rule(50, 100, 300), Rule(100, 100, 300), Rule(120, 100, 300)]


def test_page_vrules(ruled_pdf):
    vrules = sorted(page_vrules(ruled_pdf, 0), key=lambda v: v.x)
    assert vrules == [VRule(100, 100, 120), VRule(300, 100, 120), VRule(400, 10, 90)]
