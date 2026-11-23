import json
import shutil
import subprocess
from pathlib import Path

import pytest

from hiesir_codebook import explorer

ROOT = Path(__file__).resolve().parents[1]


def _collect():
    return explorer.collect(
        corrected=ROOT / "output" / "2_corrected",
        items=ROOT / "output" / "3_items",
        source=ROOT / "curated" / "2_corrected" / "corrections.csv",
        groups=ROOT / "output" / "4_groups",
    )


def test_every_chain_and_kept_relation_is_embedded():
    data = _collect()
    ids = {c["id"] for c in data["chains"]}
    assert len(ids) == len(data["chains"])
    for r in data["relations"]:
        assert set(r["from"]) | set(r["to"]) <= ids, r["id"]
        assert r["verified"] != "rejected"
    # the group headers of an item come from the corrected questionnaire, outermost first
    rice = next(c for c in data["chains"] if c["id"] == "011111-1383")
    assert [p[0] for p in rice["path"]] == ["011", "0111", "01111, 01112"]
    assert set(data["sections"]) == set(range(1, 15))
    # and its groups in each year, from output/4_groups/ (indexes into data["groups"])
    (y0, path), *_ = rice["gp"]
    assert y0 == 1383 and [data["groups"][i][0] for i in path] == ["011", "0111", "01111, 01112"]
    assert [data["groupIds"][i] for i in path] == ["011-1383", "0111-1383", "01111+01112-1383"]
    for c in data["chains"]:
        assert [y for y, _ in c["gp"]] == sorted({y for y, _ in c["gp"]}), c["id"]
    # a group's wording by year, for the list under a picked year, the latest last
    # (a fifth entry, only for a group whose label changed)
    reworded = next(g for g in data["groups"] if len(g) > 4)
    assert len(reworded[4]) > 1
    assert [y for y, _ in reworded[4]] == sorted({y for y, _ in reworded[4]})
    assert reworded[4][-1][1] == reworded[1]
    # 0111 is printed فرآورده‌های until 1385 and فراورده‌های from 1386: one word
    # written two ways, which the corrected labels write one way
    cereals = next(g for g in data["groups"] if g[0] == "0111")
    assert cereals[1] == "غلات، نان، آرد، رشته و فراورده‌های آن" and len(cereals) == 4
    assert data["sectionYears"][10][0][0] == 1383


def test_bundle_follows_imports(tmp_path):
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib" / "a.js").write_text(
        "export const one = 1;\nexport function two() { return 2; }\n"
        "const three = 3;\nexport { three as THREE };\n",
        encoding="utf-8",
    )
    (tmp_path / "b.js").write_text(
        'import { one, two as deux } from "./lib/a.js";\nimport { THREE } from "./lib/a.js";\n'
        "export const sum = one + deux() + THREE;\n",
        encoding="utf-8",
    )
    entry = tmp_path / "main.js"
    entry.write_text('import { sum } from "./b.js";\nwindow.out = sum;\n', encoding="utf-8")
    js = explorer.bundle_js(entry)
    # each module once, after the ones it imports
    assert js.index("// ---- lib/a.js") < js.index("// ---- b.js") < js.index("// ---- main.js")
    assert js.count("// ---- lib/a.js") == 1
    assert "return { one, two, THREE: three };" in js
    assert "const { one, two: deux } = $m0;" in js
    assert "import " not in js and "export " not in js
    if shutil.which("node"):  # and it runs
        run = tmp_path / "run.js"
        run.write_text("const window = {};\n" + js + "console.log(window.out);\n", encoding="utf-8")
        assert subprocess.run(["node", str(run)], capture_output=True, text=True).stdout.strip() == "6"


def test_bundle_refuses_what_it_cannot_read(tmp_path):
    a, b = tmp_path / "a.js", tmp_path / "b.js"
    a.write_text('import { b } from "./b.js";\nexport const a = 1;\n', encoding="utf-8")
    b.write_text('import { a } from "./a.js";\nexport const b = 1;\n', encoding="utf-8")
    with pytest.raises(ValueError, match="import cycle"):
        explorer.bundle_js(a)
    b.write_text("export default 1;\n", encoding="utf-8")
    with pytest.raises(ValueError, match=r"b\.js:1"):
        explorer.bundle_js(a)


def test_bundle_css_inlines_imports(tmp_path):
    (tmp_path / "a.css").write_text(".a {}\n", encoding="utf-8")
    (tmp_path / "b.css").write_text('@import "a.css";\n.b {}\n', encoding="utf-8")
    (tmp_path / "all.css").write_text('/* all */\n@import "b.css";\n.c {}\n', encoding="utf-8")
    assert explorer.bundle_css(tmp_path / "all.css") == "/* all */\n.a {}\n.b {}\n.c {}\n"


def test_component_bundles():
    """web/explorer/ bundles into one script holding both languages, and
    (when Node is installed) the script parses."""
    js = explorer.bundle_js()
    for part in ("i18n/fa.js", "core/model.js", "ui/tree.js", "app/mount.js", "explorer.js"):
        assert f"// ---- {part}\n" in js
    assert js.count("tabs: {") == 2  # an English and a Farsi set of strings
    assert '@import "' not in explorer.bundle_css()
    if shutil.which("node"):
        r = subprocess.run(["node", "--check", "-"], input=js, capture_output=True, encoding="utf-8")
        assert r.returncode == 0, r.stderr


