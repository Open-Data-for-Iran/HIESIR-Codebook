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
    # a group's wording by year, for the list under a picked year: 0111 spelled
    # فرآورده‌های until 1385, فراورده‌های from 1386
    cereals = next(g for g in data["groups"] if g[0] == "0111")
    assert cereals[4][0] == [1383, "غلات، نان، آرد، رشته و فرآورده‌های آن"]
    assert cereals[4][-1][1] == cereals[1]
    assert data["sectionYears"][10][0][0] == 1383


def test_render_escapes_closing_tags(tmp_path):
    template = tmp_path / "t.html"
    template.write_text(
        "<style>/*__CSS__*/</style>"
        f"<script>const DATA = {explorer.PLACEHOLDER};</script>"
        "<script>/*__JS__*/</script>",
        encoding="utf-8",
    )
    js, css = tmp_path / "x.js", tmp_path / "x.css"
    js.write_text('const s = "</script>";', encoding="utf-8")
    css.write_text(".a { color: red }", encoding="utf-8")
    html = explorer.render({"x": "</script><b>"}, template, js=js, css=css)
    assert html.count("</script>") == 2  # only the template's own closing tags
    assert '"<\\/script><b>"' in html
    assert ".a { color: red }" in html


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
    for part in ("i18n/en.js", "i18n/fa.js", "i18n/index.js", "explorer.js"):
        assert f"// ---- {part}\n" in js
    assert js.count("tabs: {") == 2  # an English and a Farsi set of strings
    assert '@import "' not in explorer.bundle_css()
    if shutil.which("node"):
        r = subprocess.run(["node", "--check", "-"], input=js, capture_output=True, encoding="utf-8")
        assert r.returncode == 0, r.stderr


def test_docs_page_and_standalone_share_the_component():
    """docs/explorer.md is drawn by overrides/explorer.html, which loads the
    bundled explorer.js and explorer.css that the standalone page inlines
    (scripts/mkdocs_hooks.py publishes them)."""
    template = (ROOT / "overrides" / "explorer.html").read_text(encoding="utf-8")
    for name in ("explorer.js", "explorer.css"):
        assert f"assets/explorer/{name}" in template
    hooks = (ROOT / "scripts" / "mkdocs_hooks.py").read_text(encoding="utf-8")
    assert "bundle_js()" in hooks and "bundle_css()" in hooks
    for page in ("explorer.md", "explorer.fa.md"):
        assert "template: explorer.html" in (ROOT / "docs" / page).read_text(encoding="utf-8")


def test_explorer_is_up_to_date(tmp_path):
    """output/explorer/index.html must match the data and the template;
    if this fails, run `uv run hiesir-codebook build --no-extract`."""
    out = tmp_path / "index.html"
    out.write_text(explorer.render(_collect()), encoding="utf-8", newline="\n")
    assert out.read_bytes() == (ROOT / "output" / "explorer" / "index.html").read_bytes()
