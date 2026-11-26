"""Render a ~14 s motion graphic of the HIESIR Codebook pipeline as a GIF."""

import sys

from PIL import Image, ImageDraw, ImageFont

OUT = sys.argv[1]
W, H, S = 800, 450, 2  # logical size, supersample factor
FPS = 20
DUR = 14.4
FONTS = "C:/Windows/Fonts/"

BG = (15, 23, 42)
PANEL = (30, 41, 59)
LINE = (51, 65, 85)
TXT = (226, 232, 240)
MUTED = (148, 163, 184)
TEAL = (45, 212, 191)
AMBER = (251, 191, 36)
ROSE = (251, 113, 133)
SKY = (56, 189, 248)
VIOLET = (167, 139, 250)

_fc = {}


def font(name, size):
    key = (name, size)
    if key not in _fc:
        _fc[key] = ImageFont.truetype(FONTS + name, int(size * S), layout_engine=ImageFont.Layout.RAQM)
    return _fc[key]


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def prog(t, a, b):
    return clamp((t - a) / (b - a))


def ease(x):
    x = clamp(x)
    return 4 * x**3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def back(x):  # ease-out with a little overshoot
    x = clamp(x)
    c1, c3 = 1.7, 2.7
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def mix(c, a, under=BG):
    a = clamp(a)
    return tuple(int(u + (v - u) * a) for v, u in zip(c, under, strict=True))


def lerp(a, b, x):
    return a + (b - a) * x


class Canvas:
    def __init__(self):
        self.im = Image.new("RGB", (W * S, H * S), BG)
        self.d = ImageDraw.Draw(self.im)

    def rect(self, x, y, w, h, fill=None, outline=None, r=6, width=1):
        self.d.rounded_rectangle(
            [x * S, y * S, (x + w) * S, (y + h) * S],
            radius=r * S,
            fill=fill,
            outline=outline,
            width=int(width * S),
        )

    def line(self, pts, fill, width=2):
        self.d.line([(x * S, y * S) for x, y in pts], fill=fill, width=int(width * S), joint="curve")

    def circle(self, x, y, r, fill):
        self.d.ellipse([(x - r) * S, (y - r) * S, (x + r) * S, (y + r) * S], fill=fill)

    def text(self, x, y, s, size, fill, f="segoeui.ttf", anchor="la", fa=False):
        kw = {}
        if fa:
            f = "tahoma.ttf"
            kw = {"direction": "rtl", "language": "fa"}
        self.d.text((x * S, y * S), s, font=font(f, size), fill=fill, anchor=anchor, **kw)

    def textw(self, s, size, f="segoeui.ttf", fa=False):
        if fa:
            return font("tahoma.ttf", size).getlength(s, direction="rtl", language="fa") / S
        return font(f, size).getlength(s) / S


def scene_alpha(t, a, b, fade=0.3):
    return min(prog(t, a, a + fade), 1 - prog(t, b - fade, b))


STEPS = ["extract", "correct", "match", "group", "explore"]
STEP_COL = [SKY, AMBER, TEAL, VIOLET, ROSE]


def stepper(c, t, active, alpha):
    if alpha <= 0:
        return
    widths = [c.textw(s, 12, "segoeuib.ttf") + 24 for s in STEPS]
    gap = 22
    total = sum(widths) + gap * (len(STEPS) - 1)
    x = (W - total) / 2
    y = 18
    for i, (s, w) in enumerate(zip(STEPS, widths, strict=True)):
        on = i == active
        done = i < active
        col = STEP_COL[i]
        if on:
            c.rect(x, y, w, 24, fill=mix(col, alpha), r=12)
            c.text(x + w / 2, y + 12, s, 12, mix(BG, alpha), "segoeuib.ttf", "mm")
        else:
            c.rect(x, y, w, 24, outline=mix(col if done else LINE, alpha), r=12, width=1.2)
            c.text(x + w / 2, y + 12, s, 12, mix(col if done else MUTED, alpha), "segoeuib.ttf", "mm")
        if i < len(STEPS) - 1:
            ax = x + w + 5
            c.line([(ax, y + 12), (ax + gap - 10, y + 12)], mix(LINE, alpha), 1.5)
            c.line(
                [(ax + gap - 14, y + 8), (ax + gap - 10, y + 12), (ax + gap - 14, y + 16)],
                mix(LINE, alpha),
                1.5,
            )
        x += w + gap


