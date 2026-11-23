"""MkDocs hooks: publish the explorer's data and component, the CSVs and the PDFs.

They are added to the site at build time instead of being copied into docs/,
so git holds one copy and the site always shows what output/ holds:

    explorer.collect() over output/          -> explorer/data.json
    web/explorer/src/ (bundled)              -> assets/explorer/explorer.js
    web/explorer/styles/ (bundled)           -> assets/explorer/explorer.css
    output/2_corrected/*.csv                 -> 2_corrected/*.csv
    output/3_items/*.csv                     -> 3_items/*.csv
    output/4_groups/*.csv                    -> 4_groups/*.csv
    the questionnaire PDFs                   -> pdf/questionnaire_<year>[_<area>].pdf

The PDFs are not in git. They come from $HIESIR_PDF_DIR, else data/pdf/
(`hiesir-codebook pdfs download` fetches the release "questionnaires" there,
as the GitHub workflow does); without any, the site is built without them. The list on the questionnaires
page (docs/questionnaires.md and its translation) is filled in from what is
found, in place of the marker <!-- questionnaire-pdfs -->.

Figures in the pages are written as {{ links.confirmed }}: each is read from
output/metrics.json (see hiesir_codebook.metrics), with thousands separators,
in Persian digits on the Farsi pages. An unknown name stops the build.

The home page's heatmap of changes by section and year (see heatmap()) goes
in place of the marker <!-- changes-heatmap -->, and each diagram in place of
its marker <!-- diagram: <name> --> (see scripts/diagrams.py).

The explorer page itself is docs/explorer.md (and its translations), drawn by
overrides/explorer.html.

Each page's <link rel="alternate" hreflang> tags are dropped: Material's
script fetches sitemap.xml from every such link, expecting a language root,
but mkdocs-static-i18n points them at the page in each language, so every
page asked for <page>/sitemap.xml and got a 404. Search engines still get the
same pairs from sitemap.xml (its xhtml:link entries), and the language menu
uses its own links.
"""

from __future__ import annotations

import html
import importlib.util
import json
import logging
import os
import re
import tempfile
from pathlib import Path

from mkdocs.structure.files import File, Files

from hiesir_codebook import explorer, metrics
from hiesir_codebook.extraction import pdfs

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output"
PUBLISH = ["2_corrected/*.csv", "3_items/*.csv", "4_groups/*.csv"]
MARKER = "<!-- questionnaire-pdfs -->"
HEAT_MARKER = "<!-- changes-heatmap -->"
HREFLANG = re.compile(r'[ \t]*<link rel="alternate" href="[^"]*" hreflang="[^"]*">\n?')
log = logging.getLogger("mkdocs.hooks.hiesir")

# scripts/diagrams.py, loaded by path: MkDocs loads this file by path too, so
# scripts/ is not importable
_spec = importlib.util.spec_from_file_location("hiesir_diagrams", Path(__file__).with_name("diagrams.py"))
diagrams = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(diagrams)

_found: list[pdfs.Pdf] = []
_heat: dict = {}


def _pdf_dir() -> Path | None:
    env = os.environ.get("HIESIR_PDF_DIR")
    candidates = [Path(env)] if env else [ROOT / "data" / "pdf"]
    return next((d for d in candidates if pdfs.find(d)), None)


def on_files(files: Files, config) -> Files:
    # added in every language build; mkdocs-static-i18n writes them once, at the
    # site root, and points the translated pages there
    cwd = os.getcwd()
    os.chdir(ROOT)  # explorer.collect() reads output/ and curated/ relative to the repository
    try:
        collected = explorer.collect()
    finally:
        os.chdir(cwd)
    _heat.clear()
    _heat.update(year_changes(collected))
    data = explorer.to_json(collected)
    # a real file: mkdocs-static-i18n cannot handle files generated from content
    cache = Path(tempfile.mkdtemp(prefix="hiesir-explorer-")) / "data.json"
    cache.write_text(data, encoding="utf-8")
    files.append(File.generated(config, "explorer/data.json", abs_src_path=str(cache)))
    # the component, bundled: one script, one stylesheet
    for name, text in (("explorer.js", explorer.bundle_js()), ("explorer.css", explorer.bundle_css())):
        (cache.parent / name).write_text(text, encoding="utf-8", newline="\n")
        files.append(File.generated(config, f"assets/explorer/{name}", abs_src_path=str(cache.parent / name)))
    for pattern in PUBLISH:
        paths = sorted(OUTPUT.glob(pattern))
        if not paths:
            raise FileNotFoundError(f"nothing matches output/{pattern}; run `hiesir-codebook build`")
        for p in paths:
            files.append(File.generated(config, p.relative_to(OUTPUT).as_posix(), abs_src_path=str(p)))

    folder = _pdf_dir()
    _found[:] = pdfs.find(folder) if folder else []
    if not _found:
        log.info("no questionnaire PDFs (set HIESIR_PDF_DIR or fill data/pdf/); building without them")
    for f in _found:
        files.append(File.generated(config, f"pdf/{f.name}", abs_src_path=str(f.path)))
    return files


