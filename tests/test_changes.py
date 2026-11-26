from hiesir_codebook.linking.chains import build_chains
from hiesir_codebook.linking.changes import Decision, apply_decisions, code_reuse, definite, find_changes
from hiesir_codebook.linking.compare import Item

YEARS = [1, 2, 3]


def _items(year, *rows, section=1):
    return [Item(year, section, code, text) for code, text in rows]


def _find(data, years=YEARS):
    chains = build_chains(data)
    rels = find_changes(chains, years)
    shape = {
        (" ".join(sorted(c.id for c in r.sources)), " ".join(sorted(c.id for c in r.targets))): r
        for r in rels
    }
    return chains, rels, shape


def test_definite_changes():
    assert definite("جگر، دل، قلوه", "جگر، دل و قلوه")  # comma / و
    assert definite("کنسرو مرغ و نظایر آن", "کنسرو مرغ و ...")  # "etc." written two ways
    assert definite("شیر پاستوریزه", "انواع شیر پاستوریزه")  # generic word
    assert definite("کفش (غیر ماشینی)", "کفش (غیرماشینی)")  # spacing
    assert not definite("گردو، بادام", "آن")  # content changed
    assert not definite("ماست مخلوط و ماست کیسه‌ای", "ماست مخلوط")  # scope narrowed
    assert not definite("ویزیت روانپزشک G", "ویزیت روانپزشک NG")  # another provider


def test_same_code_and_code_reuse():
    data = {
        1: _items(1, ("011", "هلو، شلیل، شفتالو"), ("012", "پاکت نامه"), ("013", "آبگرمکن گازی")),
        2: _items(
            2, ("011", "هلو، شلیل و شفتالو"), ("012", "پاکت‌نامه و هزینه بسته‌بندی"), ("013", "کولرگازی")
        ),
    }
    chains, _, shape = _find(data, [1, 2])
    r = shape[("C-011-1", "C-011-2")]
    assert (r.type, r.detail, r.decided_by) == ("same", "minor", "code")  # definite
    r = shape[("C-012-1", "C-012-2")]
    assert (r.type, r.detail, r.decided_by) == ("same", "label_broadened", "open")
    assert ("C-013-1", "C-013-2") not in shape  # a reused code is no change
    assert [(a.id, b.id) for a, b, _ in code_reuse(chains, [1, 2])] == [("C-013-1", "C-013-2")]


def test_recoded():
    data = {1: _items(1, ("021", "میز و صندلی")), 2: _items(2, ("022", "میز و صندلی"))}
    _, _, shape = _find(data, [1, 2])
    r = shape[("C-021-1", "C-022-2")]
    assert (r.type, r.detail, r.needs_verification) == ("recoded", "", False)


def test_merged_and_split():
    data = {
        1: _items(
            1,
            ("031", "هزینه باغبانی"),
            ("032", "هزینه سرایداری"),
            ("041", "جوش شیرین، وانیل و مایه خمیر نان"),
            ("051", "خدمات آمبولانس"),
        ),
        2: _items(
            2,
            ("031", "هزینه باغبانی، سرایداری و میراب"),
            ("041", "جوش شیرین، وانیل و مایه خمیر نان"),
            ("042", "خمیر نان"),
            ("052", "خدمات آمبولانس G"),
            ("053", "خدمات آمبولانس NG"),
        ),
    }
    _, _, shape = _find(data, [1, 2])
    assert shape[("C-031-1 C-032-1", "C-031-2")].type == "merged"
    # the source goes on with its label unchanged, so it is also a target
    assert shape[("C-041-1", "C-041-1 C-042-2")].type == "split"
    assert shape[("C-041-1", "C-041-1 C-042-2")].year == 2
    assert shape[("C-051-1", "C-052-2 C-053-2")].type == "split"  # public / private pair
    assert all(r.needs_verification for r in shape.values())


