"""Re-extract every year and compare with the tracked CSVs in output/1_extracted/.

The PDFs are not in git, so these tests skip when data/pdf/ is missing.
A failure means the extractor's output changed: if the change is intended,
regenerate with `uv run hbsir-questionnaire all` and review the diff.
"""

from pathlib import Path

import pytest

from hbsir_questionnaire import SUPPORTED_YEARS, write_csv
from hbsir_questionnaire.parse import extract_year, pdf_path

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
