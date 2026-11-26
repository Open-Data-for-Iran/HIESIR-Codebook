from pathlib import Path

import pytest

from hiesir_codebook.linking.chains import Chain
from hiesir_codebook.linking.series import build_series, main

ROOT = Path(__file__).resolve().parents[1]


def _c(code, years, section=1, text="x"):
    return Chain(f"C-{code}-{years[0]}", section, code, text, list(years))


def test_links_join_chains_into_one_series():
    a = _c("011114", [1383, 1384, 1385, 1386])
    b = _c("011114", [1387, 1388])
    c = _c("011174", [1390])  # recoded, after a skipped year
    alone = _c("011111", [1383, 1388])
    series = build_series([a, b, c, alone], [(a.id, b.id), (b.id, c.id)])
    assert [s.id for s in series] == ["I-011111-1383", "I-011114-1383"]
    s = series[1]
    assert [x.id for x in s.chains] == [a.id, b.id, c.id]
    assert s.codes == ["011114", "011174"]
    assert s.years == [1383, 1384, 1385, 1386, 1387, 1388, 1390]


def test_merges_start_and_end_series_but_not_one_that_goes_on():
    burger = _c("011241", [1383, 1388])
    cutlet = _c("011242", [1383, 1388])
    merged = _c("011241", [1389, 1403])
    goes_on = _c("011243", [1383, 1403])
    rel = ("L0003", [burger.id, cutlet.id, goes_on.id], [merged.id, goes_on.id])
    by_chain = {s.chains[0].id: s for s in build_series([burger, cutlet, merged, goes_on], [], [rel])}
    assert by_chain[burger.id].ends == ["L0003"] and by_chain[burger.id].starts == []
    assert by_chain[cutlet.id].ends == ["L0003"]
    assert by_chain[merged.id].starts == ["L0003"] and by_chain[merged.id].ends == []
    assert by_chain[goes_on.id].starts == [] and by_chain[goes_on.id].ends == []


def test_a_chain_continues_through_one_change_onward():
    a, b, c = _c("1", [1383]), _c("2", [1384]), _c("3", [1384])
    with pytest.raises(ValueError, match="one change onward"):
        build_series([a, b, c], [(a.id, b.id), (a.id, c.id)])


def test_linked_chains_may_not_overlap():
    a, b = _c("1", [1383, 1385]), _c("2", [1385, 1386])
    with pytest.raises(ValueError, match="overlap"):
        build_series([a, b], [(a.id, b.id)])


def test_series_are_up_to_date(tmp_path):
    """output/3_items/series.csv must match chains.csv and changes.csv; if this
    fails, run `uv run hiesir-codebook build --no-extract`."""
    items = ROOT / "output" / "3_items"
    for name in ("chains.csv", "changes.csv"):
        (tmp_path / name).write_bytes((items / name).read_bytes())
    main(items=tmp_path)
    assert (tmp_path / "series.csv").read_bytes() == (items / "series.csv").read_bytes()
