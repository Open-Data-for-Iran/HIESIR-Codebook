"""The documentation's diagrams, drawn as inline SVG.

A page asks for one with a marker on a line of its own::

    <!-- diagram: pipeline -->

and scripts/mkdocs_hooks.py puts the drawing there, in the page's language:
the Farsi pages get the same layout mirrored, so it reads right to left.

The drawings follow the editorial rules of diagram-design
(https://github.com/cathrynlavery/diagram-design): every node a distinct idea
and every line carrying information; connectors at right angles only; an
arrow label on a mask, clear of its line; one focal element at most, in the
accent colour; no shadows. Colours and fonts are not written here: each part
has a class (``dg-node``, ``dg-edge``, ``dg-name`` ...), styled in
docs/assets/extra.css from the theme's own colours, so a diagram follows the
light or dark scheme and the site's Persian font. A diagram is drawn at its
own size (``W`` wide, the width of the text column) and scrolls sideways on a
narrow screen rather than shrinking its text.

Each diagram is a function of the language that lays it out in left-to-right
coordinates; :class:`Drawing` mirrors them for Farsi.
"""

from __future__ import annotations

import html
import itertools
import re

W = 680  # the width of the text column on a desktop screen
FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
RTL_FIRST = re.compile(r"^[^A-Za-z؀-ۿ]*[؀-ۿ]")
LINE = {"code": 16, "name": 18, "meta": 16}  # line heights in a node
MONO_EM = 0.62  # width of a monospace character, in em (diagram-design's budget)


def esc(s: str) -> str:
    return html.escape(s, quote=True)


