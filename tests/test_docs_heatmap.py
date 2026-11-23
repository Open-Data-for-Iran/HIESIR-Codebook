"""The home page's heatmap (scripts/mkdocs_hooks.py) counts what the explorer's
Changes by year counts (web/explorer/src/core/changes.js), cell by cell."""

import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from hiesir_codebook import explorer

ROOT = Path(__file__).resolve().parents[1]

JS = """
import { readFileSync } from "node:fs";
import { model } from "CORE/model.js";
import { events, DEFAULT_KINDS } from "CORE/changes.js";
const M = model(JSON.parse(readFileSync(process.argv[2], "utf8")));
const cells = {}, totals = {};
for (const e of events(M)) {
  if (!DEFAULT_KINDS.includes(e.kind)) continue;
  totals[e.y] = (totals[e.y] || 0) + e.n;
  if (e.sec !== null) { const k = `${+e.sec}-${e.y}`; cells[k] = (cells[k] || 0) + e.n; }
}
console.log(JSON.stringify({ cells, totals }));
"""


def _hooks():
    pytest.importorskip("mkdocs")
    spec = importlib.util.spec_from_file_location("mkdocs_hooks", ROOT / "scripts" / "mkdocs_hooks.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _collect():
    return explorer.collect(
        corrected=ROOT / "output" / "2_corrected",
        items=ROOT / "output" / "3_items",
        source=ROOT / "curated" / "2_corrected" / "corrections.csv",
        groups=ROOT / "output" / "4_groups",
    )


@pytest.mark.skipif(not shutil.which("node"), reason="needs Node")
def test_heatmap_counts_as_the_explorer(tmp_path):
    hooks = _hooks()
    data = _collect()
    heat = hooks.year_changes(data)
    (tmp_path / "data.json").write_text(explorer.to_json(data), encoding="utf-8")
    script = tmp_path / "heat.mjs"
    script.write_text(JS.replace("CORE/", (explorer.WEB / "src" / "core").as_uri() + "/"), encoding="utf-8")
    r = subprocess.run(
        ["node", str(script), str(tmp_path / "data.json")], capture_output=True, encoding="utf-8"
    )
    assert r.returncode == 0, r.stderr
    js = json.loads(r.stdout)
    assert {f"{s}-{y}": n for (s, y), n in heat["cells"].items()} == js["cells"]
    assert {str(y): n for y, n in heat["totals"].items()} == js["totals"]


def test_heatmap_html():
    hooks = _hooks()
    heat = hooks.year_changes(_collect())
    en, fa = hooks.heatmap(heat, "en"), hooks.heatmap(heat, "fa")
    # a row per section and the totals, a link per changed cell
    assert en.count("<tr") == len(heat["sections"]) + 2
    assert en.count('href="explorer/#changes&amp;year=') == len(heat["cells"]) + len(heat["totals"])
    assert "۱۳۸۶" in fa and ">86<" in en
    assert hooks.heatmap({}, "en") == ""
