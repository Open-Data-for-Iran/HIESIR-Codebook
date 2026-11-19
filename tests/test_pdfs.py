import importlib.util
from pathlib import Path

import pytest

from hiesir_codebook import explorer, pdfs

ROOT = Path(__file__).resolve().parents[1]


def test_published_names(tmp_path):
    for name in (
        "Questionnaire 1363 Urban.pdf",
        "Questionnaire 1386.pdf",
        "questionnaire_1401.pdf",
        "notes.pdf",
    ):
        (tmp_path / name).write_bytes(b"%PDF")
    found = pdfs.find(tmp_path)
    assert [(f.year, f.area, f.name, f.kind) for f in found] == [
        (1363, "urban", "questionnaire_1363_urban.pdf", "scan"),
        (1386, "", "questionnaire_1386.pdf", "extracted"),
        (1401, "", "questionnaire_1401.pdf", "dictionary"),
    ]
    staged = pdfs.stage(tmp_path, tmp_path / "out")
    assert sorted(p.name for p in staged) == [f.name for f in found]


def _hooks():
    pytest.importorskip("mkdocs")  # the docs dependency group
    spec = importlib.util.spec_from_file_location("mkdocs_hooks", ROOT / "scripts" / "mkdocs_hooks.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_questionnaire_table(tmp_path):
    (tmp_path / "Questionnaire 1386.pdf").write_bytes(b"%PDF" * 1000)
    hooks = _hooks()
    found = pdfs.find(tmp_path)
    en = hooks.pdf_table(found, "en")
    assert (
        "| 1386 | urban and rural | extracted" in en
        and "[questionnaire_1386.pdf](pdf/questionnaire_1386.pdf)" in en
    )
    fa = hooks.pdf_table(found, "fa")
    assert "| ۱۳۸۶ | شهری و روستایی |" in fa
    assert "!!! note" in hooks.pdf_table([], "en")


def test_explorer_knows_the_printed_page():
    data = explorer.collect(
        corrected=ROOT / "output" / "2_corrected",
        matched=ROOT / "output" / "3_matched",
        source=ROOT / "curated" / "source.csv",
    )
    for c in data["chains"]:
        asked = [y for y in data["years"] if c["first"] <= y <= c["last"] and y not in c["miss"]]
        assert len(c["pg"]) == len(asked), c["id"]  # one page per year asked, in order
    rice = next(c for c in data["chains"] if c["id"] == "011111-1383")
    assert all(isinstance(p, int) and p > 0 for p in rice["pg"])
