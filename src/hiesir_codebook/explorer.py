"""Build the explorer: one static HTML page to search and browse the matched items.

Reads ``output/2_corrected/``, ``output/3_matched/chains.csv``,
``output/3_matched/links.csv``, ``relations.csv`` and ``curated/source.csv``, and writes
``output/explorer/index.html`` with the data embedded, so the page works
offline and on any static host (no server, no build step).

    uv run python -m hiesir_codebook.explorer
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path

from . import CORRECTED, CURATED, MATCHED, OUTPUT
from .compare import YEARS

# The component (explorer.js, explorer.css) is shared by the standalone page
# written here and by the documentation site (docs/explorer.md,
# overrides/explorer.html, scripts/mkdocs_hooks.py), so the two cannot drift.
ASSETS = Path(__file__).parent / "data" / "explorer"
JS = ASSETS / "explorer.js"
CSS = ASSETS / "explorer.css"
TEMPLATE = ASSETS / "standalone.html"
OUT = OUTPUT / "explorer" / "index.html"
PLACEHOLDER = "/*__DATA__*/null"


def _read(path: Path) -> list[dict[str, str]]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _questionnaire(
    path: Path,
) -> tuple[dict[str, str], dict[str, list[list[str]]], dict[str, int], dict[str, list[int]]]:
    """Section titles and, for each expenditure code, its group headers (outermost
    first), the PDF page it is printed on and its extent on that page
    ([top, bottom] in whole points from the top)."""
    sections: dict[str, str] = {}
    paths: dict[str, list[list[str]]] = {}
    pages: dict[str, int] = {}
    boxes: dict[str, list[int]] = {}
    stack: dict[int, list[str]] = {}
    for r in _read(path):
        if r["kind"] == "section":
            sections[r["section"]] = r["description"]
            stack = {}
        elif r["kind"] == "header":
            level = int(r["level"])
            stack = {k: v for k, v in stack.items() if k < level}
            stack[level] = [r["code"], r["description"]]
        elif r["kind"] == "item" and r["expenditure_code"] not in paths:
            paths[r["expenditure_code"]] = [stack[k] for k in sorted(stack)]
            if r["page"]:  # items added by curated/source.csv have no printed page
                pages[r["expenditure_code"]] = int(r["page"])
            if r["top"] and r["bottom"]:
                boxes[r["expenditure_code"]] = [math.floor(float(r["top"])), math.ceil(float(r["bottom"]))]
    return sections, paths, pages, boxes


def collect(
    corrected: Path = CORRECTED,
    matched: Path = MATCHED,
    source: Path = CURATED / "source.csv",
    years: list[int] = YEARS,
) -> dict:
    """Everything the page shows, as plain JSON-able data."""
    sections: dict[str, str] = {}
    paths: dict[int, dict[str, list[list[str]]]] = {}
    pages: dict[int, dict[str, int]] = {}
    boxes: dict[int, dict[str, list[int]]] = {}
    for y in years:
        s, paths[y], pages[y], boxes[y] = _questionnaire(corrected / f"questionnaire_{y}.csv")
        sections.update(s)  # the latest year's title wins
    chains = []
    for c in _read(matched / "chains.csv"):
        first, last = int(c["first_year"]), int(c["last_year"])
        miss = [int(y) for y in c["missing_years"].split()]
        code = c["expenditure_code"]
        chains.append(
            {
                "id": c["chain_id"],
                "s": int(c["section"]),
                "code": c["expenditure_code"],
                "first": first,
                "last": last,
                "miss": miss,
                "text": c["text"],
                "path": paths[last].get(code, []),
                # the printed page in each year the chain is asked, in year order
                "pg": [pages[y].get(code) for y in years if first <= y <= last and y not in miss],
                # and its [top, bottom] on that page, for the highlight
                "bx": [boxes[y].get(code) for y in years if first <= y <= last and y not in miss],
            }
        )
    relations = [
        {
            "id": r[cols[0]],
            "from": r[cols[1]].split(),
            "to": r[cols[2]].split(),
            "rel": r["relation"],
            "detail": r["detail"],
            "year": int(r["year"]),
            "check": r["needs_verification"] == "True",
            "verified": r["verified"],
            "note": r["note"],
        }
        for name, cols in (
            ("links.csv", ("link_id", "from_chain", "to_chain")),
            ("relations.csv", ("relation_id", "from_chains", "to_chains")),
        )
        for r in _read(matched / name)
        if r["verified"] != "rejected"
    ]
    corrections = [
        {k: r[k] for k in ("year", "action", "expenditure_code", "description", "value", "reason")}
        for r in _read(source)
    ]
    return {
        "years": years,
        "sections": {int(k): v for k, v in sorted(sections.items(), key=lambda kv: int(kv[0]))},
        "chains": chains,
        "relations": relations,
        "corrections": corrections,
    }


def to_json(data: dict) -> str:
    """The data as compact JSON, safe to embed in a <script> element."""
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def render(data: dict, template: Path = TEMPLATE, js: Path = JS, css: Path = CSS) -> str:
    """The standalone page: template + component + data in one file."""
    html = template.read_text(encoding="utf-8")
    parts = {
        PLACEHOLDER: to_json(data),
        "/*__JS__*/": js.read_text(encoding="utf-8").replace("</script", "<\\/script"),
        "/*__CSS__*/": css.read_text(encoding="utf-8"),
    }
    for key, value in parts.items():
        if key not in html:
            raise ValueError(f"{template} has no {key} placeholder")
        html = html.replace(key, value, 1)
    return html


def build(out: Path = OUT, **kwargs) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(render(collect(**kwargs)))
    return out


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="python -m hiesir_codebook.explorer", description=__doc__)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)
    out = build(args.out)
    print(f"explorer -> {out.as_posix()} ({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