def caption(c, s, a, col=MUTED):
    c.text(W / 2, H - 30, s, 14, mix(col, a), anchor="mm")


# ---------------------------------------------------------------- scenes


def s_title(c, t):
    a = scene_alpha(t, 0, 1.8, 0.35)
    p = ease(prog(t, 0.05, 0.8))
    c.text(W / 2, 175 + 20 * (1 - p), "HIESIR Codebook", 46, mix(TXT, a * p), "segoeuib.ttf", "mm")
    p2 = ease(prog(t, 0.35, 1.0))
    c.text(
        W / 2,
        228 + 12 * (1 - p2),
        "Iran's household expenditure questionnaires",
        18,
        mix(MUTED, a * p2),
        anchor="mm",
    )
    c.text(
        W / 2, 254 + 12 * (1 - p2), "1383 – 1403, followed item by item", 18, mix(MUTED, a * p2), anchor="mm"
    )
    # a little row of colour dots, one per stage
    for i, col in enumerate(STEP_COL):
        pi = back(prog(t, 0.6 + i * 0.08, 1.0 + i * 0.08))
        c.circle(W / 2 - 48 + i * 24, 300, 5 * pi, mix(col, a))


ROWS = [
    ("011111", "برنج صدری، دمسیاه و استخوانی"),
    ("011112", "برنج طارم"),
    ("011113", "برنج بی‌نام"),
    ("011114", "برنج چمپا و آشی"),
    ("011241", "همبرگر و کباب لقمه آماده برای طبخ"),
    ("011242", "کتلت آماده برای طبخ"),
]


def s_extract(c, t, a0, b0):
    a = scene_alpha(t, a0, b0)
    lt = t - a0
    # 20 mini PDF pages
    years = [y for y in range(1383, 1404) if y != 1401]
    for i, yr in enumerate(years):
        col, row = i % 5, i // 5
        x, y = 50 + col * 46, 110 + row * 62
        p = back(prog(lt, i * 0.03, 0.35 + i * 0.03))
        if p <= 0:
            continue
        ph = 50 * p
        c.rect(x, y + (50 - ph) / 2, 36, ph, fill=mix(PANEL, a), outline=mix(LINE, a), r=3)
        for k in range(4):
            if p > 0.9:
                c.line([(x + 6, y + 10 + k * 7), (x + 30 - (k % 2) * 8, y + 10 + k * 7)], mix(LINE, a), 1.2)
        c.text(x + 18, y + 43, str(yr), 8, mix(MUTED, a * clamp(p)), anchor="mm")
        # scan highlight
        sp = prog(lt, 0.9 + row * 0.12, 1.3 + row * 0.12)
        if 0 < sp < 1:
            c.rect(x - 2, y - 2, 40, 54, outline=mix(SKY, a * (1 - sp)), r=4, width=1.5)
    c.text(140, 360, "20 PDF forms", 13, mix(MUTED, a * prog(lt, 0.6, 1.0)), anchor="mm")

    # arrow
    ap = ease(prog(lt, 0.8, 1.2))
    c.line([(300, 225), (300 + 50 * ap, 225)], mix(SKY, a), 2.5)
    if ap > 0.95:
        c.line([(342, 218), (350, 225), (342, 232)], mix(SKY, a), 2.5)

    # table
    tx, ty, tw = 375, 110, 380
    tp = ease(prog(lt, 1.0, 1.3))
    c.rect(tx, ty, tw, 250 * tp + 1, fill=mix(PANEL, a), r=8)
    if tp > 0.8:
        c.text(tx + 16, ty + 14, "code", 11, mix(MUTED, a), "segoeuib.ttf")
        c.text(tx + tw - 16, ty + 14, "label, as printed", 11, mix(MUTED, a), "segoeuib.ttf", "ra")
    for i, (code, lab) in enumerate(ROWS):
        rp = ease(prog(lt, 1.2 + i * 0.12, 1.5 + i * 0.12))
        if rp <= 0:
            continue
        y = ty + 44 + i * 33
        dx = 30 * (1 - rp)
        c.line([(tx + 12, y - 8), (tx + tw - 12, y - 8)], mix(LINE, a * rp, PANEL), 1)
        c.text(tx + 16 + dx, y + 6, code, 14, mix(SKY, a * rp, PANEL), "consola.ttf", "lm")
        c.text(tx + tw - 16 + dx, y + 6, lab, 14, mix(TXT, a * rp, PANEL), anchor="rm", fa=True)

    n = int(21821 * ease(prog(lt, 1.3, 2.4)))
    caption(c, f"{n:,} items read off the page", a * prog(lt, 1.3, 1.5), TXT)


