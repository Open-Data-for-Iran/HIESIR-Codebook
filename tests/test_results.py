from pathlib import Path

import pytest

from hiesir_codebook import csv_io, results

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "5_results"


def _labels(path, key, rows):
    csv_io.write(path, [key, "label_en", "note", "source"], [{key: k, "label_en": v} for k, v in rows])
    return path


def test_every_id_needs_an_english_label(tmp_path):
    path = _labels(tmp_path / "l.csv", "chain_id", [("C-1-1383", "Rice"), ("C-2-1383", "")])
    with pytest.raises(ValueError, match="no English label for 1: C-2-1383"):
        results.read_labels(path, "chain_id", ["C-1-1383", "C-2-1383"])


def test_a_label_for_a_chain_that_is_gone_is_an_error(tmp_path):
    path = _labels(tmp_path / "l.csv", "chain_id", [("C-1-1383", "Rice"), ("C-9-1383", "Old")])
    with pytest.raises(ValueError, match="no longer exist: C-9-1383"):
        results.read_labels(path, "chain_id", ["C-1-1383"])


def test_two_labels_for_one_id_is_an_error(tmp_path):
    path = _labels(tmp_path / "l.csv", "group_id", [("G-011-1383", "Food"), ("G-011-1383", "Foods")])
    with pytest.raises(ValueError, match="two English labels"):
        results.read_labels(path, "group_id", ["G-011-1383"])


def test_every_item_has_one_chain_series_and_group():
    """items.csv is the crosswalk: one row per year and code, each with a
    chain, a series and a group at every level, all of which exist."""
    items = csv_io.read(OUT / "items.csv")
    keys = [(r["year"], r["expenditure_code"]) for r in items]
    assert len(keys) == len(set(keys))
    chains = {r["chain_id"]: r for r in csv_io.read(OUT / "chains.csv")}
    series = {r["series_id"] for r in csv_io.read(OUT / "series.csv")}
    groups = {r["group_id"] for r in csv_io.read(OUT / "groups.csv")}
    members = csv_io.read(ROOT / "output" / "4_groups" / "members.csv")
    assert len(items) == len(members)
    for r in items:
        assert chains[r["chain_id"]]["series_id"] == r["series_id"] in series
        assert chains[r["chain_id"]]["expenditure_code"] == r["expenditure_code"]
        assert all(r[f"group_l{n}"] in groups for n in (2, 3) if r[f"group_l{n}"])
        assert r["label_en"]


def test_a_series_is_labelled_by_its_last_chain():
    chains = {r["chain_id"]: r for r in csv_io.read(OUT / "chains.csv")}
    for s in csv_io.read(OUT / "series.csv"):
        last = chains[s["chains"].split()[-1]]
        assert (s["label_fa"], s["label_en"]) == (last["label_fa"], last["label_en"])


def test_change_chains_is_the_long_form_of_changes():
    long = {(r["change_id"], r["side"], r["chain_id"]) for r in csv_io.read(OUT / "change_chains.csv")}
    wide = {
        (c["change_id"], side, x)
        for c in csv_io.read(OUT / "changes.csv")
        for side in ("from", "to")
        for x in c[f"{side}_chains"].split()
    }
    assert long == wide


def test_results_are_up_to_date(tmp_path):
    """output/5_results/ must match stages 2 to 4 and the English labels in
    curated/; if this fails, run `uv run hiesir-codebook build --no-extract`."""
    results.main(
        corrected=ROOT / "output" / "2_corrected",
        items=ROOT / "output" / "3_items",
        groups=ROOT / "output" / "4_groups",
        curated_items=ROOT / "curated" / "3_items",
        curated_groups=ROOT / "curated" / "4_groups",
        out=tmp_path,
    )
    names = sorted(p.name for p in OUT.glob("*.csv"))
    assert names == sorted(p.name for p in tmp_path.glob("*.csv"))
    for name in names:
        assert (tmp_path / name).read_bytes() == (OUT / name).read_bytes(), name
