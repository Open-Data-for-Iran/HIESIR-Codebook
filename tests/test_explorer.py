from pathlib import Path

from hiesir_codebook import explorer

ROOT = Path(__file__).resolve().parents[1]


def _collect():
    return explorer.collect(
        corrected=ROOT / "output" / "2_corrected",
        items=ROOT / "output" / "3_items",
        source=ROOT / "curated" / "2_corrected" / "corrections.csv",
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


def test_docs_page_and_standalone_share_the_component():
    """docs/explorer.md is drawn by overrides/explorer.html, which loads the same
    explorer.js and explorer.css that the standalone page inlines."""
    template = (ROOT / "overrides" / "explorer.html").read_text(encoding="utf-8")
    assert "assets/explorer/explorer.js" in template and "assets/explorer/explorer.css" in template
    for page in ("explorer.md", "explorer.fa.md"):
        assert "template: explorer.html" in (ROOT / "docs" / page).read_text(encoding="utf-8")
    js = explorer.JS.read_text(encoding="utf-8")
    assert js.count("tabs: {") == 2  # an English and a Farsi set of strings


def test_explorer_is_up_to_date(tmp_path):
    """output/explorer/index.html must match the data and the template;
    if this fails, run `uv run hiesir-codebook build --no-extract`."""
    out = tmp_path / "index.html"
    out.write_text(explorer.render(_collect()), encoding="utf-8", newline="\n")
    assert out.read_bytes() == (ROOT / "output" / "explorer" / "index.html").read_bytes()
