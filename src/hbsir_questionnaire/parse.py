"""Extract the expenditure questionnaire (code list) from a questionnaire PDF."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .pdf_text import Line, Rule, Segment, VRule, page_count, page_lines, page_rules, page_vrules
from .utils import OPT_SPACE, collapse_whitespace, has_letters, has_persian

_CODE = r"(?:[AM] ?)?\d{2,5}(?: ?[AM])?"
ITEM_RE = re.compile(rf"^(\d{{2}}) ({_CODE})(?: (.*))?$")
HEADER_RE = re.compile(rf"^({_CODE}(?: ?(?:و|,|،) ?{_CODE})*)(?: (.*))?$")
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
    m = ITEM_RE.match(text)
    if m and len(re.sub(r"\D", "", m.group(2))) in (3, 4):
        return "item", m.group(2), m.group(1), (m.group(3) or "").strip()
    m = HEADER_RE.match(text)
    if m and m.group(2) and has_persian(m.group(2)):
        return "header", m.group(1), None, m.group(2).strip()
    if m and not m.group(2) and len(re.sub(r"\D", "", m.group(1))) >= 3:
        return "header", m.group(1), None, ""  # code only; description wraps
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
_CODE_ONLY = re.compile(rf"^(?:\d{{2}} )?{_CODE}(?: ?(?:و|,|،) ?{_CODE})*$")


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


def _page_entries(lines: list[Line], rules: list[Rule], vrules: list[VRule]) -> list[_Entry]:
    """Pair code lines with the wrapped description lines of the same table row.

    Only the right-most segment of each visual line is used (code and
    description columns); text further left belongs to other columns (units,
    footnote marks).  A wrapped line belongs to the nearest code line that is
    not separated from it by a rule crossing the description column.
    """
    coded: list[_Entry] = []
    loose: list[Segment] = []
    loose_y: list[float] = []
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
            loose_y.append(ln.y)
    for seg, y in zip(loose, loose_y, strict=True):
        if not _aligned(seg, y, vrules):
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
            continue
        # no candidate in the same table row: the text overflowed its cell,
        # so fall back to the nearest code line
        e = min(same_row or cands, key=lambda e: abs(e.line.y - y))
        (e.before if y < e.line.y else e.after).append(seg)
    for text, y in code_tails:
        # a header code list split over two lines ("و03123 M" / "03124 M"):
        # prefer an adjacent code-only header, else the header just above
        heads = [e for e in coded if e.kind == "header" and abs(y - e.line.y) <= 25 and not e.desc]
        heads = heads or [e for e in coded if e.kind == "header" and 0 < y - e.line.y <= 30]
        if heads:
            e = min(heads, key=lambda e: abs(y - e.line.y))
            e.code = f"{e.code} {text}"
    return coded


def extract(pdf_path: str | Path, old_scheme: bool = False) -> list[Row]:
    """Rows (sections, group headers, items) of the expenditure part.

    The expenditure part runs from the first "بخش 1" heading to "قسمت چهارم"
    (income).  A heading whose number drops below the current one also ends
    it (e.g. the income "بخش 3" in 1382).
    """
    pdf = str(pdf_path)
    rows: list[Row] = []
    section: int | None = None
    for p in range(page_count(pdf)):
        lines = page_lines(pdf, p)
        if section is not None and any(PART4_RE.match(x.text) for x in lines):
            break
        headings = [(ln.y, SECTION_RE.match(ln.text)) for ln in lines]
        headings = [(y, int(m.group(1)), m.group(2).strip()) for y, m in headings if m]
        if section is None and not any(num == 1 for _y, num, _t in headings):
            continue
        body = [ln for ln in lines if not SECTION_RE.match(ln.text)]
        entries = _page_entries(body, page_rules(pdf, p), page_vrules(pdf, p))
        # walk entries and headings top-to-bottom; a heading switches the section
        events = [(y, 0, h) for y, *h in headings] + [(e.line.y, 1, e) for e in entries]
        for _y, is_entry, ev in sorted(events, key=lambda t: (t[0], t[1])):
            if not is_entry:
                num, title = ev
                if section is not None and num < section:
                    _assign_levels(rows, old_scheme)
                    return rows
                if num != section:
                    section = num
                    rows.append(Row("section", num, "", None, title, p))
                continue
            if section is None:
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
            rows.append(Row(e.kind, section, normalize_code(e.code), e.sub, desc, p))
    _assign_levels(rows, old_scheme)
    return rows


# 1382 and earlier use the pre-COICOP 3+2 digit code scheme
LAST_OLD_SCHEME_YEAR = 1382


def pdf_path(year: int, data: Path) -> Path:
    return data / "pdf" / f"Questionnaire {year}.pdf"


def extract_year(year: int, data: Path) -> list[Row]:
    """Extract one survey year from ``<data>/pdf/Questionnaire <year>.pdf``."""
    return extract(pdf_path(year, data), old_scheme=year <= LAST_OLD_SCHEME_YEAR)


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
            n = len(re.sub(r"\D", "", r.code.split(",")[0]))
            if old_scheme or (n <= 3 and r.code.startswith("3")):
                r.level = n
            else:
                r.level = n - 1