def s_correct(c, t, a0, b0):
    a = scene_alpha(t, a0, b0)
    lt = t - a0
    cx = W / 2
    c.text(cx - 170, 100, "as printed", 14, mix(MUTED, a), "segoeuib.ttf", "mm")
    c.text(cx + 170, 100, "as intended", 14, mix(AMBER, a), "segoeuib.ttf", "mm")

    def card(y, left, right, f_left, f_right, fa, delay):
        p = back(prog(lt, delay, delay + 0.4))
        cw = 260
        c.rect(cx - 170 - cw / 2, y - 28 + 10 * (1 - p), cw, 56, fill=mix(PANEL, a * clamp(p)), r=8)
        c.rect(
            cx + 170 - cw / 2,
            y - 28,
            cw,
            56,
            outline=mix(AMBER, a * prog(lt, delay + 0.7, delay + 1.0)),
            r=8,
            width=1.5,
        )
        c.text(cx - 170, y, left, 22, mix(TXT, a * clamp(p), PANEL), f_left, "mm", fa=fa)
        # strike-through
        sp = ease(prog(lt, delay + 0.45, delay + 0.75))
        if sp > 0:
            lw = c.textw(left, 22, f_left, fa=fa)
            c.line(
                [(cx - 170 - lw / 2 - 4, y + 1), (cx - 170 - lw / 2 - 4 + (lw + 8) * sp, y + 1)],
                mix(ROSE, a),
                2.5,
            )
        # arrow
        ap = ease(prog(lt, delay + 0.55, delay + 0.85))
        if ap > 0:
            c.line([(cx - 30, y), (cx - 30 + 60 * ap, y)], mix(AMBER, a), 2.5)
            if ap > 0.95:
                c.line([(cx + 22, y - 7), (cx + 30, y), (cx + 22, y + 7)], mix(AMBER, a), 2.5)
        rp = ease(prog(lt, delay + 0.7, delay + 1.0))
        c.text(cx + 170 + 20 * (1 - rp), y, right, 22, mix(TXT, a * rp), f_right, "mm", fa=fa)

    card(165, "دیبرستان", "دبیرستان", None, None, True, 0.15)
    card(250, "1022 16", "103116", "consola.ttf", "consola.ttf", False, 0.55)
    c.text(
        cx + 170, 290, "pre-university item, group 1031", 11, mix(MUTED, a * prog(lt, 1.6, 1.9)), anchor="mm"
    )
    c.text(cx - 170, 206, "typo", 11, mix(MUTED, a * prog(lt, 1.2, 1.5)), anchor="mm")

    p = ease(prog(lt, 1.5, 1.9))
    c.rect(cx - 190, 335 + 8 * (1 - p), 380, 34, fill=mix(PANEL, a * p), r=17)
    c.circle(cx - 170, 352 + 8 * (1 - p), 4, mix(AMBER, a * p))
    c.text(
        cx + 6,
        352 + 8 * (1 - p),
        "curated/  —  each fix is one row, with its reason",
        13,
        mix(TXT, a * p, PANEL),
        anchor="mm",
    )


YEARS = [y for y in range(1383, 1404) if y != 1401]


def yx(year):
    i = YEARS.index(year) if year in YEARS else YEARS.index(1402) - 0.5
    return 110 + i * (650 / (len(YEARS) - 1))


