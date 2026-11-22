"""The explorer's data and component, for the documentation site.

:func:`collect` reads ``output/2_corrected/``, ``output/3_items/chains.csv``,
``links.csv``, ``relations.csv``, ``output/4_groups/groups.csv``, ``members.csv``
and ``curated/2_corrected/corrections.csv``; :func:`bundle_js` and
:func:`bundle_css` join the component of ``web/explorer/`` into one script and
one stylesheet. Nothing is written to ``output/``: ``scripts/mkdocs_hooks.py``
calls these when the site is built and publishes ``explorer/data.json`` and
``assets/explorer/``.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

from . import CORRECTED, CURATED_CORRECTED, GROUPS, ITEMS, csv_io
from .linking.compare import YEARS

# The component lives in web/explorer/ (website code, not Python; see its README);
# the documentation site loads it (docs/explorer.md, overrides/explorer.html,
# scripts/mkdocs_hooks.py). Like output/ and curated/, it is read from the repository.
WEB = Path(__file__).resolve().parents[2] / "web" / "explorer"
JS = WEB / "src" / "explorer.js"  # the entry module; bundle_js() follows its imports
CSS = WEB / "styles" / "explorer.css"  # @imports the partials; bundle_css() inlines them


def _read(path: Path) -> list[dict[str, str]]:
    return csv_io.read(path)


def _questionnaire(
    path: Path,
) -> tuple[dict[str, str], dict[str, list[list[str]]], dict[str, int], dict[str, list[int]]]:
    """Section titles and, for each expenditure code, its group headers (outermost
    first), the PDF page it is printed on and its box on that page
    ([top, bottom, left, right] in whole points from the top-left corner;
    [top, bottom] when the row has no table around it)."""
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
            if r["page"]:  # items added by corrections.csv have no printed page
                pages[r["expenditure_code"]] = int(r["page"])
            if r["top"] and r["bottom"]:
                box = [math.floor(float(r["top"])), math.ceil(float(r["bottom"]))]
                if r["left"] and r["right"]:
                    box += [math.floor(float(r["left"])), math.ceil(float(r["right"]))]
                boxes[r["expenditure_code"]] = box
    return sections, paths, pages, boxes


def _runs(by_year: dict[int, str]) -> list[list]:
    """{1383: a, 1384: a, 1386: b} -> [[1383, a], [1386, b]]: each wording from
    the first year it is printed."""
    runs: list[list] = []
    for y in sorted(by_year):
        if not runs or runs[-1][1] != by_year[y]:
            runs.append([y, by_year[y]])
    return runs


def _groups(path: Path) -> tuple[list[list], dict[tuple[int, str], list[int]], list[list], list[str]]:
    """The groups as [code, label, level, section] (a fifth entry, the
    wordings by year, is added by collect() when the label changed); for
    every (year, expenditure code) the indexes of its groups, outermost first
    (level 2, 3, 4 when printed); and the group links that are not rejected,
    as [from index, to index, relation, year, items]; and the group ids."""
    rows = _read(path / "groups.csv")
    index = {r["group_id"]: i for i, r in enumerate(rows)}
    groups = [[r["code"], r["label"], int(r["level"]), int(r["section"])] for r in rows]
    members = {
        (int(m["year"]), m["expenditure_code"]): [
            index[m[k]] for k in ("level_2", "level_3", "level_4") if m[k]
        ]
        for m in _read(path / "members.csv")
    }
    links = [
        [index[r["from_group"]], index[r["to_group"]], r["relation"], int(r["year"]), int(r["items"] or 0)]
        for r in _read(path / "links.csv")
        if r["verified"] != "rejected"
    ]
    return groups, members, links, [r["group_id"] for r in rows]


def collect(
    corrected: Path = CORRECTED,
    items: Path = ITEMS,
    source: Path = CURATED_CORRECTED / "corrections.csv",
    years: list[int] = YEARS,
    groups: Path = GROUPS,
) -> dict:
    """Everything the page shows, as plain JSON-able data."""
    sections: dict[str, str] = {}
    paths: dict[int, dict[str, list[list[str]]]] = {}
    pages: dict[int, dict[str, int]] = {}
    boxes: dict[int, dict[str, list[int]]] = {}
    section_years: dict[int, dict[int, str]] = {}
    for y in years:
        s, paths[y], pages[y], boxes[y] = _questionnaire(corrected / f"questionnaire_{y}.csv")
        sections.update(s)  # the latest year's title wins
        for k, v in s.items():
            section_years.setdefault(int(k), {})[y] = v
    group_list, members, group_links, group_ids = _groups(groups)
    # the wording of each group in each year, read from the header printed
    # above its items, so the page can show the words of the year picked
    group_years: dict[int, dict[int, str]] = {}
    for (y, code), idx in members.items():
        printed = {p[0]: p[1] for p in paths[y].get(code, [])} if y in paths else {}
        for gi in idx:
            if group_list[gi][0] in printed:
                group_years.setdefault(gi, {})[y] = printed[group_list[gi][0]]
    for gi, worded in group_years.items():
        if len(set(worded.values())) > 1:
            group_list[gi].append(_runs(worded))
    chains = []
    for c in _read(items / "chains.csv"):
        first, last = int(c["first_year"]), int(c["last_year"])
        miss = [int(y) for y in c["missing_years"].split()]
        code = c["expenditure_code"]
        asked = [y for y in years if first <= y <= last and y not in miss]
        # its groups, as [first year, [group indexes]] each time they change
        gp: list = []
        for y in asked:
            g = members.get((y, code), [])
            if not gp or gp[-1][1] != g:
                gp.append([y, g])
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
                "pg": [pages[y].get(code) for y in asked],
                # and its box on that page, for the highlight
                "bx": [boxes[y].get(code) for y in asked],
                "gp": gp,
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
            "check": r["decided_by"] == "open",
            "verified": r["verified"],
            "note": r["note"],
        }
        for name, cols in (
            ("links.csv", ("link_id", "from_chain", "to_chain")),
            ("relations.csv", ("relation_id", "from_chains", "to_chains")),
        )
        for r in _read(items / name)
        if r["verified"] != "rejected"
    ]
    corrections = [
        {k: r[k] for k in ("year", "action", "expenditure_code", "description", "value", "reason")}
        for r in _read(source)
    ]
    return {
        "years": years,
        "sections": {int(k): v for k, v in sorted(sections.items(), key=lambda kv: int(kv[0]))},
        # section titles that changed: {section: [[first year, title], ...]}
        "sectionYears": {k: _runs(v) for k, v in sorted(section_years.items()) if len(set(v.values())) > 1},
        "groups": group_list,
        "groupLinks": group_links,
        # the id of each group (code and first year, as in output/4_groups/), for links to its page
        "groupIds": group_ids,
        "chains": chains,
        "relations": relations,
        "corrections": corrections,
    }


def to_json(data: dict) -> str:
    """The data as compact JSON, safe to embed in a <script> element."""
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


# --- the bundler ----------------------------------------------------------------
# The component is written as plain ES modules, so a site with its own build
# can import them as they are. The two pages here need one classic script (an
# ES module does not load from file://), so bundle_js() joins them, without
# Node: each module becomes a function returning what it exports, in the order
# of their imports. It reads only the forms the component uses, and stops on
# any other:
#   import { a, b as c } from "./x.js";      (relative, at the start of a line)
#   export function f / export async function f / export const|let|class x
#   export { a, b as c };
# Dynamic import() (PDF.js, from its CDN) is left alone.
_IMPORT = re.compile(r'^import\s*\{([^}]*)\}\s*from\s*"(\.{1,2}/[^"]+)";?[ \t]*$', re.M)
_EXPORT = re.compile(r"^export\s+((?:async\s+)?function\*?|const|let|class)\s+([A-Za-z_$][\w$]*)", re.M)
_EXPORT_LIST = re.compile(r"^export\s*\{([^}]*)\};?[ \t]*$", re.M)
_OTHER = re.compile(r"^[ \t]*(?:import\s*[^\s(]|export\b)", re.M)
_CSS_IMPORT = re.compile(r'^@import\s+"([^"]+)";[ \t]*\n?', re.M)


def _names(spec: str) -> list[tuple[str, str]]:
    """'a, b as c' -> [("a", "a"), ("b", "c")]"""
    out = []
    for part in filter(None, (p.strip() for p in spec.split(","))):
        name, _, alias = (x.strip() for x in part.partition(" as "))
        out.append((name, alias or name))
    return out


def _modules(entry: Path) -> list[Path]:
    """The modules entry needs, each after the ones it imports."""
    order: list[Path] = []
    state: dict[Path, str] = {}

    def visit(path: Path, trail: list[Path]) -> None:
        path = path.resolve()
        if state.get(path) == "done":
            return
        if state.get(path) == "open":
            raise ValueError("import cycle: " + " -> ".join(p.name for p in [*trail, path]))
        if not path.is_file():
            raise FileNotFoundError(f"{trail[-1] if trail else entry} imports {path}, which does not exist")
        state[path] = "open"
        for _, spec in _IMPORT.findall(path.read_text(encoding="utf-8")):
            visit(path.parent / spec, [*trail, path])
        state[path] = "done"
        order.append(path)

    visit(entry, [])
    return order


def bundle_js(entry: Path = JS) -> str:
    """entry and every module it imports, as one script."""
    paths = _modules(entry)
    var = {p: f"$m{i}" for i, p in enumerate(paths)}
    root = entry.resolve().parent
    out = ["(function () {", '"use strict";']
    for path in paths:
        src = path.read_text(encoding="utf-8")
        exports: list[tuple[str, str]] = [(m.group(2), m.group(2)) for m in _EXPORT.finditer(src)]
        for m in _EXPORT_LIST.finditer(src):
            exports += [(alias, name) for name, alias in _names(m.group(1))]

        def imp(m: re.Match, path: Path = path) -> str:
            names = ", ".join(n if n == a else f"{n}: {a}" for n, a in _names(m.group(1)))
            return f"const {{ {names} }} = {var[(path.parent / m.group(2)).resolve()]};"

        src = _EXPORT_LIST.sub("", _EXPORT.sub(r"\1 \2", _IMPORT.sub(imp, src)))
        left = _OTHER.search(src)
        if left:
            line = src.count("\n", 0, left.start()) + 1
            raise ValueError(f"{path}:{line}: the bundler cannot read this import or export")
        ret = ", ".join(k if k == v else f"{k}: {v}" for k, v in exports)
        out += [
            f"// ---- {path.relative_to(root).as_posix() if path.is_relative_to(root) else path.name}",
            f"const {var[path]} = (() => {{",
            src.rstrip("\n"),
            f"return {{ {ret} }};" if ret else "return {};",
            "})();",
        ]
    out.append("})();")
    return "\n".join(out) + "\n"


def bundle_css(entry: Path = CSS, _seen: frozenset[Path] = frozenset()) -> str:
    """entry with its @import "x.css"; lines replaced by the files, recursively."""
    entry = entry.resolve()
    if entry in _seen:
        raise ValueError(f"@import cycle at {entry}")

    def inline(m: re.Match) -> str:
        return bundle_css(entry.parent / m.group(1), _seen | {entry})

    return _CSS_IMPORT.sub(inline, entry.read_text(encoding="utf-8"))