class Drawing:
    """One diagram in one language: shapes in paint order, mirrored for Farsi."""

    def __init__(self, slug: str, lang: str, height: int, title: str, desc: str, width: int = W):
        self.slug, self.lang, self.fa = slug, lang, lang == "fa"
        self.w, self.h, self.title, self.desc = width, height, title, desc
        self.zones: list[str] = []
        self.edges: list[str] = []
        self.labels: list[str] = []
        self.nodes: list[str] = []

    # coordinates: written left to right, mirrored on a Farsi page
    def x(self, x: float, w: float = 0) -> float:
        return self.w - x - w if self.fa else x

    def t(self, en: str, fa: str) -> str:
        return fa if self.fa else en

    def year(self, s: str) -> str:
        """A year or a count: Persian digits on a Farsi page (codes keep theirs)."""
        return s.translate(FA_DIGITS) if self.fa else s

    def text(self, x: float, y: float, s: str, cls: str, align: str = "center") -> str:
        """A line of text centred vertically on y; align is physical (left, center, right)
        in left-to-right coordinates, so it flips with the layout."""
        rtl = bool(RTL_FIRST.match(s))
        if self.fa and align != "center":
            align = "right" if align == "left" else "left"
        anchor = {"center": "middle", "left": "end" if rtl else "start", "right": "start" if rtl else "end"}[
            align
        ]
        return (
            f'<text x="{self.x(x):g}" y="{y:g}" class="{cls}" text-anchor="{anchor}"'
            f' direction="{"rtl" if rtl else "ltr"}" dominant-baseline="central">{esc(s)}</text>'
        )

    def zone(self, x: float, y: float, w: float, h: float, eyebrow: str) -> None:
        """A dashed frame around nodes that belong together, named at its top."""
        self.zones.append(
            f'<rect x="{self.x(x, w):g}" y="{y:g}" width="{w:g}" height="{h:g}" rx="8" class="dg-zone"/>'
        )
        self.zones.append(self.text(x + 12, y + 14, eyebrow, "dg-eyebrow", "left"))

    def node(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        lines: list[tuple[str, str]],
        kind: str = "",
        align: str = "center",
    ) -> None:
        """A box with lines of text, each (class, text): code, name or meta."""
        cls = f"dg-node {kind}".strip()
        self.nodes.append(
            f'<rect x="{self.x(x, w):g}" y="{y:g}" width="{w:g}" height="{h:g}" rx="6" class="{cls}"/>'
        )
        total = sum(LINE[c] for c, _ in lines)
        cy = y + (h - total) / 2
        tx = {"center": x + w / 2, "left": x + 12, "right": x + w - 12}[align]
        for c, s in lines:
            self.nodes.append(self.text(tx, cy + LINE[c] / 2, s, f"dg-{c}", align))
            cy += LINE[c]

    def row(
        self, x: float, y: float, w: float, h: float, code: str, label: str, kind: str = "", col: float = 96
    ):
        """A one-line box: the code at its start and the label in a column after it."""
        cls = f"dg-node {kind}".strip()
        self.nodes.append(
            f'<rect x="{self.x(x, w):g}" y="{y:g}" width="{w:g}" height="{h:g}" rx="6" class="{cls}"/>'
        )
        self.nodes.append(self.text(x + 12, y + h / 2, code, "dg-code", "left"))
        self.nodes.append(self.text(x + 12 + col, y + h / 2, label, f"dg-name {kind}".strip(), "left"))

    def edge(self, points: list[tuple[float, float]], kind: str = "", head: bool = True) -> None:
        """A connector through the points, at right angles only, corners rounded."""
        for (x1, y1), (x2, y2) in itertools.pairwise(points):
            if x1 != x2 and y1 != y2:
                raise ValueError(f"{self.slug}: diagonal segment {(x1, y1)} -> {(x2, y2)}")
        pts = [(self.x(px), py) for px, py in points]
        d = f"M{pts[0][0]:g},{pts[0][1]:g}"
        last = len(pts) - 2
        for i in range(1, len(pts) - 1):
            (ax, ay), (bx, by), (cx, cy) = pts[i - 1], pts[i], pts[i + 1]
            seg_in, seg_out = abs(bx - ax) + abs(by - ay), abs(cx - bx) + abs(cy - by)
            # a corner of radius 8, smaller where a segment is too short to hold it
            k = min(8, seg_in if i == 1 else seg_in / 2, seg_out if i == last else seg_out / 2)
            sx, sy = _toward(bx, by, ax, ay, k)
            ex, ey = _toward(bx, by, cx, cy, k)
            d += f" L{sx:g},{sy:g} Q{bx:g},{by:g} {ex:g},{ey:g}"
        d += f" L{pts[-1][0]:g},{pts[-1][1]:g}"
        cls = f"dg-edge {kind}".strip()
        marker = (
            f' marker-end="url(#{self.slug}-head{"-accent" if "accent" in kind else ""})"' if head else ""
        )
        self.edges.append(f'<path d="{d}" class="{cls}"{marker}/>')

    def label(self, cx: float, cy: float, s: str) -> None:
        """An arrow label centred on (cx, cy), on a mask; keep it clear of the line."""
        size = 12 if self.fa else 10
        w = (len(s) * size * (0.55 if self.fa else MONO_EM + 0.06)) + 10
        w = 4 * round(w / 4)
        h = 18 if self.fa else 14
        self.labels.append(
            f'<rect x="{self.x(cx - w / 2, w):g}" y="{cy - h / 2:g}" width="{w:g}" height="{h}" rx="2"'
            f' class="dg-mask"/>'
        )
        self.labels.append(self.text(cx, cy, s, "dg-label"))

    def svg(self) -> str:
        sid = f"diagram-{self.slug}"
        defs = "".join(
            f'<marker id="{self.slug}-head{suffix}" markerWidth="8" markerHeight="6" refX="7" refY="3"'
            f' orient="auto" markerUnits="userSpaceOnUse"><polygon points="0 0, 8 3, 0 6"'
            f' class="dg-head{cls}"/></marker>'
            for suffix, cls in (("", ""), ("-accent", " accent"))
        )
        body = "\n".join(self.zones + self.edges + self.labels + self.nodes)
        return (
            f'<figure class="diagram" markdown="0">\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" class="dg-{self.lang}" width="{self.w}"'
            f' height="{self.h}"'
            f' viewBox="0 0 {self.w} {self.h}" role="img" aria-labelledby="{sid}-title {sid}-desc">\n'
            f'<title id="{sid}-title">{esc(self.title)}</title>\n<desc'
            f' id="{sid}-desc">{esc(self.desc)}</desc>\n'
            f"<defs>{defs}</defs>\n{body}\n</svg>\n</figure>"
        )


