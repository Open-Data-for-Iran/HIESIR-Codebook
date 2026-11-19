"""Turn PDF pages into logical-order Persian text lines.

The questionnaire PDFs store glyphs in visual (left-to-right) order, often as
Arabic presentation forms, and some (e.g. 1382) use subset fonts without a
ToUnicode map.  We therefore work at the glyph level:

1. collect every glyph with its bounding box and glyph id (PyMuPDF texttrace),
2. decode glyphs PyMuPDF cannot map to Unicode via their glyph names,
3. group glyphs into visual lines by vertical position,
4. sort each line right-to-left, insert spaces at horizontal gaps and ZWNJs
   where a joining letter is drawn in its final form with no gap,
5. NFKC-normalise (presentation forms -> base letters), unify Arabic/Persian
   letters, and restore numbers, Latin runs and mirrored brackets
   (see :func:`utils.normalize_visual`).
"""

from __future__ import annotations

import io
import re
import unicodedata
from dataclasses import dataclass, field
from functools import cache, lru_cache

import pymupdf
from fontTools.ttLib import TTFont

from . import glyph_db
from .utils import ZWNJ, canonical, is_arabic_letter, joins_next, normalize_visual

# --- glyph-name decoding ----------------------------------------------------

_ARABIC_LETTERS = {
    "hamza": "ء",
    "alefwithmaddaabove": "آ",
    "alefwithhamzaabove": "أ",
    "wawwithhamzaabove": "ؤ",
    "alefwithhamzabelow": "إ",
    "yehwithhamzaabove": "ئ",
    "alef": "ا",
    "beh": "ب",
    "tehmarbuta": "ة",
    "teh": "ت",
    "theh": "ث",
    "jeem": "ج",
    "hah": "ح",
    "khah": "خ",
    "dal": "د",
    "thal": "ذ",
    "reh": "ر",
    "zain": "ز",
    "seen": "س",
    "sheen": "ش",
    "sad": "ص",
    "dad": "ض",
    "tah": "ط",
    "zah": "ظ",
    "ain": "ع",
    "ghain": "غ",
    "feh": "ف",
    "qaf": "ق",
    "kaf": "ک",
    "arabickaf": "ک",
    "keheh": "ک",
    "lam": "ل",
    "meem": "م",
    "noon": "ن",
    "heh": "ه",
    "waw": "و",
    "alefmaksura": "ی",
    "yeh": "ی",
    "farsiyeh": "ی",
    "peh": "پ",
    "tcheh": "چ",
    "jeh": "ژ",
    "gaf": "گ",
    "lamwithalef": "لا",
    "lamwithalefwithmaddaabove": "لآ",
    "lamwithalefwithhamzaabove": "لأ",
}
_FORM_SUFFIX = re.compile(r"(isolated|final|initial|medial)$")
_SIMPLE_NAMES = {
    "space": " ",
    "quotedbl": '"',
    "parenleft": "(",
    "parenright": ")",
    "period": ".",
    "colon": ":",
    "comma": ",",
    "hyphen": "-",
    "slash": "/",
    "endash": "-",
    "arabiccomma": "،",
    "arabicquestionmark": "؟",
    "arabicsemicolon": "؛",
    "arabictatweel": "",
    "tatweel": "",
    "zero": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
}
for _i, _d in enumerate(["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]):
    _SIMPLE_NAMES[f"arabicindicdigit{_d}"] = str(_i)
    _SIMPLE_NAMES[f"persiandigit{_d}"] = str(_i)


def glyph_name_to_text(name: str) -> str | None:
    if name in _SIMPLE_NAMES:
        return _SIMPLE_NAMES[name]
    m = re.fullmatch(r"(?:uni|u)([0-9A-Fa-f]{4,6})", name)
    if m:
        return chr(int(m.group(1), 16))
    base = _FORM_SUFFIX.sub("", name)
    if base in _ARABIC_LETTERS:
        return _ARABIC_LETTERS[base]
    if len(name) == 1:
        return name
    return None


@lru_cache(maxsize=8)
def _open(pdf_path: str) -> pymupdf.Document:
    return pymupdf.open(pdf_path)


@cache
def _font_glyph_names(pdf_path: str, xref: int) -> list[str]:
    """Glyph id -> glyph name for an embedded TrueType font."""
    try:
        buf = _open(pdf_path).extract_font(xref)[3]
        return TTFont(io.BytesIO(buf)).getGlyphOrder()
    except Exception:
        return []


def _undecoded_fonts(pdf_path: str, page: pymupdf.Page) -> dict[str, int]:
    """Font base-name -> xref for page fonts that lack a ToUnicode map."""
    doc = _open(pdf_path)
    out = {}
    for xref, _ext, _typ, basefont, *_ in page.get_fonts():
        if "ToUnicode" not in doc.xref_object(xref):
            out[basefont.split("+", 1)[-1]] = xref
    return out


# --- glyphs and lines ---------------------------------------------------------


@dataclass
class Glyph:
    text: str
    x0: float
    x1: float
    y0: float
    y1: float
    size: float
    ends_word: bool = False  # drawn in a final/isolated contextual form

    @property
    def mid(self) -> float:
        return (self.y0 + self.y1) / 2


@dataclass
class Segment:
    text: str
    x0: float
    x1: float


@dataclass
class Line:
    text: str
    y: float
    x0: float
    x1: float
    glyphs: list[Glyph] = field(default_factory=list, repr=False)
    # pieces of the line separated by wide gaps (different table columns),
    # right-most (first in reading order) first
    segments: list[Segment] = field(default_factory=list, repr=False)


def _page_fonts(page: pymupdf.Page) -> dict[str, int]:
    return {basefont.split("+", 1)[-1]: xref for xref, _e, _t, basefont, *_ in page.get_fonts()}


@cache
def _outline_hashes(pdf_path: str, xref: int) -> list[str | None]:
    try:
        return glyph_db.font_outline_hashes(_open(pdf_path).extract_font(xref)[3])
    except Exception:
        return []


@lru_cache(maxsize=8)
def _broken_fonts(pdf_path: str, threshold: float = 0.005) -> frozenset[int]:
    """Fonts whose ToUnicode map disagrees with the glyph database.

    One pass over the document compares, for every glyph the database knows,
    the character PyMuPDF reports with the character its outline stands for.
    Clean PDFs agree 100%; every font in the broken ones disagrees on >0.8%.
    """
    db = glyph_db.load()
    if not db:
        return frozenset()
    agree: dict[int, int] = {}
    total: dict[int, int] = {}
    for page in _open(pdf_path):
        fonts = _page_fonts(page)
        for span in page.get_texttrace():
            xref = fonts.get(span["font"])
            if xref is None:
                continue
            hs = _outline_hashes(pdf_path, xref)
            for code, gid, _o, _b in span["chars"]:
                if 0 <= gid < len(hs) and hs[gid] in db and 0x20 < code != 0xFFFD:
                    total[xref] = total.get(xref, 0) + 1
                    if canonical(chr(code)) == canonical(db[hs[gid]]):
                        agree[xref] = agree.get(xref, 0) + 1
    return frozenset(x for x, n in total.items() if n >= 20 and 1 - agree.get(x, 0) / n > threshold)


def page_glyphs(pdf_path: str, page_no: int) -> list[Glyph]:
    page = _open(pdf_path)[page_no]
    undecoded = _undecoded_fonts(pdf_path, page)
    fonts = _page_fonts(page)
    broken = _broken_fonts(pdf_path)
    db = glyph_db.load()
    glyphs: list[Glyph] = []
    seen: set[tuple[str, int, int]] = set()
    for span in page.get_texttrace():
        xref = undecoded.get(span["font"])
        names = _font_glyph_names(pdf_path, xref) if xref else []
        fx = fonts.get(span["font"])
        hashes = _outline_hashes(pdf_path, fx) if fx in broken else None
        for code, gid, _origin, bbox in span["chars"]:
            if hashes is not None and gid < 0:
                continue  # extra char of a multi-char (wrong) ToUnicode entry
            if hashes is not None and 0 <= gid < len(hashes) and hashes[gid] in db:
                # broken ToUnicode map: identify the glyph by its outline
                code = ord(db[hashes[gid]][0]) if len(db[hashes[gid]]) == 1 else code
            # 0xFFFD / control chars: PyMuPDF could not map the glyph to Unicode,
            # so fall back to the glyph's name inside the embedded font.
            if (code == 0xFFFD or code < 0x20) and 0 <= gid < len(names):
                t = glyph_name_to_text(names[gid]) or ""
                ends = names[gid].endswith(("final", "isolated"))
            else:
                t = chr(code)
                uname = unicodedata.name(t, "")
                ends = "FINAL FORM" in uname or "ISOLATED FORM" in uname
            if not t.strip():
                continue
            x0, y0, x1, y1 = bbox
            # "fake bold": the same glyph drawn again with a tiny offset
            key = (t, round(x0), round(y1))
            if any((t, key[1] + dx, key[2] + dy) in seen for dx in (-1, 0, 1) for dy in (-1, 0, 1)):
                continue
            seen.add(key)
            glyphs.append(Glyph(t, x0, x1, y0, y1, span["size"], ends))
    return glyphs


def _needs_zwnj(prev: Glyph, cur: Glyph) -> bool:
    """A joining letter drawn in its final form, touching the next letter,
    means the source text had a ZWNJ there (هزینه‌ها)."""
    if not prev.ends_word:
        return False
    a, b = canonical(prev.text), canonical(cur.text)
    return bool(a) and bool(b) and joins_next(a[-1]) and is_arabic_letter(b[0])


def group_lines(
    glyphs: list[Glyph], tol: float = 3.0, gap: float = 0.2, column_gap: float = 2.0
) -> list[Line]:
    rows: list[list[Glyph]] = []
    mids: list[float] = []
    for g in sorted(glyphs, key=lambda g: g.mid):
        if mids and abs(mids[-1] - g.mid) < tol:
            rows[-1].append(g)
        else:
            rows.append([g])
            mids.append(g.mid)
    lines = []
    for row, mid in zip(rows, mids, strict=True):
        row.sort(key=lambda g: -g.x1)
        segs: list[tuple[list[str], list[Glyph]]] = []
        prev = None
        for g in row:
            # digits of one number may be kerned apart ("0 31" for 031)
            word_gap = gap * 3 if prev is not None and prev.text.isdigit() and g.text.isdigit() else gap
            if prev is None or prev.x0 - g.x1 > g.size * column_gap:
                segs.append(([], []))
            elif prev.x0 - g.x1 > g.size * word_gap:
                segs[-1][0].append(" ")
            elif _needs_zwnj(prev, g):
                segs[-1][0].append(ZWNJ)
            segs[-1][0].append(g.text)
            segs[-1][1].append(g)
            prev = g
        segments = [
            Segment(normalize_visual("".join(parts)), min(x.x0 for x in gs), max(x.x1 for x in gs))
            for parts, gs in segs
        ]
        text = " ".join(sg.text for sg in segments)
        lines.append(Line(text, mid, min(g.x0 for g in row), max(g.x1 for g in row), row, segments))
    return lines


# --- page helpers -------------------------------------------------------------


def page_lines(pdf_path: str, page_no: int) -> list[Line]:
    return group_lines(page_glyphs(pdf_path, page_no))


def page_count(pdf_path: str) -> int:
    return len(_open(pdf_path))


@dataclass
class Rule:
    y: float
    x0: float
    x1: float


def page_rules(pdf_path: str, page_no: int, min_width: float = 20) -> list[Rule]:
    """Horizontal table rules drawn on the page (with their horizontal extent)."""
    rules: list[Rule] = []
    for d in _open(pdf_path)[page_no].get_drawings():
        for it in d["items"]:
            if it[0] == "l":
                p, q = it[1], it[2]
                if abs(p.y - q.y) < 1 and abs(p.x - q.x) > min_width:
                    rules.append(Rule((p.y + q.y) / 2, min(p.x, q.x), max(p.x, q.x)))
            elif it[0] == "re":
                r = it[1]
                if r.width > min_width:
                    rules.append(Rule(r.y0, r.x0, r.x1))
                    if r.height >= 2:
                        rules.append(Rule(r.y1, r.x0, r.x1))
    # merge collinear pieces (tables are often drawn one cell border at a time)
    rules.sort(key=lambda r: (round(r.y), r.x0))
    merged: list[Rule] = []
    for r in rules:
        m = merged[-1] if merged else None
        if m and abs(m.y - r.y) < 1.5 and r.x0 <= m.x1 + 3:
            m.x1 = max(m.x1, r.x1)
        else:
            merged.append(Rule(r.y, r.x0, r.x1))
    return merged


@dataclass
class VRule:
    x: float
    y0: float
    y1: float


def page_vrules(pdf_path: str, page_no: int, min_height: float = 8) -> list[VRule]:
    """Vertical table rules (column borders) with their vertical extent."""
    out: list[VRule] = []
    for d in _open(pdf_path)[page_no].get_drawings():
        for it in d["items"]:
            if it[0] == "l":
                p, q = it[1], it[2]
                if abs(p.x - q.x) < 1 and abs(p.y - q.y) > min_height:
                    out.append(VRule(p.x, min(p.y, q.y), max(p.y, q.y)))
            elif it[0] == "re":
                r = it[1]
                if r.width < 2 and r.height > min_height:
                    out.append(VRule(r.x0, r.y0, r.y1))
                elif r.width >= 2 and r.height > min_height:
                    out.extend([VRule(r.x0, r.y0, r.y1), VRule(r.x1, r.y0, r.y1)])
    return out