TABLE = {
    "en": {
        "head": "| Year | Form | Status | Size | PDF |\n|---|---|---|---:|---|",
        "area": {"urban": "urban", "rural": "rural", "": "urban and rural"},
        "kind": {
            "extracted": "extracted: see the explorer",
            "text": "text layer, left out (older code scheme)",
            "dictionary": "data dictionary, not a questionnaire",
            "scan": "scanned images only",
        },
        "missing": "!!! note\n    The PDFs were not available when this copy of the site was built.",
        "mb": "MB",
        "year": str,
    },
    "fa": {
        "head": "| سال | فرم | وضعیت | حجم | PDF |\n|---|---|---|---:|---|",
        "area": {"urban": "شهری", "rural": "روستایی", "": "شهری و روستایی"},
        "kind": {
            "extracted": "استخراج‌شده: در جست‌وجوی اقلام",
            "text": "لایه متنی دارد، کنار گذاشته شده (نظام کدگذاری قدیمی)",
            "dictionary": "راهنمای داده، نه پرسشنامه",
            "scan": "فقط تصویر اسکن‌شده",
        },
        "missing": "!!! note\n    فایل‌های PDF هنگام ساختن این نسخه از سایت در دسترس نبودند.",
        "mb": "مگابایت",
        "year": lambda y: str(y).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")),
    },
}


def pdf_table(found: list[pdfs.Pdf], lang: str) -> str:
    t = TABLE.get(lang, TABLE["en"])
    if not found:
        return t["missing"]
    rows = [t["head"]]
    for f in found:
        size = f"{f.path.stat().st_size / 2**20:.1f} {t['mb']}"
        if lang == "fa":
            size = t["year"](size).replace(".", "٫")
        rows.append(
            f"| {t['year'](f.year)} | {t['area'][f.area]} | {t['kind'][f.kind]} | {size} "
            f"| [{f.name}](pdf/{f.name}) |"
        )
    return "\n".join(rows)


# --- the home page's heatmap: items changed by section and year -------------------
# The same count as the explorer's Changes by year with its default kinds
# (web/explorer/src/core/changes.js, events()): a new or dropped chain counts 1,
# a merge, split or regrouping its larger side, a reworded link (wording or
# scope) 1; group-heading links and PDF corrections are left out. Ported here so
# the home page needs no script and not the explorer's data.json.

HEAT_KINDS = {"added", "dropped", "recoded", "merged", "split", "regrouped", "scope"}


def year_changes(data: dict) -> dict:
    """{"years", "sections", "titles", "cells": {(section, year): n}, "totals": {year: n}}
    from explorer.collect()."""
    years: list[int] = data["years"]
    groups = data["groups"]
    chains = {c["id"]: c for c in data["chains"]}
    ins: dict[str, list[dict]] = {}
    outs: dict[str, list[dict]] = {}
    for r in data["relations"]:
        for i in r["to"]:
            ins.setdefault(i, []).append(r)
        for i in r["from"]:
            outs.setdefault(i, []).append(r)

    def asked(c: dict) -> list[int]:
        miss = set(c["miss"])
        return [y for y in years if c["first"] <= y <= c["last"] and y not in miss]

    def sec_at(c: dict, y: int | None) -> int:
        g: list[int] = []
        for y0, p in c.get("gp") or []:
            if y is not None and y0 <= y:
                g = p
        return (g and g[0] < len(groups) and groups[g[0]][3]) or c["s"]

    def prev(y: int) -> int | None:
        i = years.index(y)
        return years[i - 1] if i > 0 else None

    events: list[tuple[str, int, int | None, int]] = []
    for r in data["relations"]:
        if r["rel"] == "same":
            kind = "scope" if r.get("detail") and r["detail"] != "minor" else None
        else:
            kind = r["rel"]
        if not kind:
            continue
        tgt = chains.get(r["to"][0]) if r["to"] else None
        src = chains.get(r["from"][0]) if r["from"] else None
        sec = sec_at(tgt, r["year"]) if tgt else sec_at(src, prev(r["year"])) if src else None
        events.append((kind, r["year"], sec, max(len(r["from"]), len(r["to"]))))
    for c in data["chains"]:
        ys = asked(c)
        first, last = ys[0], ys[-1]
        if first != years[0] and not any(r["year"] == first for r in ins.get(c["id"], [])):
            events.append(("added", first, sec_at(c, first), 1))
        i = years.index(last)
        nxt = years[i + 1] if i + 1 < len(years) else None
        if nxt and not any(r["year"] == nxt for r in outs.get(c["id"], [])):
            events.append(("dropped", nxt, sec_at(c, last), 1))

    cells: dict[tuple[int, int], int] = {}
    totals: dict[int, int] = {}
    for kind, y, sec, n in events:
        if kind not in HEAT_KINDS:
            continue
        totals[y] = totals.get(y, 0) + n
        if sec is not None:
            cells[(int(sec), y)] = cells.get((int(sec), y), 0) + n
    sections = sorted(int(s) for s in data["sections"])
    return {
        "years": years,
        "sections": sections,
        "titles": data["sections"],
        "cells": cells,
        "totals": totals,
    }