def _toward(x: float, y: float, tx: float, ty: float, k: float) -> tuple[float, float]:
    """The point k along the straight line from (x, y) to (tx, ty)."""
    if tx != x:
        return x + k * (1 if tx > x else -1), y
    return x, y + k * (1 if ty > y else -1)


def bus(
    d: Drawing, x: float, sources: list[tuple[float, float]], targets: list[tuple[float, float]], kind=""
):
    """Sources joined at a vertical bar at x, which goes on to the targets: the shape
    of a change between sets of items (a merge, a split, a regrouping)."""
    ys = [y for _, y in sources + targets]
    for sx, sy in sources:
        d.edge([(sx, sy), (x, sy)], head=False)
    d.edge([(x, min(ys)), (x, max(ys))], kind=f"dg-bus {kind}".strip(), head=False)
    for tx, ty in targets:
        d.edge([(x, ty), (tx, ty)], kind=kind)


# --- the diagrams ------------------------------------------------------------


def pipeline(lang: str) -> Drawing:
    """The stages of the build, and the hand-kept decisions that three of them read."""
    d = Drawing(
        "pipeline",
        lang,
        156,
        d_t(lang, "How the codebook is made", "چگونه ساخته می‌شود"),
        d_t(
            lang,
            "The questionnaire PDFs are extracted as printed, corrected, matched across years and grouped;"
            " the hand-kept decisions in curated/ feed the last three stages.",
            "فایل‌های PDF پرسشنامه‌ها همان‌طور که چاپ شده‌اند استخراج، سپس اصلاح، در طول سال‌ها پیوند و"
            " گروه‌بندی می‌شوند؛ تصمیم‌های دستی پوشه curated/ به سه مرحله آخر می‌رسند.",
        ),
    )
    stages = [
        ("data/pdf/", d.t("Questionnaire|PDFs", "فایل‌های PDF|پرسشنامه")),
        ("1_extracted/", d.t("As printed", "متن چاپی")),
        ("2_corrected/", d.t("As intended", "متن درست")),
        ("3_items/", d.t("Items across|years", "اقلام در طول|سال‌ها")),
        ("4_groups/", d.t("Groups across|years", "گروه‌ها در طول|سال‌ها")),
    ]
    nw, gap, ny, nh = 112, 28, 76, 76
    xs = [4 + i * (nw + gap) for i in range(len(stages))]
    for i, (folder, name) in enumerate(stages):
        d.node(xs[i], ny, nw, nh, [("code", folder)] + [("name", s) for s in name.split("|")])
        if i:
            d.edge([(xs[i - 1] + nw, ny + nh / 2), (xs[i], ny + nh / 2)])
    # curated/: one bar over the stages it feeds, a dashed drop into each
    bx, bw = xs[2], xs[4] + nw - xs[2]
    d.nodes.append(
        f'<rect x="{d.x(bx, bw):g}" y="4" width="{bw}" height="36" rx="6" class="dg-node accent"/>'
    )
    words = d.t("hand decisions, one row each with its reason", "تصمیم‌های دستی، هر یک سطری با دلیلش")
    rtl = "rtl" if d.fa else "ltr"  # curated/ is isolated (LRI ... PDI) so its slash stays at its end
    d.nodes.append(
        f'<text x="{d.x(bx + bw / 2):g}" y="22" text-anchor="middle" direction="{rtl}"'
        f' dominant-baseline="central">'
        f'<tspan class="dg-code">⁦curated/⁩</tspan><tspan class="dg-name"> {esc(words)}</tspan></text>'
    )
    for i in (2, 3, 4):
        d.edge([(xs[i] + nw / 2, 40), (xs[i] + nw / 2, ny)], kind="accent dashed")
    return d