def s_match(c, t, a0, b0):
    a = scene_alpha(t, a0, b0)
    lt = t - a0
    # axis
    axp = ease(prog(lt, 0.0, 0.4))
    ay = 375
    c.line([(yx(1383), ay), (yx(1383) + (yx(1403) - yx(1383)) * axp, ay)], mix(LINE, a), 1.5)
    for yr in YEARS:
        if yx(yr) <= yx(1383) + (yx(1403) - yx(1383)) * axp:
            c.line([(yx(yr), ay - 3), (yx(yr), ay + 3)], mix(LINE, a), 1.2)
            if yr in (1383, 1387, 1389, 1395, 1403):
                c.text(yx(yr), ay + 16, str(yr), 11, mix(MUTED, a), anchor="mm")

    # sweep cursor: year reached
    sw = ease(prog(lt, 0.3, 2.3))
    cur = lerp(yx(1383), yx(1403), sw)
    if 0 < sw < 1:
        c.line([(cur, 80), (cur, ay)], mix(TEAL, a * 0.35), 1)

    def bar(y, y0, y1, col, code, label, label_side="above"):
        xa, xb = yx(y0) - 6, yx(y1) + 6
        xe = min(xb, cur + 6)
        if xe <= xa:
            return False
        c.rect(xa, y - 7, xe - xa, 14, fill=mix(col, a), r=7)
        lp = prog(cur, xa + 10, xa + 60)
        c.text(xa + 2, y - 18, code, 11, mix(col, a * lp), "consola.ttf", "lm")
        fits = c.textw(label, 12, fa=True) + c.textw(code, 11, "consola.ttf") + 16 < xb - xa
        if fits:
            c.text(xb - 2, y - 18, label, 12, mix(TXT, a * lp), anchor="rm", fa=True)
        else:
            c.text(xb - 2, y + 19, label, 12, mix(TXT, a * lp), anchor="rm", fa=True)
        return True

    # rice: same item, label narrowed
    bar(110, 1383, 1386, SKY, "011114", "برنج چمپا و آشی")
    if bar(110, 1387, 1403, TEAL, "011114", "برنج آشی"):
        lp = prog(lt, 0.9, 1.2)
        c.line([(yx(1386) + 6, 110), (yx(1387) - 6, 110)], mix(TXT, a * lp), 2)
        c.text(yx(1387) + 4, 129, "same · label narrowed", 11, mix(TEAL, a * lp), "segoeuib.ttf", "lm")

    # three ready-meal items merged into one
    srcs = [(190, "011241", "همبرگر و کباب لقمه"), (235, "011242", "کتلت"), (280, "011243", "استیک")]
    for y, code, lab in srcs:
        bar(y, 1383, 1388, SKY, code, lab)
    if cur > yx(1389) - 6:
        mp = ease(prog(cur, yx(1389) - 6, yx(1389) + 40))
        for y, _, _ in srcs:
            x0, x1 = yx(1388) + 6, yx(1389) - 6
            c.line([(x0, y), (lerp(x0, x1, mp), lerp(y, 235, mp))], mix(TXT, a * 0.8), 2)
        bar(235, 1389, 1403, TEAL, "011241", "همبرگر، کباب لقمه، کتلت و استیک")
        c.text(yx(1389) + 4, 312, "3 → 1 · merged", 11, mix(TEAL, a * mp), "segoeuib.ttf", "lm")

    caption(c, "the same item, linked across years as its code and wording change", a * prog(lt, 0.3, 0.6))


