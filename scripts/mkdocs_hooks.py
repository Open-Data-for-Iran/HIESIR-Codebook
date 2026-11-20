"""MkDocs hooks: publish the explorer's data and component, the CSVs and the PDFs.

They are added to the site at build time instead of being copied into docs/,
so git holds one copy and the site always shows what output/ holds:

    explorer.collect() over output/          -> explorer/data.json
    src/.../data/explorer/{strings,explorer}.js, explorer.css -> assets/explorer/
    output/2_corrected/*.csv                 -> 2_corrected/*.csv
    output/3_items/*.csv                     -> 3_items/*.csv
    output/4_groups/*.csv                    -> 4_groups/*.csv
    the questionnaire PDFs                   -> pdf/questionnaire_<year>[_<area>].pdf

The PDFs are not in git. They come from $HIESIR_PDF_DIR (the GitHub workflow
downloads the release "questionnaires" there), else data/release/ or data/pdf/;
without any, the site is built without them. The list on the questionnaires
page (docs/questionnaires.md and its translation) is filled in from what is
found, in place of the marker <!-- questionnaire-pdfs -->.

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

import logging
import os
import re
import tempfile
from pathlib import Path

from mkdocs.structure.files import File, Files

from hiesir_codebook import explorer
from hiesir_codebook.extraction import pdfs

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output"
PUBLISH = ["2_corrected/*.csv", "3_items/*.csv", "4_groups/*.csv"]
MARKER = "<!-- questionnaire-pdfs -->"
HREFLANG = re.compile(r'[ \t]*<link rel="alternate" href="[^"]*" hreflang="[^"]*">\n?')
log = logging.getLogger("mkdocs.hooks.hiesir")

_found: list[pdfs.Pdf] = []


def _pdf_dir() -> Path | None:
    env = os.environ.get("HIESIR_PDF_DIR")
    candidates = [Path(env)] if env else [ROOT / "data" / "release", ROOT / "data" / "pdf"]
    return next((d for d in candidates if pdfs.find(d)), None)


def on_files(files: Files, config) -> Files:
    # added in every language build; mkdocs-static-i18n writes them once, at the
    # site root, and points the translated pages there
    cwd = os.getcwd()
    os.chdir(ROOT)  # explorer.collect() reads output/ and curated/ relative to the repository
    try:
        data = explorer.to_json(explorer.collect())
    finally:
        os.chdir(cwd)
    # a real file: mkdocs-static-i18n cannot handle files generated from content
    cache = Path(tempfile.mkdtemp(prefix="hiesir-explorer-")) / "data.json"
    cache.write_text(data, encoding="utf-8")
    files.append(File.generated(config, "explorer/data.json", abs_src_path=str(cache)))
    for src in (explorer.STRINGS, explorer.JS, explorer.CSS):
        files.append(File.generated(config, f"assets/explorer/{src.name}", abs_src_path=str(src)))
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


def on_page_markdown(markdown: str, page, config, files) -> str:
    if MARKER not in markdown:
        return markdown
    return markdown.replace(MARKER, pdf_table(_found, config.theme.get("language", "en")))


def on_post_page(output: str, page, config) -> str:
    return HREFLANG.sub("", output)
