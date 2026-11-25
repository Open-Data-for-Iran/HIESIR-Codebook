import pytest

from hiesir_codebook.linking.chains import build_chains, read_chains, write_chains
from hiesir_codebook.linking.compare import Item

YEARS = [1, 2, 3, 4, 5]


def _items(year, *rows):
    return [Item(year, 1, code, text) for code, text in rows]


DATA = {
    1: _items(1, ("011", "برنج طارم"), ("012", "آبگرمکن گازی"), ("013", "پاکت نامه"), ("014", "سمعک")),
    2: _items(2, ("011", "برنج  طارم،"), ("012", "کولرگازی"), ("013", "پاکت‌نامه و هزینه بسته‌بندی")),
    3: _items(3, ("012", "کولرگازی"), ("013", "پاکت‌نامه و هزینه بسته‌بندی")),
    4: _items(4, ("011", "برنج طارم"), ("012", "کولر گازی")),
    5: _items(5, ("014", "سمعک")),
}


def test_one_code_and_one_label_per_chain():
    chains = {c.id: c for c in build_chains(DATA, max_gap=2)}
    assert chains["C-011-1"].years == [1, 2, 4]  # trivial differences, missing in year 3
    assert chains["C-012-1"].years == [1]
    assert chains["C-012-2"].years == [2, 3, 4]  # "کولرگازی" / "کولر گازی": same label
    assert chains["C-013-1"].years == [1]
    assert chains["C-013-2"].years == [2, 3]  # broadened label: a new chain
    # missing from three questionnaires: more than the gap allows
    assert chains["C-014-1"].years == [1]
    assert chains["C-014-5"].years == [5]


def test_code_printed_twice_is_refused():
    # the structure check of output/2_corrected/ rules it out; chains do not guess
    data = {**DATA, 3: _items(3, ("012", "کولرگازی"), ("012", "کولر آبی"))}
    with pytest.raises(ValueError, match="printed twice"):
        build_chains(data)


def test_every_item_in_one_chain():
    covered = sorted((y, c.code) for c in build_chains(DATA) for y in c.years)
    assert covered == sorted((y, it.code) for y, items in DATA.items() for it in items)


def test_chains_round_trip(tmp_path):
    chains = build_chains(DATA)
    write_chains(chains, tmp_path / "chains.csv", YEARS)
    back = read_chains(tmp_path / "chains.csv", YEARS)
    assert sorted((c.id, c.code, c.text, c.years) for c in back) == sorted(
        (c.id, c.code, c.text, c.years) for c in chains
    )


def test_matched_is_up_to_date(tmp_path):
    """output/3_items/chains.csv and links.csv must match output/2_corrected/;
    if this fails, run `uv run hiesir-codebook build --no-extract`."""
    from pathlib import Path

    from hiesir_codebook.linking.compare import YEARS as ALL_YEARS
    from hiesir_codebook.linking.compare import load_year
    from hiesir_codebook.linking.relations import (
        build_relations,
        conflicts,
        load_decisions,
        write_links,
        write_suggested,
    )

    root = Path(__file__).resolve().parents[1]
    matched = root / "output" / "3_items"
    chains = build_chains({y: load_year(y, root / "output" / "2_corrected") for y in ALL_YEARS})
    write_chains(chains, tmp_path / "chains.csv", ALL_YEARS)
    decisions = load_decisions(root / "curated" / "3_items" / "links.csv")
    relations, stale = build_relations(chains, decisions, ALL_YEARS)
    assert not stale, [str(d) for d in stale]
    assert not conflicts(relations), conflicts(relations)
    write_links(relations, tmp_path / "links.csv")
    write_suggested(relations, tmp_path / "suggested")
    for name in ("chains.csv", "links.csv", "suggested/links.csv"):
        assert (tmp_path / name).read_bytes() == (matched / name).read_bytes(), name
