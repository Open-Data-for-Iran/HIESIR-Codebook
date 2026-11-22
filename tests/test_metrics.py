from pathlib import Path

import pytest

from hiesir_codebook import metrics

ROOT = Path(__file__).resolve().parents[1]


def _compute():
    return metrics.compute(
        extracted=ROOT / "output" / "1_extracted",
        corrected=ROOT / "output" / "2_corrected",
        curated=ROOT / "curated" / "2_corrected",
        items=ROOT / "output" / "3_items",
        groups=ROOT / "output" / "4_groups",
    )


def test_metrics_are_up_to_date():
    """output/metrics.json must match output/ and curated/; if this fails,
    run `uv run python -m hiesir_codebook.metrics` (or the whole build)."""
    assert metrics.to_json(_compute()) == (ROOT / "output" / "metrics.json").read_text(encoding="utf-8")


def test_metrics_add_up():
    m = _compute()
    for name in ("links", "relations"):
        d = m[name]
        assert d["code"] + d["curated"] + d["open"] == d["total"]
        assert d["total"] - d["rejected"] == d["kept"]
    assert m["links"]["same"] + m["links"]["recoded"] == m["links"]["kept"]
    assert sum(m["relations"][k] for k in ("merged", "split", "regrouped")) == m["relations"]["kept"]
    assert sum(m["questionnaires"]["items_by_year"].values()) == m["questionnaires"]["items"]
    assert m["labels"]["spelling"] <= m["labels"]["total"]


def test_every_figure_in_the_docs_exists():
    """Each {{ name }} in docs/ names one figure of output/metrics.json."""
    m = metrics.json.loads((ROOT / "output" / "metrics.json").read_text(encoding="utf-8"))
    for page in sorted((ROOT / "docs").glob("*.md")):
        text = page.read_text(encoding="utf-8")
        lang = "fa" if page.name.endswith(".fa.md") else "en"
        assert "{{" not in metrics.fill(text, m, lang, page.name), page.name


def test_figures_are_formatted_for_each_language():
    m = {"links": {"total": 1064}, "corrections": {"years": "1383–1390"}}
    assert metrics.fill("{{ links.total }} links", m) == "1,064 links"
    assert metrics.fill("{{links.total}}", m, "fa") == "۱٬۰۶۴"
    assert metrics.fill("in {{ corrections.years }}", m, "fa") == "in ۱۳۸۳–۱۳۹۰"
    with pytest.raises(ValueError, match=r"no metric 'links\.kept'"):
        metrics.fill("{{ links.kept }}", m, where="methods.md")
    with pytest.raises(ValueError, match="group of metrics"):
        metrics.fill("{{ links }}", m)