def test_collapsed_group():
    # 1390: 21-inch TVs + other TVs -> all TVs
    data = {
        1: _items(
            1,
            ("01112", "انواع تلویزیون 21 اینچ رنگی تولید داخل"),
            ("01114", "سایر انواع تلویزیون رنگی داخلی"),
        ),
        2: _items(2, ("01128", "انواع تلویزیون رنگی داخلی")),
    }
    _, _, shape = _find(data, [1, 2])
    assert shape[("C-01112-1 C-01114-1", "C-01128-2")].type == "merged"


def test_decisions():
    data = {
        1: _items(
            1,
            ("012", "پاکت نامه"),
            ("013", "آبگرمکن گازی"),
            ("014", "ویزیت دندانپزشک"),
            ("015", "کشیدن دندان"),
        ),
        2: _items(
            2,
            ("012", "پاکت‌نامه و هزینه بسته‌بندی"),
            ("013", "کولرگازی"),
            ("016", "ویزیت و کشیدن دندان G"),
            ("017", "ویزیت و کشیدن دندان NG"),
        ),
    }
    chains = build_chains(data)
    rels = find_changes(chains, [1, 2])
    f = frozenset
    decisions = [
        Decision(f({"C-012-1"}), f({"C-012-2"}), "confirm", "", "", "checked"),
        Decision(f({"C-013-1"}), f({"C-013-2"}), "add", "same", "label_reworded", "code reuse misjudged"),
        Decision(f({"C-014-1", "C-015-1"}), f({"C-016-2", "C-017-2"}), "add", "regrouped", "", "1395 dental"),
        Decision(f({"C-012-1"}), f({"C-999-1"}), "reject", "", "", "no such change"),
    ]
    rels, stale = apply_decisions(rels, decisions, chains)
    got = {r.key: (r.type, r.detail, r.verified, r.needs_verification) for r in rels}
    assert got[(f({"C-012-1"}), f({"C-012-2"}))] == ("same", "label_broadened", "confirmed", False)
    assert got[(f({"C-013-1"}), f({"C-013-2"}))] == ("same", "label_reworded", "added", False)
    assert got[(f({"C-014-1", "C-015-1"}), f({"C-016-2", "C-017-2"}))] == ("regrouped", "", "added", False)
    assert [str(d) for d in stale] == ["C-012-1 -> C-999-1 reject"]


def test_change_decision():
    data = {1: _items(1, ("012", "پاکت نامه")), 2: _items(2, ("012", "پاکت‌نامه و هزینه بسته‌بندی"))}
    chains = build_chains(data)
    f = frozenset
    rels, stale = apply_decisions(
        find_changes(chains, [1, 2]),
        [Decision(f({"C-012-1"}), f({"C-012-2"}), "amend", "same", "minor", "only packaging added")],
        chains,
    )
    (r,) = rels
    assert (r.type, r.detail, r.verified, r.needs_verification, stale) == (
        "same",
        "minor",
        "amended",
        False,
        [],
    )


def _rel(src_codes, tgt_codes, detail, year=3):
    from hiesir_codebook.linking.chains import Chain

    sources = [Chain(f"{c}-1", 1, c, "x", [1, 2]) for c in src_codes]
    targets = [Chain(f"{c}-3", 1, c, "y", [3]) for c in tgt_codes]
    from hiesir_codebook.linking.changes import Change

    return Change(sources, targets, "same", detail, at=year)


# {year: {code: households}}: siblings 011112/011113 double from year 2 to 3
OCC = {
    2: {11111: 400, 11112: 100, 11113: 100, 21111: 500},
    3: {11111: 410, 11112: 200, 11113: 200, 21111: 1000, 21112: 900},
}


def test_evidence_relative_to_group():
    from hiesir_codebook.linking.changes import evidence

    e = evidence(_rel(["011111"], ["011111"], "label_broadened"), OCC)
    assert (e.before_year, e.before, e.after, e.group) == (2, 400, 410, 2.0)
    assert str(e) == "households 2: 400 -> 3: 410, x0.51 relative to the group (x2.0); does not fit"
    # flat while the group doubled: half its share, too little for a broadening
    assert e.ratio == 0.51 and e.verdict == "does not fit"
    assert evidence(_rel(["011111"], ["011111"], "label_narrowed"), OCC).verdict == "fits"