def s_group(c, t, a0, b0):
    a = scene_alpha(t, a0, b0)
    lt = t - a0
    cx = W / 2
    p1 = ease(prog(lt, 0.0, 0.4))
    p2 = ease(prog(lt, 0.25, 0.65))
    # level 2
    w1, h1 = lerp(200, 620, p1), lerp(60, 270, p1)
    c.rect(cx - w1 / 2, 85, w1, h1, outline=mix(VIOLET, a * p1), r=12, width=1.5)
    c.text(cx - w1 / 2 + 16, 104, "011", 13, mix(VIOLET, a * p1), "consolab.ttf", "lm")
    c.text(cx + w1 / 2 - 16, 104, "مواد خوراکی", 14, mix(TXT, a * p1), anchor="rm", fa=True)
    # level 3 boxes
    subs = [
        ("0111", "غلات، نان، آرد", ["011111", "011112", "011113", "011114"]),
        ("0112", "گوشت", ["011211", "011241", "011244"]),
    ]
    for k, (code, lab, items) in enumerate(subs):
        bx = cx - 290 + k * 300
        bw, bh = 280 * p2, 190 * p2
        if p2 <= 0:
            continue
        c.rect(bx, 130, bw, bh, fill=mix(PANEL, a * p2), r=10)
        c.text(bx + 14, 150, code, 12, mix(VIOLET, a * p2, PANEL), "consolab.ttf", "lm")
        c.text(bx + bw - 14, 150, lab, 13, mix(TXT, a * p2, PANEL), anchor="rm", fa=True)
        for j, it in enumerate(items):
            ip = back(prog(lt, 0.6 + (k * 4 + j) * 0.07, 0.95 + (k * 4 + j) * 0.07))
            if ip <= 0:
                continue
            ix = bx + 14 + (j % 3) * 86
            iy = 178 + (j // 3) * 42 + 30 * (1 - ip)
            c.rect(
                ix,
                iy,
                76,
                28,
                fill=mix(TEAL, a * clamp(ip) * 0.18, PANEL),
                outline=mix(TEAL, a * clamp(ip), PANEL),
                r=6,
            )
            c.text(ix + 38, iy + 14, it, 12, mix(TEAL, a * clamp(ip), PANEL), "consola.ttf", "mm")
    caption(c, "items roll up into the questionnaire's groups, tracked year by year", a * prog(lt, 0.3, 0.6))


def s_explore(c, t, a0, b0):
    a = scene_alpha(t, a0, b0 + 1, 0.3) if t < b0 else 1 - prog(t, b0 - 0.35, b0)
    lt = t - a0
    cards = [
        ("Explorer", "search a code or label,", "see its whole history", ROSE),
        ("CSV tables", "chains · changes · groups,", "tracked as diffs in git", TEAL),
        ("Excel", "the corrected questionnaire", "for any year", SKY),
    ]
    cw, gap = 220, 20
    x0 = (W - (3 * cw + 2 * gap)) / 2
    for i, (title, l1, l2, col) in enumerate(cards):
        p = back(prog(lt, 0.1 + i * 0.15, 0.55 + i * 0.15))
        if p <= 0:
            continue
        x, y = x0 + i * (cw + gap), 120 + 40 * (1 - p)
        aa = a * clamp(p)
        c.rect(x, y, cw, 150, fill=mix(PANEL, aa), r=12)
        c.rect(x, y, cw, 5, fill=mix(col, aa), r=2)
        c.text(x + 20, y + 42, title, 20, mix(TXT, aa, PANEL), "segoeuib.ttf", "lm")
        c.text(x + 20, y + 85, l1, 13, mix(MUTED, aa, PANEL), anchor="lm")
        c.text(x + 20, y + 106, l2, 13, mix(MUTED, aa, PANEL), anchor="lm")
    tp = ease(prog(lt, 0.8, 1.2))
    c.text(
        W / 2,
        330 + 10 * (1 - tp),
        "one item, followed across 20 years of forms",
        20,
        mix(TXT, a * tp),
        "segoeuib.ttf",
        "mm",
    )
    c.text(
        W / 2,
        362 + 10 * (1 - tp),
        "open-data-for-iran.github.io/HIESIR-Codebook",
        13,
        mix(MUTED, a * tp),
        "consola.ttf",
        "mm",
    )


SCENES = [  # (start, end, stepper index or None, fn)
    (1.8, 4.5, 0, s_extract),
    (4.5, 7.0, 1, s_correct),
    (7.0, 10.0, 2, s_match),
    (10.0, 11.9, 3, s_group),
    (11.9, DUR, 4, s_explore),
]


def frame(t):
    c = Canvas()
    if t < 1.8:
        s_title(c, t)
    for a0, b0, idx, fn in SCENES:
        if a0 <= t < b0:
            fn(c, t, a0, b0)
            sa = prog(t, 1.8, 2.1) * (1 - prog(t, DUR - 0.35, DUR))
            stepper(c, t, idx, sa)
    return c.im.resize((W, H), Image.LANCZOS)


def main():
    n = int(DUR * FPS)
    frames = [frame(i / FPS) for i in range(n)]
    # one shared palette, taken from a strip of sample frames
    samples = [frames[int(s * FPS)] for s in (1.0, 3.5, 6.2, 9.5, 11.5, 13.5)]
    strip = Image.new("RGB", (W, H * len(samples)))
    for i, s in enumerate(samples):
        strip.paste(s, (0, H * i))
    pal = strip.quantize(colors=128, method=Image.Quantize.MEDIANCUT)
    q = [f.quantize(palette=pal, dither=Image.Dither.NONE) for f in frames]
    q[0].save(
        OUT, save_all=True, append_images=q[1:], duration=int(1000 / FPS), loop=0, optimize=True, disposal=1
    )
    for s in (1.0, 3.5, 6.2, 9.0, 11.5, 13.5):
        frames[int(s * FPS)].save(OUT.replace(".gif", f"_t{s}.png"))
    print("frames", n)


if __name__ == "__main__":
    main()