HEAT_TEXT = {
    "en": {
        "caption": "Items changed in each questionnaire, by section: new, dropped, recoded, merged, split, "
        "regrouped and reworded; the stronger the colour, the more items. Pick a cell to see those changes "
        "in the explorer.",
        "section": "Section",
        "total": "All",
        "cell": lambda y, s, n: f"{y}, section {s}: {n} items changed",
        "year": lambda y, n: f"{y}: {n} items changed",
        "num": lambda n: f"{n:,}",
    },
    "fa": {
        "caption": "اقلامی که هر پرسشنامه تغییر داده، به تفکیک بخش: تازه، حذف‌شده، تغییر کد، ادغام، تفکیک، "
        "بازگروه‌بندی و عبارت تازه؛ هر چه رنگ پررنگ‌تر، اقلام بیشتر. "
        "روی یک خانه بزنید تا آن تغییرات را در جست‌وجوی اقلام ببینید.",
        "section": "بخش",
        "total": "همه",
        "cell": lambda y, s, n: f"{y}، بخش {s}: {n} قلم تغییر کرده",
        "year": lambda y, n: f"{y}: {n} قلم تغییر کرده",
        "num": lambda n: metrics.figure(n, "fa"),
    },
}


def heatmap(heat: dict, lang: str) -> str:
    """The heatmap as an HTML table (styled in docs/assets/extra.css): rows are
    sections, columns years, each cell a link to its changes in the explorer."""
    if not heat:
        return ""
    t = HEAT_TEXT.get(lang, HEAT_TEXT["en"])
    num = t["num"]
    yr = (lambda y: metrics.figure(str(y), "fa")) if lang == "fa" else str
    years, cells = heat["years"], heat["cells"]
    top = max(cells.values(), default=1)
    esc = html.escape
    rows = [
        f'<tr><th scope="col" class="corner">{t["section"]}</th>'
        + "".join(f'<th scope="col" title="{yr(y)}">{yr(y)[2:]}</th>' for y in years)
        + "</tr>"
    ]
    for s in heat["sections"]:
        tds = []
        for y in years:
            n = cells.get((s, y), 0)
            if not n:
                tds.append("<td></td>")
                continue
            # the explorer's square-root scale, starting darker so one item
            # stands out from none at this size
            a = 0.25 + 0.75 * (n / top) ** 0.5
            label = esc(t["cell"](yr(y), num(s), num(n)))
            tds.append(
                f'<td style="--a:{a:.2f}"><a href="explorer/#changes&amp;year={y}&amp;section={s}" '
                f'title="{label}"><span>{num(n)}</span></a></td>'
            )
        title = esc(heat["titles"].get(str(s), ""))
        rows.append(f'<tr><th scope="row" title="{title}">{num(s)}</th>{"".join(tds)}</tr>')
    tds = []
    for y in years:
        n = heat["totals"].get(y, 0)
        label = esc(t["year"](yr(y), num(n)))
        tds.append(
            f'<td><a href="explorer/#changes&amp;year={y}" title="{label}">{num(n)}</a></td>'
            if n
            else "<td></td>"
        )
    rows.append(f'<tr class="total"><th scope="row">{t["total"]}</th>{"".join(tds)}</tr>')
    return (
        f'<figure class="heatmap">\n<div class="heatmap-scroll"><table class="heatmap-table">'
        f"{''.join(rows)}</table></div>\n<figcaption>{esc(t['caption'])}</figcaption>\n</figure>"
    )


def on_page_markdown(markdown: str, page, config, files) -> str:
    lang = config.theme.get("language", "en")
    if "{{" in markdown:
        figures = json.loads((OUTPUT / "metrics.json").read_text(encoding="utf-8"))
        markdown = metrics.fill(markdown, figures, lang, page.file.src_uri)
    if HEAT_MARKER in markdown:
        markdown = markdown.replace(HEAT_MARKER, heatmap(_heat, lang))
    markdown = diagrams.fill(markdown, lang)
    if MARKER not in markdown:
        return markdown
    return markdown.replace(MARKER, pdf_table(_found, lang))


def on_post_page(output: str, page, config) -> str:
    return HREFLANG.sub("", output)