def change_shapes(lang: str) -> Drawing:
    """One example of each change between sets of chains, codes and labels as printed."""
    d = Drawing(
        "change-shapes",
        lang,
        336,
        d_t(lang, "The shapes of a change", "شکل‌های یک تغییر"),
        d_t(
            lang,
            "Four examples: 011837 recoded as 011174 in 1386; two cigarette items merged into one in 1390;"
            " city taxi and car fares split into two items in 1385; two radiology items regrouped into a G"
            " and an NG item"
            " in 1395.",
            "چهار نمونه: تغییر کد 011837 به 011174 در ۱۳۸۶؛ ادغام دو قلم سیگار در یک قلم در ۱۳۹۰؛ تفکیک"
            " کرایه تاکسی"
            " و سواری داخل شهری به دو قلم در ۱۳۸۵؛ بازگروه‌بندی دو قلم رادیولوژی به یک قلم G و یک قلم NG در"
            " ۱۳۹۵.",
        ),
    )
    pw, bw, bh = 332, 148, 60
    one, two = [60], [24, 96]  # box tops: one box, or two

    def panel(px, py, name, shape, year, left, right):
        d.labels.append(d.text(px, py + 8, f"{name} · {shape}", "dg-eyebrow", "left"))
        d.labels.append(d.text(px + pw, py + 8, d.year(year), "dg-meta", "right"))
        ls, rs = (one if len(left) == 1 else two), (one if len(right) == 1 else two)
        for top, (code, label) in zip(ls, left, strict=True):
            d.node(px, py + top, bw, bh, [("code", code)] + [("name", s) for s in label.split("|")])
        for top, (code, label) in zip(rs, right, strict=True):
            d.node(px + pw - bw, py + top, bw, bh, [("code", code)] + [("name", s) for s in label.split("|")])
        src = [(px + bw, py + t + bh / 2) for t in ls]
        dst = [(px + pw - bw, py + t + bh / 2) for t in rs]
        if len(src) == len(dst) == 1:
            d.edge([src[0], dst[0]])
        else:
            bus(d, px + pw / 2, src, dst)

    arrow = "←" if d.fa else "→"

    def shape(a, b):
        return f"{b} {arrow} {a}" if d.fa else f"{a} {arrow} {b}"

    panel(
        0,
        0,
        "recoded",
        shape("1", "1"),
        "1386",
        [("011837", "انواع شیرینی خشک")],
        [("011174", "انواع شیرینی خشک")],
    )
    panel(
        pw + 16,
        0,
        "merged",
        shape("n", "1"),
        "1390",
        [("022111", "انواع سیگار ایرانی|به جز بهمن"), ("022112", "سیگار بهمن")],
        [("022111", "انواع سیگار ایرانی")],
    )
    panel(
        0,
        180,
        "split",
        shape("1", "n"),
        "1385",
        [("073216", "کرایه تاکسی و سواری|داخل شهری")],
        [("073216", "کرایه تاکسی|داخل شهری"), ("073224", "کرایه سواری داخل شهری|(مسافرکش شخصی)")],
    )
    panel(
        pw + 16,
        180,
        "regrouped",
        shape("n", "m"),
        "1395",
        [
            ("062313", "رادیولوژی، سونوگرافی ...|" + d.t("(outpatient)", "(سرپایی)")),
            ("063313", "رادیولوژی، سونوگرافی ...|" + d.t("(hospital)", "(بیمارستانی)")),
        ],
        [("062334", "خدمات رادیولوژی ... G"), ("062335", "خدمات رادیولوژی ... NG")],
    )
    return d


