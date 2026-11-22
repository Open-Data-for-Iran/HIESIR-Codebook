import io

import pytest
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen

from hiesir_codebook.extraction import glyph_db
from hiesir_codebook.extraction.glyph_db import GlyphDBError, check_coverage, font_outline_hashes


def _font() -> bytes:
    """A TrueType font with an empty .notdef and one square glyph."""
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder([".notdef", "square"])
    fb.setupCharacterMap({0x41: "square"})
    pen = TTGlyphPen(None)
    pen.moveTo((100, 0))
    pen.lineTo((100, 500))
    pen.lineTo((600, 500))
    pen.lineTo((600, 0))
    pen.closePath()
    fb.setupGlyf({".notdef": TTGlyphPen(None).glyph(), "square": pen.glyph()})
    fb.setupHorizontalMetrics({".notdef": (500, 0), "square": (700, 100)})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "Test", "styleName": "Regular"})
    fb.setupOS2()
    fb.setupPost()
    buf = io.BytesIO()
    fb.save(buf)
    return buf.getvalue()


def test_outline_hash_is_stable():
    """The database is keyed by these hashes: if this one changes (a fontTools
    upgrade changing RecordingPen's output), every lookup misses and the
    repaired years (1395, 1396, 1399, 1402) extract as garbage.  Rebuild the
    database (build_glyph_db) and update the hash here only together."""
    assert font_outline_hashes(_font()) == [None, "8386cabdb353a06a"]


def test_unreadable_font_has_no_hashes():
    assert font_outline_hashes(b"not a font") == []


def test_database_is_shipped():
    db = glyph_db.load()
    assert len(db) > 500
    assert all(len(ch) == 1 for ch in db.values())


def test_missing_database_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(glyph_db, "DB_PATH", tmp_path / "glyph_db.json")
    glyph_db.load.cache_clear()
    try:
        with pytest.raises(GlyphDBError, match="no glyph database"):
            glyph_db.load()
        (tmp_path / "glyph_db.json").write_text("{}", encoding="utf-8")
        glyph_db.load.cache_clear()
        with pytest.raises(GlyphDBError, match="empty"):
            glyph_db.load()
    finally:
        monkeypatch.undo()
        glyph_db.load.cache_clear()


def test_coverage():
    check_coverage(944, 1000, "1384")  # the lowest COICOP year
    check_coverage(815, 1000, "1382")  # fonts the database is not built from
    check_coverage(0, 999, "a few glyphs")  # too few to judge
    with pytest.raises(GlyphDBError, match="knows 5 of 70000"):
        check_coverage(5, 70000, "1403")


def test_span_font_picks_the_subset_that_draws_it():
    """1397 embeds BNazanin twice on a page: a few digits (xref 455) and the
    letters (xref 474); a span's glyph ids are drawn in only one of them."""
    from hiesir_codebook.extraction.glyph_db import span_font

    outlines = {455: ["a", None, None, None], 474: [None, "b", "c", "d"]}
    fonts = {"BNazanin": [474, 455], "BZar": [341]}
    span = lambda name, *gids: {"font": name, "chars": [(0x41, g, None, None) for g in gids]}  # noqa: E731
    assert span_font(fonts, span("BNazanin", 1, 2, 3), outlines.get) == 474
    assert span_font(fonts, span("BNazanin", 0), outlines.get) == 455
    assert span_font(fonts, span("BZar", 7), outlines.get) == 341  # one font of that name
    assert span_font(fonts, span("Arial", 1), outlines.get) is None