def test_evidence_merge_and_missing_year():
    from hiesir_codebook.linking.changes import evidence

    # group 0211 has no other code: plain ratio of the sums
    e = evidence(_rel(["021111"], ["021111", "021112"], ""), OCC)
    assert (e.before, e.after, e.group, e.ratio) == (500, 1900, None, 3.8)
    assert e.verdict == "does not fit"
    assert evidence(_rel(["011111"], ["011111"], "", year=5), OCC) is None
    small = {2: {11111: 10}, 3: {11111: 40}}
    assert evidence(_rel(["011111"], ["011111"], "minor"), small).verdict == "too few"


def test_curated_notes_match_evidence():
    """The household evidence quoted in the curated decision notes is what
    the code computes now."""
    from pathlib import Path

    import pytest

    from hiesir_codebook.linking.chains import read_chains
    from hiesir_codebook.linking.changes import build_changes, evidence, load_decisions
    from hiesir_codebook.usage import load_occurrence

    root = Path(__file__).resolve().parents[1]
    path = root / "data" / "code_usage.csv"
    if not path.exists():
        pytest.skip(f"no {path.name} in data/ (not in git)")
    from hiesir_codebook.linking.compare import YEARS as SURVEY_YEARS

    occ = {y: v for y, v in load_occurrence(path).items() if y in SURVEY_YEARS}  # as changes reads it
    chains = read_chains(root / "output" / "3_items" / "chains.csv")
    curated = root / "curated" / "3_items"
    decisions = load_decisions(curated / "changes.csv")
    changes, _ = build_changes(chains, decisions)
    checked = 0
    for r in changes:
        if r.verified and "households" in r.note:
            e = evidence(r, occ, chains)
            assert e is not None and str(e) in r.note, r.id
            checked += 1
    assert checked > 200


def test_evidence_merge_counts_households_once():
    from hiesir_codebook.linking.changes import evidence

    # tyres: the same households buy outer and inner tyres, so the merged code
    # has far fewer households than the sum of the two
    occ = {2: {21111: 3500, 21112: 3900}, 3: {21111: 4700}}
    e = evidence(_rel(["021111", "021112"], ["021111"], ""), occ)
    assert e.expected == (0.32, 1.67) and e.ratio == 0.64 and e.verdict == "fits"
    assert str(e).endswith("x0.64 (expected x0.32-1.67); fits")
    # a split: the targets may add up to more than the source, but neither may outgrow it
    occ = {2: {21111: 1000}, 3: {21112: 700, 21113: 600}}
    e = evidence(_rel(["021111"], ["021112", "021113"], ""), occ)
    assert e.expected == (0.6, 3.1) and e.verdict == "fits"


def test_evidence_ignores_reused_sibling_codes():
    from hiesir_codebook.linking.chains import Chain
    from hiesir_codebook.linking.changes import evidence

    # 011112 and 011113 tripled because their codes were reused for other items in year 3
    occ = {2: {11111: 400, 11112: 100, 11113: 100}, 3: {11111: 400, 11112: 300, 11113: 300}}
    r = _rel(["011111"], ["011111"], "minor")
    assert evidence(r, occ).verdict == "does not fit"
    chains = [Chain("011112-1", 1, "011112", "a", [1, 2]), Chain("011112-3", 1, "011112", "b", [3])]
    e = evidence(r, occ, chains)
    assert e.group is None and e.ratio == 1.0 and e.verdict == "fits"


