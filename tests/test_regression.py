"""Re-extract every year and compare with the tracked CSVs in output/1_extracted/.

The PDFs are not in git, so these tests skip when data/pdf/ is missing.
A failure means the extractor's output changed: if the change is intended,
regenerate with `uv run hiesir-codebook all` and review the diff.
"""

from pathlib import Path

import pytest

from hiesir_codebook import SUPPORTED_YEARS, write_csv
from hiesir_codebook.extraction.parse import extract_year, pdf_path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
EXTRACTED = ROOT / "output" / "1_extracted"


@pytest.mark.slow
@pytest.mark.parametrize("year", SUPPORTED_YEARS)
def test_extract_matches_tracked_csv(year, tmp_path):
    if not pdf_path(year, DATA).exists():
        pytest.skip(f"no PDF for {year} in {DATA / 'pdf'}")
    out = tmp_path / f"questionnaire_{year}.csv"
    write_csv(extract_year(year, DATA), out)
    assert out.read_bytes() == (EXTRACTED / out.name).read_bytes()


@pytest.mark.parametrize("year", [1395, 1396, 1399, 1402])
def test_repaired_fonts_keep_zwnj(year):
    """In the years whose fonts are repaired through glyph_db, a plain letter
    from the database is an isolated glyph, so its ZWNJ is recovered."""
    text = (EXTRACTED / f"questionnaire_{year}.csv").read_text(encoding="utf-8-sig")
    assert "میوه‌گیری" in text  # 053214, printed with a final ه
    assert "میوهگیری" not in text


@pytest.mark.slow
@pytest.mark.parametrize("year", [1395, 1396, 1399, 1402])
def test_repaired_fonts_read_every_glyph(year):
    """Every glyph of the broken fonts is found in the glyph database (the
    1396 isolated alef is learnt from 1387)."""
    if not pdf_path(year, DATA).exists():
        pytest.skip(f"no PDF for {year} in {DATA / 'pdf'}")
    discards = []
    extract_year(year, DATA, discards)
    assert [d for d in discards if "glyph" in d.reason] == []
