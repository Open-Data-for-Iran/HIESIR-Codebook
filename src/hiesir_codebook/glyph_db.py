"""Glyph-outline -> character database for repairing broken ToUnicode maps.

Some questionnaire PDFs (1395, 1396, 1399, 1402) embed the B Nazanin / Lotus /
Zar fonts with a wrong ToUnicode table ("بخش" extracts as "لاوش").  The glyph
outlines themselves are intact and identical to those in PDFs whose text
extracts correctly, so we hash each glyph's outline and look the character up
in a database built from the clean PDFs.

Build (or rebuild) the database with::

    uv run python -m hiesir_codebook.build_glyph_db
"""

from __future__ import annotations

import collections
import hashlib
import io
import json
import logging
from functools import lru_cache
from pathlib import Path

import pymupdf
from fontTools.pens.recordingPen import RecordingPen
from fontTools.ttLib import TTFont

from .utils import canonical

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


def build(pdf_paths: list[Path]) -> dict[str, str]:
    votes: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for path in pdf_paths:
        doc = pymupdf.open(path)
        hashes: dict[int, list[str | None]] = {}
        for page in doc:
            fonts = {f[3].split("+", 1)[-1]: f[0] for f in page.get_fonts()}
            for span in page.get_texttrace():
                xref = fonts.get(span["font"])
                if xref is None:
                    continue
                if xref not in hashes:
                    hashes[xref] = font_outline_hashes(doc.extract_font(xref)[3])
                hs = hashes[xref]
                for code, gid, _o, _b in span["chars"]:
                    if 0 <= gid < len(hs) and hs[gid] and 0x20 < code != 0xFFFD:
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


@lru_cache(maxsize=1)
def load() -> dict[str, str]:
    try:
        return json.loads(DB_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
