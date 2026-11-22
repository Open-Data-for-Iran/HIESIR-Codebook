"""Extract the expenditure questionnaire (code list) from a questionnaire PDF."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from ..utils import OPT_SPACE, collapse_whitespace, has_letters, has_persian
from .layout import CELL_LABELS, DISTANCES, LAST_OLD_SCHEME_YEAR, QUIRKS, Distances, distances
from .pdf_text import (
    Line,
    Note,
    Notes,
    Rule,
    Segment,
    VRule,
    page_count,
    page_lines,
    page_rules,
    page_turned,
    page_vrules,
)
from .pdfs import published_name

_CODE = r"(?:[AM] ?)?\d{2,5}(?: ?[AM])?"
ITEM_RE = re.compile(rf"^(\d{{2}}) ({_CODE})(?: (.*))?$")
HEADER_RE = re.compile(rf"^({_CODE}(?: ?(?:و|,|،) ?{_CODE})*)(?: (.*))?$")
# the first line of a header code list that continues on the next code line:
# "06312 و" (/ "06313 M"), "01193و چاشنی‌ها ..." (/ "01192")
CODE_HEAD_RE = re.compile(rf"^({_CODE}(?: ?(?:و|,|،) ?{_CODE})*) ?(?:و|,|،)(?: (?![AM]? ?\d)(.*))?$")
_SP = OPT_SPACE
SECTION_RE = re.compile(rf"^بخش{_SP}(\d{{1,2}}){_SP}[-–]{_SP}(.*)$")
PART4_RE = re.compile(rf"^قسمت{_SP}چهارم")
SKIP_RE = re.compile(rf"تعداد{_SP}سطر|جمع{_SP}ارقام|^صفحه \d|^کد ?\d|^\d( \d)+$")


@dataclass
class Row:
    kind: str  # "section" | "header" | "item"
    section: int
    code: str  # as printed, normalised (e.g. "0111", "091 A", "01111, 01112")
    sub: str | None
    desc: str
    page: int
    level: int | None = None
    # the row's box on its page, in points from the top-left corner: the table
    # row it is printed in (between its rules, across the table's outer
    # borders), else the extent of its lines; None for rows not in the PDF
    top: float | None = None
    bottom: float | None = None
    left: float | None = None
    right: float | None = None

    @property
    def expenditure_code(self) -> str | None:
        """Code digits as printed followed by the sub-code ('0111' + '11' -> '011111').

        Kept as text: the leading zero of COICOP divisions 01-09 is part of the
        code.  The raw data stores the same code as a number (11111), so compare
        with ``int(expenditure_code)`` when joining.
        """
        if self.kind != "item" or not self.sub:
            return None
        return re.sub(r"\D", "", self.code) + self.sub


@dataclass
class _Entry:
    line: Line
    kind: str
    code: str
    sub: str | None
    desc: str
    before: list[Segment] = field(default_factory=list)
    after: list[Segment] = field(default_factory=list)
    lines: list[Line] = field(default_factory=list)  # wrapped lines, for the row's extent

    def extent(self) -> tuple[float, float]:
        """Top and bottom of the code line and its wrapped lines, in points."""
        glyphs = [g for ln in (self.line, *self.lines) for g in ln.glyphs]
        if not glyphs:
            ys = [ln.y for ln in (self.line, *self.lines)]
            return min(ys) - 5, max(ys) + 5
        return min(g.y0 for g in glyphs), max(g.y1 for g in glyphs)


def normalize_code(raw: str) -> str:
    """'01112 و 01111' -> '01111, 01112'; 'A091'/'091A' -> '091 A'."""
    parts = re.split(r" ?(?:و|,|،) ?", raw.strip())
    out = []
    for p in parts:
        m = re.fullmatch(r"([AM]?)(\d+)([AM]?)", p)
        if not m:
            out.append(p)
            continue
        suffix = m.group(1) or m.group(3)
        out.append(m.group(2) + (f" {suffix}" if suffix else ""))
    out.sort(key=lambda c: re.sub(r"\D", "", c))
    return ", ".join(out)


# a stray comma inside the code, read right-to-left: "69 312,0" = 0312 69 (QUIRKS["stray_comma"])
STRAY_COMMA_RE = re.compile(r"^(\d{2}) (\d{3}),(\d)(?= |$)")


def _classify(text: str) -> tuple[str, str, str | None, str] | None:
    if SKIP_RE.search(text):
        return None
    text = STRAY_COMMA_RE.sub(r"\1 \3\2", text)
    m = ITEM_RE.match(text)
    if m and len(re.sub(r"\D", "", m.group(2))) in (3, 4):
        return "item", m.group(2), m.group(1), (m.group(3) or "").strip()
    m = CODE_HEAD_RE.match(text)
    if m:
        return "head", m.group(1), None, (m.group(2) or "").strip()
    m = HEADER_RE.match(text)
    if m and m.group(2) and has_persian(m.group(2)):
        return "header", m.group(1), None, m.group(2).strip()
    # code only, the description wraps around it; two-digit codes only for
    # the investment groups 33 / 34 (other two-digit lines are sub-codes or noise)
    if m and not m.group(2) and (len(re.sub(r"\D", "", m.group(1))) >= 3 or m.group(1) in ("33", "34")):
        return "header", m.group(1), None, ""
    return None


def _separated(rules: list[Rule], y0: float, y1: float, x_text: float, x_code: float) -> bool:
    """Is there a row rule between y0 and y1?

    Only rules that run from the wrapped text (x_text) across the code column
    (x_code) count: the description column of some years has its own ruled
    grid that wrapped text overflows.
    """
    lo, hi = sorted((y0, y1))
    return any(lo < r.y < hi and r.x0 < x_text and r.x1 > x_code for r in rules)


CODE_TAIL_RE = re.compile(rf"^(?:و|,|،) ?{_CODE}(?: ?(?:و|,|،) ?{_CODE})*$")
_CODE_ONLY = re.compile(rf"^(?:\d{{2}} )?{_CODE}(?: ?(?:و|,|،) ?{_CODE})*(?: ?(?:و|,|،))?$")


def _row_box(
    e: _Entry, rules: list[Rule], vrules: list[VRule], d: Distances = DISTANCES
) -> tuple[float, float, float | None, float | None]:
    """The table row an entry is printed in: (top, bottom, left, right).

    Top and bottom snap to the nearest horizontal rules across the code column
    (else the extent of the text); left and right are the outermost vertical
    rules at the row's height (None when the row has no table around it).
    """
    top, bottom = e.extent()
    xc = e.line.segments[0].x1 - 3  # inside the code column
    across = [r.y for r in rules if r.x0 <= xc <= r.x1]
    above = [y for y in across if y <= top + 1.5]
    below = [y for y in across if y >= bottom - 1.5]
    if above and top - max(above) < d.row_rule:
        top = max(above)
    if below and min(below) - bottom < d.row_rule:
        bottom = min(below)
    mid = (top + bottom) / 2
    xs = [v.x for v in vrules if v.y0 - 1 <= mid <= v.y1 + 1]
    left, right = (min(xs), max(xs)) if len(xs) >= 2 and max(xs) - min(xs) > d.table_width else (None, None)
    return top, bottom, left, right


def _main_segment(ln: Line) -> Segment:
    """The code + description part of a line (right-most columns).

    Codes may sit in their own columns ("11" | "0711" | description), so
    leading code-only segments are joined with the segment that follows.
    """
    segs = ln.segments
    text, x0, x1 = segs[0].text, segs[0].x0, segs[0].x1
    for nxt in segs[1:]:
        if not _CODE_ONLY.match(text):
            break
        text, x0 = f"{text} {nxt.text}", nxt.x0
    return Segment(text, x0, x1)


# trailing notes on the allowed source codes: "... 3 یا 4", "...(سهم دولت) 8"
FOOTNOTE_TAIL_RE = re.compile(r"(?:\s+[1-8](?: ?یا ?[1-8])+|\s+یا ?[1-8]|(?<=\))\s+[1-8])$")

# text inside description cells that is not part of the description: notes
# listing the allowed "source" codes ("3 یا 4") and field labels (layout.CELL_LABELS)
SOURCE_NOTE_RE = re.compile(r"^(?:\d ?(?:یا ?\d ?)*|یا ?\d(?: ?یا ?\d)*)$")
CELL_LABEL_RE = re.compile("^(?:" + "|".join(map(re.escape, CELL_LABELS)) + ")$")
NOT_DESC_RE = re.compile(f"{SOURCE_NOTE_RE.pattern}|{CELL_LABEL_RE.pattern}")


def _aligned(seg: Segment, y: float, vrules: list[VRule], d: Distances = DISTANCES) -> bool:
    """Wrapped description lines are right-aligned to their column border.

    Text that ends well before the next vertical rule on its right (a label
    such as "تعداد افراد بیمه شده" or a footnote mark inside the cell) is not
    part of the description.
    """
    borders = [v.x for v in vrules if v.y0 - 2 <= y <= v.y1 + 2 and v.x > seg.x1 - 1]
    if not borders:
        return True
    return min(borders) - seg.x1 < d.border


# why text was left out (the "reason" column of output/1_extracted/report_<year>.csv)
DROP_UNALIGNED = "text not aligned to its column border (a label inside the cell?)"
DROP_NO_CODE = "text with no code line near it"
DROP_CODE_TAIL = "code continuation with no header to join"
DROP_PAGE_NUMBER = "two-digit line with no text around it (page number?)"
DROP_STRAY_TWO_DIGIT = "two-digit header with no code below it"
DROP_BEFORE_SECTION = "before the first section heading"
DROP_TURNED = "page turned sideways, not read (its text would run vertically)"


def _page_entries(
    lines: list[Line],
    rules: list[Rule],
    vrules: list[VRule],
    notes: Notes | None = None,
    d: Distances = DISTANCES,
) -> list[_Entry]:
    """Pair code lines with the wrapped description lines of the same table row.

    Only the right-most segment of each visual line is used (code and
    description columns); text further left belongs to other columns (units,
    footnote marks).  A wrapped line belongs to the nearest code line that is
    not separated from it by a rule crossing the description column.

    Text with letters that is left out is recorded in ``notes`` (what
    ``SKIP_RE`` names is left out unrecorded), and so are the print quirks
    repaired here (``layout.QUIRKS``).
    """
    notes = notes if notes is not None else Notes()

    coded: list[_Entry] = []
    loose: list[Segment] = []
    loose_lines: list[Line] = []
    code_tails: list[tuple[str, float]] = []
    for ln in sorted(lines, key=lambda x: x.y):
        seg = _main_segment(ln)
        c = _classify(seg.text)
        if CODE_TAIL_RE.match(seg.text):
            code_tails.append((seg.text, ln.y))  # e.g. "و01184" wrapped from a header code
        elif c:
            if STRAY_COMMA_RE.match(seg.text):
                notes.add(ln.y, QUIRKS["stray_comma"].note, seg.text)
            coded.append(_Entry(ln, *c))
        elif not has_letters(seg.text) or SKIP_RE.search(seg.text):
            continue
        elif SOURCE_NOTE_RE.match(seg.text):
            notes.add(ln.y, QUIRKS["source_note"].note, seg.text)
        elif CELL_LABEL_RE.match(seg.text):
            notes.add(ln.y, QUIRKS["cell_label"].note, seg.text)
        else:
            loose.append(seg)
            loose_lines.append(ln)
    for seg, ln in zip(loose, loose_lines, strict=True):
        y = ln.y
        if not _aligned(seg, y, vrules, d):
            notes.add(y, DROP_UNALIGNED, seg.text)
            continue
        cands = [
            e for e in coded if abs(e.line.y - y) <= d.wrap and seg.x1 < e.line.segments[0].x1 - d.code_column
        ]
        same_row = [
            e
            for e in cands
            if not _separated(rules, y, e.line.y, seg.x1 - 2, e.line.segments[0].x1 - d.code_column)
        ]
        if not cands:
            notes.add(y, DROP_NO_CODE, seg.text)
            continue
        # no candidate in the same table row: the text overflowed its cell,
        # so fall back to the nearest code line
        e = min(same_row or cands, key=lambda e: abs(e.line.y - y))
        (e.before if y < e.line.y else e.after).append(seg)
        e.lines.append(ln)
    for text, y in code_tails:
        # a header code list split over two lines ("و03123 M" / "03124 M"):
        # prefer an adjacent code-only header, else the header just above
        heads = [
            e for e in coded if e.kind == "header" and abs(y - e.line.y) <= d.tail_adjacent and not e.desc
        ]
        heads = heads or [e for e in coded if e.kind == "header" and 0 < y - e.line.y <= d.tail_above]
        if heads:
            e = min(heads, key=lambda e: abs(y - e.line.y))
            notes.add(y, QUIRKS["code_tail"].note, f"{e.code} / {text}")
            e.code = f"{e.code} {text}"
        else:
            notes.add(y, DROP_CODE_TAIL, text)
    # a two-digit code line with no text anywhere around it is a page number
    page_numbers = [
        e for e in coded if re.fullmatch(r"\d{2}", e.code) and not (e.desc or e.before or e.after)
    ]
    for e in page_numbers:
        notes.add(e.line.y, DROP_PAGE_NUMBER, e.line.text)
    return _join_code_heads([e for e in coded if e not in page_numbers], notes, d)


def _join_code_heads(
    entries: list[_Entry], notes: Notes | None = None, d: Distances = DISTANCES
) -> list[_Entry]:
    """Join a header code list split over two code lines, the connector
    ending the first ("06312 و" / "06313 M" with the description between
    them, 1391-1394; "01193و چاشنی‌ها ..." / "01192", 1386), with the
    nearest header line; the description is the text of both, top first."""
    for h in [e for e in entries if e.kind == "head"]:
        near = [e for e in entries if e.kind == "header" and abs(e.line.y - h.line.y) <= d.head]
        h.kind = "header"
        if not near:
            continue
        other = min(near, key=lambda e: abs(e.line.y - h.line.y))
        upper, lower = sorted((h, other), key=lambda e: e.line.y)
        texts = [s.text for e in (upper, lower) for s in (*e.before, Segment(e.desc, 0, 0), *e.after)]
        upper.desc, upper.before, upper.after = collapse_whitespace(" ".join(texts)), [], []
        if notes is not None:
            notes.add(upper.line.y, QUIRKS["code_head"].note, f"{h.code} / {other.code}")
        upper.code = f"{h.code}, {other.code}"
        upper.lines.extend([lower.line, *lower.lines])
        lower.kind = "absorbed"
    return [e for e in entries if e.kind != "absorbed"]


def _join_split_codes(
    entries: list[_Entry], notes: Notes | None = None, d: Distances = DISTANCES
) -> list[_Entry]:
    """COICOP scheme: repair entries whose code is just two digits.

    In a tall cell the sub-code can sit on the first line and the code
    centred a line below ("13 رادیولوژی، ..." / "0623", 1391-1394): join them
    into one item.  Any other two-digit header (other than the investment
    groups 33/34) is stray text from outside the tables and is dropped.
    """
    notes = notes if notes is not None else Notes()
    out = []
    for e in entries:
        if e.kind != "header" or not re.fullmatch(r"\d{2}", e.code) or e.code.startswith("3"):
            out.append(e)
            continue
        code = next(
            (
                f
                for f in entries
                if f.kind == "header"
                and re.fullmatch(r"\d{3,4}", f.code)
                and 0 < f.line.y - e.line.y <= d.split_code
            ),
            None,
        )
        if code is None:
            notes.add(e.line.y, DROP_STRAY_TWO_DIGIT, e.line.text)
            continue
        notes.add(e.line.y, QUIRKS["split_code"].note, f"{e.code} / {code.code}")
        e.kind, e.sub, e.code = "item", e.code, code.code
        e.after.extend([*code.before, *([Segment(code.desc, 0, 0)] if code.desc else []), *code.after])
        e.lines.extend([code.line, *code.lines])
        code.kind = "absorbed"
        out.append(e)
    return [e for e in out if e.kind != "absorbed"]


def extract(
    pdf_path: str | Path,
    old_scheme: bool = False,
    notes: Notes | None = None,
    d: Distances = DISTANCES,
) -> list[Row]:
    """Rows (sections, group headers, items) of the expenditure part.

    The expenditure part runs from the first "بخش 1" heading to "قسمت چهارم"
    (income).  A heading whose number drops below the current one also ends
    it (e.g. the income "بخش 3" in 1382).

    Pages whose text is turned sideways are skipped (see ``page_turned``): in
    every year they are landscape tables after the expenditure part (income).

    What is left out inside the expenditure pages, the glyphs that could not
    be read and the print quirks repaired are added to ``notes``.  Pages
    before the part are not reported; on the page that ends it, only what is
    above the ending heading.
    """
    notes = notes if notes is not None else Notes()
    pdf = str(pdf_path)
    rows: list[Row] = []
    section: int | None = None
    for p in range(page_count(pdf)):
        if page_turned(pdf, p):
            if section is not None:
                notes.items.append(Note(p, None, DROP_TURNED, ""))
            continue
        page_notes = Notes(p)  # kept once the page is known to be in the part
        lines = page_lines(pdf, p, page_notes)
        if section is not None and any(PART4_RE.match(x.text) for x in lines):
            break
        headings = [(ln.y, SECTION_RE.match(ln.text)) for ln in lines]
        headings = [(y, int(m.group(1)), m.group(2).strip()) for y, m in headings if m]
        if section is None and not any(num == 1 for _y, num, _t in headings):
            continue
        body = [ln for ln in lines if not SECTION_RE.match(ln.text)]
        rules, vrules = page_rules(pdf, p), page_vrules(pdf, p)
        entries = _page_entries(body, rules, vrules, page_notes, d)
        if not old_scheme:
            entries = _join_split_codes(entries, page_notes, d)
        # walk entries and headings top-to-bottom; a heading switches the section
        events = [(y, 0, h) for y, *h in headings] + [(e.line.y, 1, e) for e in entries]
        for _y, is_entry, ev in sorted(events, key=lambda t: (t[0], t[1])):
            if not is_entry:
                num, title = ev
                if section is not None and num < section:
                    # the rest of the page belongs to the next part (income)
                    notes.items.extend(x for x in page_notes.items if x.y is not None and x.y < _y)
                    return _finish(rows, old_scheme, notes)
                if num != section:
                    section = num
                    rows.append(Row("section", num, "", None, title, p))
                continue
            if section is None:
                page_notes.add(ev.line.y, DROP_BEFORE_SECTION, ev.line.text)
                continue
            e = ev
            div = _division(e.code)
            if not old_scheme and div and section < div <= 12 and not headings:
                # the section heading on this page is an image; infer it from the
                # COICOP division of the codes (sections 1-12 = divisions 01-12)
                section = div
                rows.append(Row("section", div, "", None, "", p))
                page_notes.add(e.line.y, QUIRKS["image_heading"].note, f"section {div}")
            desc = " ".join([*(s.text for s in e.before), e.desc, *(s.text for s in e.after)])
            desc = collapse_whitespace(desc)
            tail = FOOTNOTE_TAIL_RE.search(desc)
            if tail:
                page_notes.add(e.line.y, QUIRKS["source_note"].note, tail.group().strip())
                desc = desc[: tail.start()]
            top, bottom, left, right = _row_box(e, rules, vrules, d)
            rows.append(
                Row(
                    e.kind,
                    section,
                    normalize_code(e.code),
                    e.sub,
                    desc,
                    p,
                    top=top,
                    bottom=bottom,
                    left=left,
                    right=right,
                )
            )
        notes.items.extend(page_notes.items)
    return _finish(rows, old_scheme, notes)


def _finish(rows: list[Row], old_scheme: bool, notes: Notes | None = None) -> list[Row]:
    rows = _merge_page_breaks(rows, notes)
    _assign_levels(rows, old_scheme)
    return rows


def _merge_page_breaks(rows: list[Row], notes: Notes | None = None) -> list[Row]:
    """Join an item whose description continues on the next page.

    Some PDFs repeat the code on the next page next to the tail of the text
    ("ملزومات جمع آوری تمبر(... آلبوم تمبر" / "واقلام دیگر)"), which would
    otherwise give two rows with the same code.
    """
    out: list[Row] = []
    for r in rows:
        prev = out[-1] if out else None
        if (
            prev is not None
            and r.kind == prev.kind == "item"
            and (r.section, r.code, r.sub) == (prev.section, prev.code, prev.sub)
            and r.page == prev.page + 1
        ):
            prev.desc = collapse_whitespace(f"{prev.desc} {r.desc}")
            if notes is not None:
                notes.items.append(Note(r.page, r.top, QUIRKS["page_break"].note, f"{r.code} {r.sub}"))
            continue
        out.append(r)
    return out


def pdf_path(year: int, data: Path) -> Path:
    """``<data>/pdf/questionnaire_<year>.pdf``, the name the GitHub release
    gives it (``hiesir-codebook pdfs download`` fetches it)."""
    return data / "pdf" / published_name(year)


def extract_year(year: int, data: Path, notes: Notes | None = None) -> list[Row]:
    """Extract one survey year from its PDF in ``<data>/pdf/``."""
    return extract(
        pdf_path(year, data), old_scheme=year <= LAST_OLD_SCHEME_YEAR, notes=notes, d=distances(year)
    )


def _division(code: str) -> int | None:
    """COICOP division of a code like '0111', 'M054' or '1111' (None if unsure)."""
    digits = re.sub(r"\D", "", code)
    return int(digits[:2]) if len(digits) >= 4 or (len(digits) == 3 and digits[0] in "01") else None


def _assign_levels(rows: list[Row], old_scheme: bool) -> None:
    """Level 2-4 for group headers, 5 for items (as in the manual Excel files).

    COICOP codes (1383+) have one more digit than their depth (011 -> 2,
    0111 -> 3, 01111 -> 4), except the investment groups 33/331 (2, 3).
    The pre-1383 scheme uses 11 -> 2 and 111 -> 3.
    """
    for r in rows:
        if r.kind == "item":
            r.level = 5
        elif r.kind == "header":
            r.level = header_level(r.code, old_scheme)


def header_level(code: str, old_scheme: bool) -> int:
    """The level of a group header from its (first) code; see _assign_levels."""
    n = len(re.sub(r"\D", "", code.split(",")[0]))
    return n if old_scheme or (n <= 3 and code.startswith("3")) else n - 1
