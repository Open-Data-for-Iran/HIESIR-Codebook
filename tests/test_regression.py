"""Re-extract every year and compare with the tracked CSVs in output/1_extracted/.

The PDFs are not in git, so these tests skip when data/pdf/ is missing (CI
downloads them from the release).  A failure means the extractor's output
changed: if the change is intended, regenerate with `uv run hiesir-codebook
all` and review the diff.
"""

from pathlib import Path

import pytest

from hiesir_codebook import SUPPORTED_YEARS, write_csv
from hiesir_codebook.extraction.layout import QUIRKS
from hiesir_codebook.extraction.parse import extract_year, pdf_path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
EXTRACTED = ROOT / "output" / "1_extracted"
REPAIRED_FONT_YEARS = [1395, 1396, 1399, 1402]


@pytest.mark.slow
@pytest.mark.parametrize("year", SUPPORTED_YEARS)
def test_extract_matches_tracked_csv(year, tmp_path):
    """One extraction per year, three checks:

    - the CSV is the tracked one;
    - every print-quirk repair it makes is one ``layout.QUIRKS`` lists for the
      year (a repair in a new year: look at the PDF, then add the year);
    - in the repaired-font years every glyph is found in the glyph database
      (the 1396 isolated alef is learnt from 1387).
    """
    if not pdf_path(year, DATA).exists():
        pytest.skip(f"no PDF for {year} in {DATA / 'pdf'}")
    discards = []
    out = tmp_path / f"questionnaire_{year}.csv"
    write_csv(extract_year(year, DATA, discards), out)
    assert out.read_bytes() == (EXTRACTED / out.name).read_bytes()

    quirk_of = {q.note: name for name, q in QUIRKS.items()}
    unlisted = sorted(
        {
            quirk_of[d.reason]
            for d in discards
            if d.reason in quirk_of and year not in QUIRKS[quirk_of[d.reason]].years
        }
    )
    assert unlisted == [], f"repairs not listed for {year} in layout.QUIRKS: {unlisted}"

    if year in REPAIRED_FONT_YEARS:
        assert [d for d in discards if "glyph" in d.reason] == []


@pytest.mark.parametrize("year", REPAIRED_FONT_YEARS)
def test_repaired_fonts_keep_zwnj(year):
    """In the years whose fonts are repaired through glyph_db, a plain letter
    from the database is an isolated glyph, so its ZWNJ is recovered."""
    text = (EXTRACTED / f"questionnaire_{year}.csv").read_text(encoding="utf-8-sig")
    assert "میوه‌گیری" in text  # 053214, printed with a final ه
    assert "میوهگیری" not in text
