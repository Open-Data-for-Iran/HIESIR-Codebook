"""Glyph-outline -> character database for repairing broken ToUnicode maps.

Some questionnaire PDFs (1395, 1396, 1399, 1402) embed the B Nazanin / Lotus /
Zar fonts with a wrong ToUnicode table ("بخش" extracts as "لاوش").  The glyph
outlines themselves are intact and identical to those in PDFs whose text
extracts correctly, so we hash each glyph's outline and look the character up
in a database built from the clean PDFs.

The database keeps the letter form: a medial or initial glyph is stored as its
presentation form (ﻬ, ﮔ), a final one as its final form (ﻪ) and an isolated one
as the plain letter (ه), as the clean PDFs' shaped fonts map them.  So a plain
letter from the database is an isolated glyph, which the ZWNJ recovery needs
(میوه‌گیری).  Letters are only learnt from shaped fonts, which keeps that true.

Build (or rebuild) the database with::

    uv run python -m hiesir_codebook.extraction.build_glyph_db
"""

from __future__ import annotations

import collections
import hashlib
import io
import json
import logging
import unicodedata
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path

import pymupdf
from fontTools.pens.recordingPen import RecordingPen
from fontTools.ttLib import TTFont

from ..utils import canonical

# The embedded font subsets have harmless table quirks ("3 extra bytes in
# post.stringData array", "'created' timestamp out of range") that fontTools
# reports as warnings; keep real errors only.
logging.getLogger("fontTools").setLevel(logging.ERROR)

DB_PATH = Path(__file__).parent / "data" / "glyph_db.json"


def font_outline_hashes(buf: bytes) -> list[str | None]:
    """Glyph id -> short hash of the glyph outline (None for empty glyphs)."""
    try:
        tt = TTFont(io.BytesIO(buf))
        gs = tt.getGlyphSet()
        order = tt.getGlyphOrder()
    except Exception:
        return []
    out: list[str | None] = []
    for name in order:
        pen = RecordingPen()
        try:
            gs[name].draw(pen)
        except Exception:
            out.append(None)
            continue
        out.append(hashlib.md5(repr(pen.value).encode()).hexdigest()[:16] if pen.value else None)
    return out


def page_fonts(page: pymupdf.Page) -> dict[str, list[int]]:
    """Font name (as a text span names it: without the subset prefix) -> xrefs.

    One name often stands for two subsets of a font on the same page (1397:
    ``HKOEMJ+BNazanin``, a few digits, and ``HKOEMI+BNazanin``, the letters),
    so a span's font is chosen among them with :func:`span_font`.
    """
    out: dict[str, list[int]] = {}
    for xref, _ext, _typ, basefont, *_ in page.get_fonts():
        out.setdefault(basefont.split("+", 1)[-1], []).append(xref)
    return out


def span_font(
    fonts: dict[str, list[int]], span: dict, hashes: Callable[[int], list[str | None]]
) -> int | None:
    """The xref of a text span's font: of the fonts with its name, the one
    that has outlines for the span's glyph ids (a subset holds only the glyphs
    it uses).  ``hashes`` gives a font's outline hashes by xref."""
    xrefs = fonts.get(span["font"], [])
    if len(xrefs) <= 1:
        return xrefs[0] if xrefs else None

    def drawn(xref: int) -> int:
        hs = hashes(xref)
        return sum(1 for _c, gid, _o, _b in span["chars"] if 0 <= gid < len(hs) and hs[gid])

    return max(xrefs, key=drawn)


def is_presentation_form(code: int) -> bool:
    return 0xFB50 <= code <= 0xFDFF or 0xFE70 <= code <= 0xFEFF


def shaped_fonts(doc: pymupdf.Document, min_forms: int = 20) -> frozenset[str]:
    """Fonts whose ToUnicode map gives each letter form its own code (ﻏ ﻐ ...).

    Such a font maps its isolated glyphs to the plain letter (غ), so there a
    plain letter is an isolated one.  In fonts that map every form to the plain
    letter (1395, 1402) a plain letter says nothing about its form.
    """
    forms: collections.Counter = collections.Counter()
    for page in doc:
        for span in page.get_texttrace():
            forms[span["font"]] += sum(is_presentation_form(code) for code, *_ in span["chars"])
    return frozenset(f for f, n in forms.items() if n >= min_forms)


def _is_letter(ch: str) -> bool:
    return unicodedata.name(ch, "").startswith("ARABIC LETTER")


def build(pdf_paths: list[Path]) -> dict[str, str]:
    votes: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for path in pdf_paths:
        doc = pymupdf.open(path)
        shaped = shaped_fonts(doc)
        hashes: dict[int, list[str | None]] = {}

        def of(xref: int, doc=doc, hashes=hashes) -> list[str | None]:
            if xref not in hashes:
                hashes[xref] = font_outline_hashes(doc.extract_font(xref)[3])
            return hashes[xref]

        for page in doc:
            fonts = page_fonts(page)
            for span in page.get_texttrace():
                xref = span_font(fonts, span, of)
                if xref is None:
                    continue
                hs = of(xref)
                for code, gid, _o, _b in span["chars"]:
                    if not (0 <= gid < len(hs) and hs[gid] and 0x20 < code != 0xFFFD):
                        continue
                    if span["font"] not in shaped and _is_letter(chr(code)):
                        continue  # its plain letters may be any form
                    votes[hs[gid]][chr(code)] += 1
    db = {}
    for h, c in votes.items():
        # majority by base letter, keeping the most common exact form of it
        by_base = collections.Counter()
        for ch, n in c.items():
            by_base[canonical(ch)] += n
        best = by_base.most_common(1)[0][0]
        db[h] = max((ch for ch in c if canonical(ch) == best), key=c.__getitem__)
    return db


class GlyphDBError(RuntimeError):
    """The glyph database is missing or does not match the PDFs' glyphs."""


_REBUILD = "uv run python -m hiesir_codebook.extraction.build_glyph_db"


@lru_cache(maxsize=1)
def load() -> dict[str, str]:
    """The database (outline hash -> character).  Raises GlyphDBError when it
    is missing or empty: without it, broken fonts extract as garbage."""
    try:
        db = json.loads(DB_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise GlyphDBError(f"no glyph database at {DB_PATH}; rebuild it with `{_REBUILD}`") from None
    if not db:
        raise GlyphDBError(f"the glyph database {DB_PATH} is empty; rebuild it with `{_REBUILD}`")
    return db


# The share of a PDF's glyph outlines the database knows: 0.94-1.0 in the
# 1383-1403 PDFs, 0.82 in 1382 (fonts the database is not built from).  Far
# below means the outline hashes no longer match the database, for example
# after a fontTools change to RecordingPen's output.
MIN_COVERAGE = 0.5


def check_coverage(known: int, outlines: int, what: str, minimum: float = MIN_COVERAGE) -> None:
    """Raise GlyphDBError when the database knows under ``minimum`` of the
    ``outlines`` glyphs of a PDF (``what`` names it in the message)."""
    if outlines >= 1000 and known / outlines < minimum:
        raise GlyphDBError(
            f"the glyph database knows {known} of {outlines} glyph outlines in {what}"
            f" ({known / outlines:.1%}, expected at least {minimum:.0%}): the outline hashes"
            f" have probably changed (fontTools?); rebuild it with `{_REBUILD}` and check"
            " that the repaired years (1395, 1396, 1399, 1402) still extract the same"
        )