CORE_CHECK = """
import { readFileSync } from "node:fs";
import { model } from "CORE/model.js";
import { compare, gcompare } from "CORE/compare.js";
import { search } from "CORE/search.js";
import { events, KINDS } from "CORE/changes.js";
import { codesSnippet } from "CORE/snippets.js";
import { norm } from "CORE/text.js";
import { itemsHash, changesHash, parseHash } from "SRC/app/state.js";
import { makeFormat } from "SRC/i18n/format.js";

const M = model(JSON.parse(readFileSync(process.argv[2], "utf8")));
const fa = makeFormat("fa", M.YEARS);
const v = { item: "011111-1383", ref: 1390, q: "برنج", sec: "1", partial: true };
const item = parseHash(M, itemsHash(M, v));
const ch = parseHash(M, changesHash({ y: 1386, sec: 2, kinds: new Set(["merged", "split"]) }));
const ids = res => res.map(([s, rank, hit]) => [hit.id, rank]);
const rice = M.serOf.get("011111-1383");
const st = cmp => Object.fromEntries([...cmp].map(([y, e]) => [y, e.st]));
console.log(JSON.stringify({
  norm: norm("كتاب‌ها ۱۲"),
  code: ids(search(M, "011111")).slice(0, 1),
  short: ids(search(M, "11114")).map(([id]) => id.slice(0, 6)),
  text: search(M, "برنج").length,
  rice: st(compare(M, rice, 1403)),
  cereals: st(gcompare(M, M.NODES.get("0111-1383"), 1403))[1403],
  kinds: [...new Set(events(M).map(e => e.kind))].every(k => KINDS.includes(k)),
  events: events(M).length,
  snippet: codesSnippet(M.YEARS, compare(M, rice, 1403), "# rice").split("\\n").slice(0, 4),
  item: [item.view, item.series.id, item.ref, item.q, item.sec, item.partial],
  changes: [ch.view, ch.y, ch.sec, [...ch.kinds]],
  // a heading not printed in the latest year, linked without a year: all items
  oldGroup: parseHash(M, "#group=" + [...M.NODES.values()].find(n => n.kind === "g" && n.last < M.LAST).id)
    .ref,
  ranges: fa.ranges([1383, 1384, 1385, 1390]),
}));
"""


@pytest.mark.skipif(not shutil.which("node"), reason="needs Node")
def test_core_runs_on_its_own(tmp_path):
    """web/explorer/src/core/ needs no DOM and no bundling: Node imports it as
    it is and runs it on the real data."""
    data = tmp_path / "data.json"
    data.write_text(explorer.to_json(_collect()), encoding="utf-8")
    script = tmp_path / "check.mjs"
    src = (explorer.WEB / "src").as_uri() + "/"
    script.write_text(CORE_CHECK.replace("CORE/", src + "core/").replace("SRC/", src), encoding="utf-8")
    r = subprocess.run(["node", str(script), str(data)], capture_output=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["norm"] == "کتابها12"  # Arabic letter forms, ZWNJ, Persian digits
    assert out["code"] == [["011111-1383", 0]]
    assert "011114" in out["short"]  # the raw data's 5-digit code finds the 6-digit one
    assert out["text"] > 0
    assert out["rice"]["1403"] == "ref" and set(out["rice"].values()) == {"ref", 0}
    assert out["cereals"] == "ref"
    assert out["kinds"] and out["events"] > 100
    assert out["snippet"] == [
        "# rice",
        "# codes to add up in each year (the raw data's Commodity_Code)",
        "codes = {",
        "    1383: [11111],",
    ]
    # the URL scheme (app/state.js) reads back what it writes
    assert out["item"] == ["items", "011111-1383", 1390, "برنج", "1", True]
    assert out["changes"] == ["years", 1386, 2, ["merged", "split"]]
    assert out["oldGroup"] is None
    assert out["ranges"] == "۱۳۸۳–۱۳۸۵، ۱۳۹۰"  # i18n/format.js, in Persian digits


def test_docs_page_loads_the_component():
    """docs/explorer.md is drawn by overrides/explorer.html, which loads the
    bundled explorer.js and explorer.css (scripts/mkdocs_hooks.py publishes
    them, with the data made from the CSVs)."""
    template = (ROOT / "overrides" / "explorer.html").read_text(encoding="utf-8")
    for name in ("explorer.js", "explorer.css"):
        assert f"assets/explorer/{name}" in template
    assert '<hies-explorer class="hx ' in template and "</hies-explorer>" in template
    hooks = (ROOT / "scripts" / "mkdocs_hooks.py").read_text(encoding="utf-8")
    assert "bundle_js()" in hooks and "bundle_css()" in hooks and "collect()" in hooks
    for page in ("explorer.md", "explorer.fa.md"):
        assert "template: explorer.html" in (ROOT / "docs" / page).read_text(encoding="utf-8")
