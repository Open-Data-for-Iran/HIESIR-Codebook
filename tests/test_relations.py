from hiesir_codebook.chains import build_chains
from hiesir_codebook.compare import Item
from hiesir_codebook.relations import Decision, apply_decisions, code_reuse, definite, find_relations

YEARS = [1, 2, 3]


def _items(year, *rows, section=1):
    return [Item(year, section, code, text) for code, text in rows]


def _find(data, years=YEARS):
    chains = build_chains(data)
    rels = find_relations(chains, years)
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
    r = shape[("011-1", "011-2")]
    assert (r.relation, r.detail, r.decided_by) == ("same", "minor", "code")  # definite
    r = shape[("012-1", "012-2")]
    assert (r.relation, r.detail, r.decided_by) == ("same", "label_broadened", "open")
    assert ("013-1", "013-2") not in shape  # a reused code is no relation
    assert [(a.id, b.id) for a, b, _ in code_reuse(chains, [1, 2])] == [("013-1", "013-2")]


def test_recoded():
    data = {1: _items(1, ("021", "میز و صندلی")), 2: _items(2, ("022", "میز و صندلی"))}
    _, _, shape = _find(data, [1, 2])
    r = shape[("021-1", "022-2")]
    assert (r.relation, r.detail, r.needs_verification) == ("recoded", "", False)


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
    assert shape[("031-1 032-1", "031-2")].relation == "merged"
    # the source goes on with its label unchanged, so it is also a target
    assert shape[("041-1", "041-1 042-2")].relation == "split"
    assert shape[("041-1", "041-1 042-2")].year == 2
    assert shape[("051-1", "052-2 053-2")].relation == "split"  # public / private pair
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
    assert shape[("01112-1 01114-1", "01128-2")].relation == "merged"


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
    rels = find_relations(chains, [1, 2])
    f = frozenset
    decisions = [
        Decision(f({"012-1"}), f({"012-2"}), "confirm", "", "", "checked"),
        Decision(f({"013-1"}), f({"013-2"}), "add", "same", "label_reworded", "code reuse judged wrongly"),
        Decision(f({"014-1", "015-1"}), f({"016-2", "017-2"}), "add", "regrouped", "", "1395 dental"),
        Decision(f({"012-1"}), f({"999-1"}), "reject", "", "", "no such relation"),
    ]
    rels, stale = apply_decisions(rels, decisions, chains)
    got = {r.key: (r.relation, r.detail, r.verified, r.needs_verification) for r in rels}
    assert got[(f({"012-1"}), f({"012-2"}))] == ("same", "label_broadened", "confirmed", False)
    assert got[(f({"013-1"}), f({"013-2"}))] == ("same", "label_reworded", "added", False)
    assert got[(f({"014-1", "015-1"}), f({"016-2", "017-2"}))] == ("regrouped", "", "added", False)
    assert [str(d) for d in stale] == ["012-1 -> 999-1 reject"]


def test_change_decision():
    data = {1: _items(1, ("012", "پاکت نامه")), 2: _items(2, ("012", "پاکت‌نامه و هزینه بسته‌بندی"))}
    chains = build_chains(data)
    f = frozenset
    rels, stale = apply_decisions(
        find_relations(chains, [1, 2]),
        [Decision(f({"012-1"}), f({"012-2"}), "change", "same", "minor", "only packaging added")],
        chains,
    )
    (r,) = rels
    assert (r.relation, r.detail, r.verified, r.needs_verification, stale) == (
        "same",
        "minor",
        "changed",
        False,
        [],
    )


def _rel(src_codes, tgt_codes, detail, year=3):
    from hiesir_codebook.chains import Chain

    sources = [Chain(f"{c}-1", 1, c, "x", [1, 2]) for c in src_codes]
    targets = [Chain(f"{c}-3", 1, c, "y", [3]) for c in tgt_codes]
    from hiesir_codebook.relations import Relation

    return Relation(sources, targets, "same", detail, at=year)


# {year: {code: households}}: siblings 011112/011113 double from year 2 to 3
OCC = {
    2: {11111: 400, 11112: 100, 11113: 100, 21111: 500},
    3: {11111: 410, 11112: 200, 11113: 200, 21111: 1000, 21112: 900},
}


