import json
from pathlib import Path

import pytest

from hiesir_codebook import bundle

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "output" / "5_results"


@pytest.fixture(scope="module")
def folder(tmp_path_factory):
    return bundle.write(RESULTS, tmp_path_factory.mktemp("bundle"), "abc123", "2026-01-01")


def _copy(folder, tmp_path):
    out = tmp_path / "copy"
    out.mkdir()
    for p in folder.iterdir():
        (out / p.name).write_bytes(p.read_bytes())
    return out


def test_the_schema_knows_every_column_of_every_file():
    """A new results file or column needs its description in bundle.py."""
    pkg = bundle.package(RESULTS)
    assert {r["path"] for r in pkg["resources"]} == {p.name for p in RESULTS.glob("*.csv")}
    for r in pkg["resources"]:
        assert all(f["description"] for f in r["schema"]["fields"])


def test_the_bundle_passes_its_own_schema(folder):
    bundle.check(folder)
    assert not (folder / "items.csv").read_bytes().startswith(b"\xef\xbb\xbf")
    assert (folder / "items.csv").read_bytes() == (RESULTS / "items.csv").read_bytes()[3:]
    pkg = json.loads((folder / "datapackage.json").read_text(encoding="utf-8"))
    assert (pkg["version"], pkg["commit"]) == (bundle.DATA_VERSION, "abc123")
    assert folder.parent.joinpath(f"{folder.name}.zip").exists()


def test_check_finds_a_bom_a_bad_value_and_a_broken_key(folder, tmp_path):
    bad = _copy(folder, tmp_path)
    (bad / "years.csv").write_bytes(b"\xef\xbb\xbf" + (bad / "years.csv").read_bytes())
    text = (bad / "chains.csv").read_text(encoding="utf-8")
    first = text.splitlines()[1]
    (bad / "chains.csv").write_text(text.replace(first, first.replace("C-", "X-", 1), 1), encoding="utf-8")
    with pytest.raises(ValueError) as e:
        bundle.check(bad)
    assert "years.csv: has a BOM" in str(e.value)
    assert "does not match" in str(e.value)
    assert "is not in chains" in str(e.value)