def hamburger(lang: str) -> Drawing:
    """A continuing change keeps one series; a merge ends three series and starts one."""
    d = Drawing(
        "hamburger",
        lang,
        276,
        d_t(lang, "The ready-to-cook hamburger, 1383–1403", "همبرگر آماده برای طبخ، ۱۳۸۳ تا ۱۴۰۳"),
        d_t(
            lang,
            "The hamburger item's label broadens in 1384, a change that keeps one series; in 1389 it absorbs"
            " the cutlet"
            " and steak items, a merge that ends three series and starts one.",
            "عنوان قلم همبرگر در ۱۳۸۴ گسترده‌تر می‌شود، تغییری که یک سری را نگه می‌دارد؛ در ۱۳۸۹ اقلام کتلت"
            " و استیک"
            " را در بر می‌گیرد، ادغامی که سه سری را پایان می‌دهد و یکی را آغاز می‌کند.",
        ),
    )

    def item(x, y, w, h, chain, label, years, kind=""):
        lines = [("code", chain)] + [("name", s) for s in label.split("|")] + [("meta", d.year(years))]
        d.node(x, y, w, h, lines, kind)

    d.zone(0, 0, 372, 124, d.t("one series", "یک سری"))
    item(12, 28, 124, 84, "C-011241-1383", "همبرگر آماده|برای طبخ", "1383")
    item(208, 28, 152, 84, "C-011241-1384", "همبرگر و کباب لقمه|آماده برای طبخ", "1384–1388")
    d.edge([(136, 70), (208, 70)])
    d.label(172, 54, d.t("broadened", "گسترده‌تر"))
    item(12, 136, 348, 64, "C-011242-1383", "کتلت آماده برای طبخ", "1383–1388")
    item(12, 212, 348, 64, "C-011243-1383", "استیک آماده برای طبخ", "1383–1388")
    bus(d, 404, [(360, 70), (360, 168), (360, 244)], [(444, 157)], kind="accent")
    d.label(460, 70, d.t("merged ", "ادغام ") + d.year("1389"))  # beside the top of the bar
    item(444, 115, 236, 84, "C-011241-1389", "همبرگر، کباب لقمه، کتلت|و استیک آماده برای طبخ", "1389–1403")
    return d


def header_levels(lang: str) -> Drawing:
    """The headers above the hamburger item in 1403: section, levels 2 to 4, item."""
    d = Drawing(
        "header-levels",
        lang,
        372,
        d_t(lang, "Header levels above an item, 1403", "سطح‌های سرگروه بالای یک قلم، ۱۴۰۳"),
        d_t(
            lang,
            "Section 1 holds level 2 header 011 (food), which holds level 3 header 0112, 0113 (meat), whose"
            " four level 4"
            " headers include 01124 (ready-to-cook meat), the header of item 011241, the hamburger.",
            "بخش ۱ سرگروه سطح ۲ با کد 011 (مواد خوراکی) را دارد، که سرگروه سطح ۳ با کد 0112, 0113 (گوشت) را"
            " دارد،"
            " که از چهار سرگروه سطح ۴ آن یکی 01124 (گوشت‌های آماده برای طبخ) است، سرگروه قلم 011241، همبرگر.",
        ),
    )
    rows = [  # (level, code, label, kind, gutter)
        (0, "1", "هزینه‌های خوراکی خانوار در ماه گذشته", "", d.t("section", "بخش")),
        (1, "011", "مواد خوراکی", "", d.t("level 2", "سطح ۲")),
        (2, "0112, 0113", "گوشت", "", d.t("level 3", "سطح ۳")),
        (3, "01121, 01122", "گوشت دام", "muted", d.t("level 4", "سطح ۴")),
        (3, "01123", "گوشت پرندگان", "muted", ""),
        (3, "01124", "گوشت‌های آماده برای طبخ", "", ""),
        (4, "011241", "همبرگر، کباب لقمه، کتلت و استیک آماده برای طبخ", "accent", d.t("item", "قلم")),
        (3, "01131, 01132", "ماهی و میگو و فراورده‌های آن", "muted", ""),
    ]
    pitch, h, x0, indent = 48, 36, 96, 28
    for i, (level, code, label, kind, gutter) in enumerate(rows):
        x, y = x0 + level * indent, i * pitch
        if gutter:
            d.labels.append(d.text(2, y + h / 2, gutter, "dg-eyebrow", "left"))
        d.row(x, y, W - x, h, code, label, kind)
    # a parent's trunk drops from its box and turns into its last child; the
    # children before that branch off it
    for i, (level, *_rest) in enumerate(rows):
        stop = next((j for j in range(i + 1, len(rows)) if rows[j][0] <= level), len(rows))
        kids = [j for j in range(i + 1, stop) if rows[j][0] == level + 1]
        if not kids:
            continue
        tx, cx = x0 + level * indent + 14, x0 + (level + 1) * indent
        cys = [j * pitch + h / 2 for j in kids]
        d.edge([(tx, i * pitch + h), (tx, cys[-1]), (cx, cys[-1])], head=False)
        for cy in cys[:-1]:
            d.edge([(tx, cy), (cx, cy)], head=False)
    return d