def test_evidence_relative_to_group():
    from hiesir_codebook.relations import evidence

    e = evidence(_rel(["011111"], ["011111"], "label_broadened"), OCC)
    assert (e.before_year, e.before, e.after, e.group) == (2, 400, 410, 2.0)
    assert str(e) == "households 2: 400 -> 3: 410, x0.51 relative to the group (x2.0); does not fit"
    # flat while the group doubled: half its share, too little for a broadening
    assert e.ratio == 0.51 and e.verdict == "does not fit"
    assert evidence(_rel(["011111"], ["011111"], "label_narrowed"), OCC).verdict == "fits"


def test_evidence_merge_and_missing_year():
    from hiesir_codebook.relations import evidence

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

    from hiesir_codebook.chains import read_chains
    from hiesir_codebook.correct import load_occurrence
    from hiesir_codebook.relations import build_relations, evidence, load_decisions

    root = Path(__file__).resolve().parents[1]
    path = root / "data" / "commodity_code_occurrence_1383-1403.csv"
    if not path.exists():
        pytest.skip(f"no {path.name} in data/ (not in git)")
    occ = load_occurrence(path)
    chains = read_chains(root / "output" / "3_items" / "chains.csv")
    curated = root / "curated" / "3_items"
    decisions = load_decisions(curated / "links.csv") + load_decisions(curated / "relations.csv")
    relations, _ = build_relations(chains, decisions)
    checked = 0
    for r in relations:
        if r.verified and "households" in r.note:
            e = evidence(r, occ, chains)
            assert e is not None and str(e) in r.note, r.id
            checked += 1
    assert checked > 200


def test_evidence_merge_counts_households_once():
    from hiesir_codebook.relations import evidence

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
    from hiesir_codebook.chains import Chain
    from hiesir_codebook.relations import evidence

    # 011112 and 011113 tripled because their codes were reused for other items in year 3
    occ = {2: {11111: 400, 11112: 100, 11113: 100}, 3: {11111: 400, 11112: 300, 11113: 300}}
    r = _rel(["011111"], ["011111"], "minor")
    assert evidence(r, occ).verdict == "does not fit"
    chains = [Chain("011112-1", 1, "011112", "a", [1, 2]), Chain("011112-3", 1, "011112", "b", [3])]
    e = evidence(r, occ, chains)
    assert e.group is None and e.ratio == 1.0 and e.verdict == "fits"


def test_decisions_go_in_their_own_file(tmp_path):
    import pytest

    from hiesir_codebook.relations import load_decisions

    link_head = "from_chain,to_chain,decision,relation,detail,note\n"
    links = tmp_path / "links.csv"
    links.write_text(link_head + "011-1,011-3,change,same,minor,x\n", encoding="utf-8")
    [d] = load_decisions(links)
    assert (d.from_chains, d.to_chains, d.detail) == ({"011-1"}, {"011-3"}, "minor")
    links.write_text(link_head + "011-1,011-3,add,merged,,x\n", encoding="utf-8")
    with pytest.raises(ValueError, match=r"belongs in relations.csv"):
        load_decisions(links)
    links.write_text(link_head + "011-1 012-1,011-3,add,same,,x\n", encoding="utf-8")
    with pytest.raises(ValueError, match="one chain to one chain"):
        load_decisions(links)
    rels = tmp_path / "relations.csv"
    rels.write_text(
        "from_chains,to_chains,decision,relation,detail,note\n011-1,011-3,add,recoded,,x\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match=r"belongs in links.csv"):
        load_decisions(rels)


def test_conflicts_between_links_and_relations():
    from hiesir_codebook.chains import Chain
    from hiesir_codebook.relations import Relation, conflicts

    a, b, c = (Chain(i, 1, i[:3], "x", [y]) for i, y in (("011-1", 1), ("012-1", 1), ("011-2", 2)))
    link = Relation([a], [c], "same", id="L0001")
    merge = Relation([a, b], [c], "merged", id="R0001")
    assert link.is_link and not merge.is_link
    # a ends in the merge yet continues; c starts in it yet continues a
    assert len(conflicts([link, merge])) == 2
    link.verified = "rejected"
    assert conflicts([link, merge]) == []
    # a chain that goes on with its label on both sides of a merge keeps its link
    keep = Relation([a, b], [a], "merged", id="R0002")
    assert conflicts([Relation([a], [c], "same", id="L0002"), keep]) == []
