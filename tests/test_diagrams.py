"""The documentation's diagrams (scripts/diagrams.py): every one drawn in both
languages, every marker in the pages naming one, the same ones on both sides."""

import importlib.util
import re
from pathlib import Path
from xml.etree import ElementTree

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("diagrams", ROOT / "scripts" / "diagrams.py")
diagrams = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diagrams)

SVG = "{http://www.w3.org/2000/svg}"


@pytest.mark.parametrize("lang", ["en", "fa"])
@pytest.mark.parametrize("name", list(diagrams.DIAGRAMS))
def test_diagram_is_an_accessible_figure(name, lang):
    figure = ElementTree.fromstring(diagrams.DIAGRAMS[name](lang).svg())
    svg = figure.find(f"{SVG}svg")
    assert svg.get("role") == "img"
    title, desc = list(svg)[:2]
    assert title.tag == f"{SVG}title" and desc.tag == f"{SVG}desc"
    assert svg.get("aria-labelledby") == f"{title.get('id')} {desc.get('id')}"
    assert title.text and desc.text
    w, h = (float(v) for v in svg.get("viewBox").split()[2:])
    for rect in svg.iter(f"{SVG}rect"):
        x, y = float(rect.get("x")), float(rect.get("y"))
        assert x >= 0 and x + float(rect.get("width")) <= w, (name, lang, rect.attrib)
        assert y >= 0 and y + float(rect.get("height")) <= h, (name, lang, rect.attrib)


def test_farsi_is_mirrored():
    """The Farsi drawing is the English one flipped left to right."""
    # boxes and frames; an arrow label's mask is as wide as its text in each language
    box = re.compile(r'<rect x="([\d.]+)" y="([\d.]+)" width="([\d.]+)"[^>]* class="dg-(?:node|zone)')
    for name, draw in diagrams.DIAGRAMS.items():
        en, fa = draw("en"), draw("fa")
        pairs = list(zip(box.findall(en.svg()), box.findall(fa.svg()), strict=True))
        assert pairs, name
        for (x, y, w), (fx, fy, fw) in pairs:
            assert (float(fx), fy, fw) == (en.w - float(x) - float(w), y, w), name


def test_connectors_are_orthogonal():
    d = diagrams.Drawing("t", "en", 100, "t", "t")
    with pytest.raises(ValueError, match="diagonal"):
        d.edge([(0, 0), (10, 10)])


def test_markers_name_known_diagrams_on_both_sides():
    for page in sorted((ROOT / "docs").glob("*.md")):
        if page.name.endswith(".fa.md"):
            continue
        fa = page.with_name(page.stem + ".fa.md")
        found = diagrams.MARKER.findall(page.read_text(encoding="utf-8"))
        assert set(found) <= set(diagrams.DIAGRAMS), page.name
        if fa.exists():
            assert diagrams.MARKER.findall(fa.read_text(encoding="utf-8")) == found, fa.name


def test_unknown_marker_stops_the_build():
    with pytest.raises(KeyError, match="unknown diagram"):
        diagrams.fill("<!-- diagram: nothing -->", "en")