def test_decisions_of_every_kind_in_one_file(tmp_path):
    import pytest

    from hiesir_codebook.linking.changes import load_decisions

    head = "from_chains,to_chains,decision,type,detail,note\n"
    decisions_csv = tmp_path / "changes.csv"
    decisions_csv.write_text(
        head + "011-1,011-3,amend,same,minor,x\n011-1 012-1,011-3,add,merged,,x\n", encoding="utf-8"
    )
    one, merge = load_decisions(decisions_csv)
    assert (one.from_chains, one.to_chains, one.detail) == ({"011-1"}, {"011-3"}, "minor")
    assert (merge.from_chains, merge.type) == ({"011-1", "012-1"}, "merged")
    decisions_csv.write_text(head + "011-1 012-1,011-3,add,same,,x\n", encoding="utf-8")
    with pytest.raises(ValueError, match="one chain to one chain"):
        load_decisions(decisions_csv)
    decisions_csv.write_text(head + "011-1,011-3,add,moved,,x\n", encoding="utf-8")
    with pytest.raises(ValueError, match="needs a type"):
        load_decisions(decisions_csv)


def test_curated_decisions_in_order():
    """In curated/, what the code would not do on its own comes first (add,
    reject, amend), the confirmations last, each block in id order."""
    from pathlib import Path

    from hiesir_codebook import csv_io
    from hiesir_codebook.linking.changes import decision_order

    root = Path(__file__).resolve().parents[1] / "curated"
    for path, key in (
        (root / "3_items" / "changes.csv", ("from_chains", "to_chains")),
        (root / "4_groups" / "changes.csv", ("from_group", "to_group")),
    ):
        rows = csv_io.read(path)
        assert rows == decision_order(rows, key), f"{path}: rows out of order"


def test_suggestions_apart_from_results(tmp_path):
    from hiesir_codebook import csv_io
    from hiesir_codebook.linking.chains import Chain
    from hiesir_codebook.linking.changes import (
        Decision,
        build_changes,
        write_changes,
        write_suggested,
    )

    chains = [
        Chain("011-1", 1, "011", "برنج طارم", [1]),
        Chain("011-2", 1, "011", "برنج طارم و هاشمی", [2]),
        Chain("012-1", 1, "012", "نان لواش", [1]),
        Chain("012-2", 1, "012", "نان لواش و تافتون", [2]),
        Chain("013-1", 1, "013", "پنیر", [1]),
        Chain("013-2", 1, "013", "پنیر محلی و پاستوریزه", [2]),
    ]
    pick = {"011": "amend", "012": "reject"}  # 013 stays open
    decisions = [
        Decision(frozenset({f"{c}-1"}), frozenset({f"{c}-2"}), d, "same" if d == "amend" else "", "", "why")
        for c, d in pick.items()
    ]
    changes, stale = build_changes(chains, decisions, [1, 2])
    assert not stale
    write_changes(changes, tmp_path / "changes.csv")
    write_suggested(changes, tmp_path / "suggested")
    final = csv_io.read(tmp_path / "changes.csv")
    found = csv_io.read(tmp_path / "suggested" / "changes.csv")
    # the results: only what was decided and not rejected, with the decision's detail
    assert [(r["from_chains"], r["verified"], r["detail"]) for r in final] == [("011-1", "amended", "")]
    # the suggestions: everything the code found, as found, and how it was decided
    assert [(r["from_chains"], r["decided_by"], r["verified"]) for r in found] == [
        ("011-1", "curated", "amended"),
        ("012-1", "curated", "rejected"),
        ("013-1", "open", ""),
    ]
    assert found[0]["detail"] == "label_broadened" and "note" not in found[0]


def test_conflicts_between_continuing_changes():
    from hiesir_codebook.linking.chains import Chain
    from hiesir_codebook.linking.changes import Change, conflicts

    a, b, c = (Chain(i, 1, i[:3], "x", [y]) for i, y in (("011-1", 1), ("012-1", 1), ("011-2", 2)))
    same = Change([a], [c], "same", id="L0001")
    merge = Change([a, b], [c], "merged", id="L0002")
    assert same.is_continuing and not merge.is_continuing
    # a ends in the merge yet continues; c starts in it yet continues a
    assert len(conflicts([same, merge])) == 2
    same.verified = "rejected"
    assert conflicts([same, merge]) == []
    # a chain that goes on with its label on both sides of a merge keeps its continuing change
    keep = Change([a, b], [a], "merged", id="L0003")
    assert conflicts([Change([a], [c], "same", id="L0004"), keep]) == []