def clothing_split(lang: str) -> Drawing:
    """The 1389 split of group 0313 into its M and A parts."""
    d = Drawing(
        "clothing-split",
        lang,
        156,
        d_t(lang, "Group 0313 split in 1389", "تفکیک گروه 0313 در ۱۳۸۹"),
        d_t(
            lang,
            "Group 0313, semi-durable clothing, ends in 1388; in 1389 eleven of its twelve items go to 0313"
            " M in"
            " section 3 and one to 0313 A in section 13.",
            "گروه 0313، پوشاک کم‌دوام، در ۱۳۸۸ پایان می‌یابد؛ در ۱۳۸۹ یازده قلم از دوازده قلمش به 0313 M در"
            " بخش ۳"
            " و یکی به 0313 A در بخش ۱۳ می‌رود.",
        ),
    )

    def meta(section, years, items=""):
        s = d.t(f"section {section} · {years}", f"بخش {section} · {years}") + (
            d.t(f" · {items} items", f" · {items} قلم") if items else ""
        )
        return ("meta", d.year(s))

    d.node(
        0,
        28,
        232,
        100,
        [
            ("code", "G-0313-1383"),
            ("name", "سایر انواع پوشاک و لوازم"),
            ("name", "پوشاکی (کم‌دوام)"),
            meta("3", "1383–1388", "12"),
        ],
    )
    d.node(448, 0, 232, 56, [("code", "G-0313M-1389"), meta("3", "1389–1403")])
    d.node(448, 100, 232, 56, [("code", "G-0313A-1389"), meta("13", "1389–1403")], "accent")
    bus(d, 320, [(232, 78)], [(448, 28), (448, 128)])
    d.label(276, 62, d.t("split ", "تفکیک ") + d.year("1389"))
    d.label(384, 12, d.year(d.t("11 items", "11 قلم")))
    d.label(384, 112, d.year(d.t("1 item", "1 قلم")))
    return d


def d_t(lang: str, en: str, fa: str) -> str:
    return fa if lang == "fa" else en


DIAGRAMS = {
    "pipeline": pipeline,
    "change-shapes": change_shapes,
    "hamburger": hamburger,
    "header-levels": header_levels,
    "clothing-split": clothing_split,
}
MARKER = re.compile(r"^<!-- diagram: ([a-z-]+) -->$", re.MULTILINE)


def fill(markdown: str, lang: str) -> str:
    """Put each diagram a marker names in its place; an unknown name stops the build."""

    def one(m: re.Match) -> str:
        name = m.group(1)
        if name not in DIAGRAMS:
            raise KeyError(f"unknown diagram {name!r}; known: {', '.join(DIAGRAMS)}")
        return DIAGRAMS[name](lang).svg()

    return MARKER.sub(one, markdown)
