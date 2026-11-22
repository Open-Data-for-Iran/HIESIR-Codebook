"""Extract the expenditure questionnaire (code list) from a questionnaire PDF."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from ..utils import OPT_SPACE, collapse_whitespace, has_letters, has_persian
from .pdf_text import Discard, Line, Rule, Segment, VRule, page_count, page_lines, page_rules, page_vrules

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


def _classify(text: str) -> tuple[str, str, str | None, str] | None:
    if SKIP_RE.search(text):
        return None
    # a stray comma inside the code, read right-to-left: "69 312,0" = 0312 69 (1384, 1385)
    text = re.sub(r"^(\d{2}) (\d{3}),(\d)(?= |$)", r"\1 \3\2", text)
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


# how far a table rule may be from the row's text to count as its border
ROW_RULE_GAP = 14


def _row_box(
    e: _Entry, rules: list[Rule], vrules: list[VRule]
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
    if above and top - max(above) < ROW_RULE_GAP:
        top = max(above)
    if below and min(below) - bottom < ROW_RULE_GAP:
        bottom = min(below)
    mid = (top + bottom) / 2
    xs = [v.x for v in vrules if v.y0 - 1 <= mid <= v.y1 + 1]
    left, right = (min(xs), max(xs)) if len(xs) >= 2 and max(xs) - min(xs) > 100 else (None, None)
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

# text inside description cells that is not part of the description:
# field labels and notes listing the allowed "source" codes (e.g. "3 یا 4").
NOT_DESC_RE = re.compile(
    r"^(?:\d ?(?:یا ?\d ?)*|یا ?\d(?: ?یا ?\d)*)$"
    r"|^(?:تعداد افراد بیمه شده|مبلغ وام|محل اخذ ?وام|مبلغ رهن(?: \(ریال\))?)$"
)


def _aligned(seg: Segment, y: float, vrules: list[VRule]) -> bool:
    """Wrapped description lines are right-aligned to their column border.

    Text that ends well before the next vertical rule on its right (a label
    such as "تعداد افراد بیمه شده" or a footnote mark inside the cell) is not
    part of the description.
    """
    borders = [v.x for v in vrules if v.y0 - 2 <= y <= v.y1 + 2 and v.x > seg.x1 - 1]
    if not borders:
        return True
    return min(borders) - seg.x1 < 15


# why text was left out (the "reason" column of reports/extraction_<year>.csv)
DROP_UNALIGNED = "text not aligned to its column border (a label inside the cell?)"
DROP_NO_CODE = "text with no code line within 30 pt"
DROP_CODE_TAIL = "code continuation with no header to join"
DROP_PAGE_NUMBER = "two-digit line with no text around it (page number?)"
DROP_STRAY_TWO_DIGIT = "two-digit header with no code below it"
DROP_BEFORE_SECTION = "before the first section heading"


def _page_entries(
    lines: list[Line],
    rules: list[Rule],
    vrules: list[VRule],
    discards: list[Discard] | None = None,
    page: int = -1,
) -> list[_Entry]:
    """Pair code lines with the wrapped description lines of the same table row.

    Only the right-most segment of each visual line is used (code and
    description columns); text further left belongs to other columns (units,
    footnote marks).  A wrapped line belongs to the nearest code line that is
    not separated from it by a rule crossing the description column.

    Text with letters that is left out for lack of a place is recorded in
    ``discards`` (labels and notes that ``NOT_DESC_RE`` / ``SKIP_RE`` name are
    left out on purpose and are not).
    """

    def drop(y: float, reason: str, text: str) -> None:
        if discards is not None:
            discards.append(Discard(page, y, reason, text))

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
            coded.append(_Entry(ln, *c))
        elif has_letters(seg.text) and not SKIP_RE.search(seg.text) and not NOT_DESC_RE.match(seg.text):
            loose.append(seg)
            loose_lines.append(ln)
    for seg, ln in zip(loose, loose_lines, strict=True):
        y = ln.y
        if not _aligned(seg, y, vrules):
            drop(y, DROP_UNALIGNED, seg.text)
            continue
        cands = [
            e
            for e in coded
            if abs(e.line.y - y) <= 30 and seg.x1 < e.line.segments[0].x1 - 10  # left of the code column
        ]
        same_row = [
            e for e in cands if not _separated(rules, y, e.line.y, seg.x1 - 2, e.line.segments[0].x1 - 10)
        ]
        if not cands:
            drop(y, DROP_NO_CODE, seg.text)
            continue
        # no candidate in the same table row: the text overflowed its cell,
        # so fall back to the nearest code line
        e = min(same_row or cands, key=lambda e: abs(e.line.y - y))
        (e.before if y < e.line.y else e.after).append(seg)
        e.lines.append(ln)
    for text, y in code_tails:
        # a header code list split over two lines ("و03123 M" / "03124 M"):
        # prefer an adjacent code-only header, else the header just above
        heads = [e for e in coded if e.kind == "header" and abs(y - e.line.y) <= 25 and not e.desc]
        heads = heads or [e for e in coded if e.kind == "header" and 0 < y - e.line.y <= 30]
        if heads:
            e = min(heads, key=lambda e: abs(y - e.line.y))
            e.code = f"{e.code} {text}"
        else:
            drop(y, DROP_CODE_TAIL, text)
    # a two-digit code line with no text anywhere around it is a page number
    page_numbers = [
        e for e in coded if re.fullmatch(r"\d{2}", e.code) and not (e.desc or e.before or e.after)
    ]
    for e in page_numbers:
        drop(e.line.y, DROP_PAGE_NUMBER, e.line.text)
    return _join_code_heads([e for e in coded if e not in page_numbers])


def _join_code_heads(entries: list[_Entry]) -> list[_Entry]:
    """Join a header code list split over two code lines, the connector
    ending the first ("06312 و" / "06313 M" with the description between
    them, 1391-1394; "01193و چاشنی‌ها ..." / "01192", 1386), with the
    nearest header line; the description is the text of both, top first."""
    for h in [e for e in entries if e.kind == "head"]:
        near = [e for e in entries if e.kind == "header" and abs(e.line.y - h.line.y) <= 25]
        h.kind = "header"
        if not near:
            continue
        other = min(near, key=lambda e: abs(e.line.y - h.line.y))
        upper, lower = sorted((h, other), key=lambda e: e.line.y)
        texts = [s.text for e in (upper, lower) for s in (*e.before, Segment(e.desc, 0, 0), *e.after)]
        upper.desc, upper.before, upper.after = collapse_whitespace(" ".join(texts)), [], []
        upper.code = f"{h.code}, {other.code}"
        upper.lines.extend([lower.line, *lower.lines])
        lower.kind = "absorbed"
    return [e for e in entries if e.kind != "absorbed"]


def _join_split_codes(
    entries: list[_Entry], discards: list[Discard] | None = None, page: int = -1
) -> list[_Entry]:
    """COICOP scheme: repair entries whose code is just two digits.

    In a tall cell the sub-code can sit on the first line and the code
    centred a line below ("13 رادیولوژی، ..." / "0623", 1391-1394): join them
    into one item.  Any other two-digit header (other than the investment
    groups 33/34) is stray text from outside the tables and is dropped.
    """
    out = []
    for e in entries:
        if e.kind != "header" or not re.fullmatch(r"\d{2}", e.code) or e.code.startswith("3"):
            out.append(e)
            continue
        code = next(
            (
                f
                for f in entries
                if f.kind == "header" and re.fullmatch(r"\d{3,4}", f.code) and 0 < f.line.y - e.line.y <= 20
            ),
            None,
        )
        if code is None:
            if discards is not None:
                discards.append(Discard(page, e.line.y, DROP_STRAY_TWO_DIGIT, e.line.text))
            continue
        e.kind, e.sub, e.code = "item", e.code, code.code
        e.after.extend([*code.before, *([Segment(code.desc, 0, 0)] if code.desc else []), *code.after])
        e.lines.extend([code.line, *code.lines])
        code.kind = "absorbed"
        out.append(e)
    return [e for e in out if e.kind != "absorbed"]


def extract(
    pdf_path: str | Path, old_scheme: bool = False, discards: list[Discard] | None = None
) -> list[Row]:
    """Rows (sections, group headers, items) of the expenditure part.

    The expenditure part runs from the first "بخش 1" heading to "قسمت چهارم"
    (income).  A heading whose number drops below the current one also ends
    it (e.g. the income "بخش 3" in 1382).

    What is left out inside the expenditure pages, and glyphs that could not
    be read, are appended to ``discards`` (pages before it are not).
    """
    pdf = str(pdf_path)
    rows: list[Row] = []
    section: int | None = None
    for p in range(page_count(pdf)):
        unread: list[Discard] = []  # glyphs; kept only for the expenditure pages
        lines = page_lines(pdf, p, unread)
        if section is not None and any(PART4_RE.match(x.text) for x in lines):
            break
        headings = [(ln.y, SECTION_RE.match(ln.text)) for ln in lines]
        headings = [(y, int(m.group(1)), m.group(2).strip()) for y, m in headings if m]
        if section is None and not any(num == 1 for _y, num, _t in headings):
            continue
        if discards is not None:
            discards.extend(unread)
        body = [ln for ln in lines if not SECTION_RE.match(ln.text)]
        rules, vrules = page_rules(pdf, p), page_vrules(pdf, p)
        entries = _page_entries(body, rules, vrules, discards, p)
        if not old_scheme:
            entries = _join_split_codes(entries, discards, p)
        # walk entries and headings top-to-bottom; a heading switches the section
        events = [(y, 0, h) for y, *h in headings] + [(e.line.y, 1, e) for e in entries]
        for _y, is_entry, ev in sorted(events, key=lambda t: (t[0], t[1])):
            if not is_entry:
                num, title = ev
                if section is not None and num < section:
                    return _finish(rows, old_scheme)
                if num != section:
                    section = num
                    rows.append(Row("section", num, "", None, title, p))
                continue
            if section is None:
                if discards is not None:
                    discards.append(Discard(p, ev.line.y, DROP_BEFORE_SECTION, ev.line.text))
                continue
            e = ev
            div = _division(e.code)
            if not old_scheme and div and section < div <= 12 and not headings:
                # the section heading on this page is an image; infer it from the
                # COICOP division of the codes (sections 1-12 = divisions 01-12)
                section = div
                rows.append(Row("section", div, "", None, "", p))
            desc = " ".join([*(s.text for s in e.before), e.desc, *(s.text for s in e.after)])
            desc = FOOTNOTE_TAIL_RE.sub("", collapse_whitespace(desc))
            top, bottom, left, right = _row_box(e, rules, vrules)
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
    return _finish(rows, old_scheme)


def _finish(rows: list[Row], old_scheme: bool) -> list[Row]:
    rows = _merge_page_breaks(rows)
    _assign_levels(rows, old_scheme)
    return rows


def _merge_page_breaks(rows: list[Row]) -> list[Row]:
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
            continue
        out.append(r)
    return out


# 1382 and earlier use the pre-COICOP 3+2 digit code scheme
LAST_OLD_SCHEME_YEAR = 1382


def pdf_path(year: int, data: Path) -> Path:
    """``<data>/pdf/Questionnaire <year>.pdf``, or the file under its published
    name (``questionnaire_<year>.pdf``, as the GitHub release holds it) when
    only that one is there."""
    local = data / "pdf" / f"Questionnaire {year}.pdf"
    published = data / "pdf" / f"questionnaire_{year}.pdf"
    return published if published.exists() and not local.exists() else local


def extract_year(year: int, data: Path, discards: list[Discard] | None = None) -> list[Row]:
    """Extract one survey year from ``<data>/pdf/Questionnaire <year>.pdf``."""
    return extract(pdf_path(year, data), old_scheme=year <= LAST_OLD_SCHEME_YEAR, discards=discards)


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
