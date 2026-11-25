from pathlib import Path

import pytest

from hiesir_codebook.linking.chains import Chain
from hiesir_codebook.linking.groups import (
    Decision,
    build_groups,
    build_links,
    item_steps,
    load_decisions,
    related_codes,
    same_labels,
)


def _q(*rows):
    """Questionnaire rows: ('s', section, title), ('h', section, level, code, label), ('i', section, code)."""
    out = []
    for r in rows:
        if r[0] == "s":
            out.append({"kind": "section", "section": str(r[1]), "description": r[2]})
        elif r[0] == "h":
            out.append(
                {
                    "kind": "header",
                    "section": str(r[1]),
                    "level": str(r[2]),
                    "code": r[3],
                    "description": r[4],
                }
            )
        else:
            out.append({"kind": "item", "section": str(r[1]), "expenditure_code": r[2]})
    return out


def _chain(code, *years):
    return Chain(f"{code}-{years[0]}", 1, code, code, list(years))


def test_related_codes():
    assert related_codes("0313", "0313 M")  # suffix added
    assert related_codes("01192, 01193", "01192, 01193, 01194")  # list grew
    assert related_codes("096", "0961")  # one level down
    assert not related_codes("0562 M", "062 M")
    assert not related_codes("06312 A", "06313 A")


def test_same_labels():
    assert same_labels("ادویه‌ها، چاشنی‌ها", "ادویه‌ها، چاشنی‌ها")  # identical
    assert same_labels("روغن‌ها و چربی‌ها و کره", "روغن‌ها، چربی‌ها و کره")  # و / ،
    assert same_labels("هزینه آموزشهای سطح‌بندی نشده", "هزینه آموزش‌های سطح‌بندی نشده")  # ZWNJ
    assert not same_labels("هزینه آموزش", "هزینه آموزش تحصیلات عالی")  # narrowed
    assert not same_labels("خدمات فرهنگی و تفریحی", "خدمات تفریحی")


def test_a_reused_header_starts_a_new_group():
    """The same header printed for something else: its label changes and
    none of its items goes on under it."""
    rows = {
        1: _q(("s", 6, "x"), ("h", 6, 3, "0631 A", "خدمات پزشکی"), ("i", 6, "063117")),
        2: _q(("s", 6, "x"), ("h", 6, 3, "0631 A", "خدمات بیمارستانی"), ("i", 6, "063141")),
    }
    groups, _ = build_groups(rows)
    assert [g.id for g in groups] == ["G-0631A-1", "G-0631A-2"]
    # an item that goes on under it, here through a relation, keeps one group
    steps = item_steps([_chain("063117", 1), _chain("063141", 2)], [], [(["063117-1"], ["063141-2"], 2)])
    groups, _ = build_groups(rows, steps=steps)
    assert [g.id for g in groups] == ["G-0631A-1"]
    # and so does a label that changes while the items stay
    rows[2] = _q(("s", 6, "x"), ("h", 6, 3, "0631 A", "خدمات بیمارستانی"), ("i", 6, "063117"))
    groups, _ = build_groups(rows)
    assert [g.id for g in groups] == ["G-0631A-1"]


def test_groups_and_members():
    rows = {
        1: _q(
            ("s", 1, "خوراکی"),
            ("h", 1, 2, "011", "مواد خوراکی"),
            ("h", 1, 3, "0111", "غلات"),
            ("i", 1, "011111"),
        ),
        2: _q(
            ("s", 1, "خوراکی"),
            ("h", 1, 2, "011", "مواد خوراکی"),
            ("h", 1, 3, "0111", "غلات و نان"),
            ("i", 1, "011111"),
        ),
    }
    groups, placement = build_groups(rows)
    assert [(g.id, g.years, g.label) for g in groups] == [
        ("G-011-1", [1, 2], "مواد خوراکی"),
        ("G-0111-1", [1, 2], "غلات و نان"),  # a new label keeps the group; the latest is shown
    ]
    assert groups[1].parents == {1: "G-011-1", 2: "G-011-1"}
    assert placement[(2, "011111")] == {2: "G-011-1", 3: "G-0111-1"}


def test_links_from_item_flows():
    # year 2: 0313 becomes 0313 M (same items) and 0314 is split into 0314 M and 0314 A;
    # item 031411 also moves between two groups printed in both years
    rows = {
        1: _q(
            ("s", 3, "پوشاک"),
            ("h", 3, 3, "0313", "سایر پوشاک"),
            ("i", 3, "031311"),
            ("h", 3, 3, "0314", "خدمات پوشاک"),
            ("i", 3, "031421"),
            ("i", 3, "031422"),
            ("h", 3, 3, "0315", "کفش"),
            ("i", 3, "031511"),
            ("h", 3, 3, "0316", "تعمیر کفش"),
        ),
        2: _q(
            ("s", 3, "پوشاک"),
            ("h", 3, 3, "0313 M", "سایر پوشاک"),
            ("i", 3, "031311"),
            ("h", 3, 3, "0314 M", "خدمات پوشاک"),
            ("i", 3, "031421"),
            ("h", 3, 3, "0315", "کفش"),
            ("h", 3, 3, "0316", "تعمیر کفش"),
            ("i", 3, "031511"),
            ("s", 13, "دوام"),
            ("h", 13, 3, "0314 A", "خدمات پوشاک"),
            ("i", 13, "031422"),
        ),
    }
    groups, placement = build_groups(rows)
    chains = [_chain(c, 1, 2) for c in ("031311", "031421", "031422", "031511")]
    links, stale = build_links(groups, placement, item_steps(chains, [], []), [])
    assert not stale
    got = {(lk.source.id, lk.target.id): (lk.relation, lk.decided_by) for lk in links}
    assert got == {
        ("G-0313-1", "G-0313M-2"): ("continued", "code"),
        ("G-0314-1", "G-0314M-2"): ("split", "code"),
        ("G-0314-1", "G-0314A-2"): ("split", "code"),
        ("G-0315-1", "G-0316-1"): ("moved", "open"),
    }
    assert [lk.id for lk in links] == ["GL0001", "GL0002", "GL0003", "GL0004"]


def test_item_links_carry_items_across_codes():
    rows = {
        1: _q(("s", 5, "x"), ("h", 5, 3, "0562 M", "خدمات خانگی"), ("i", 5, "056211")),
        2: _q(("s", 5, "x"), ("h", 5, 3, "0563 M", "خدمات خانگی"), ("i", 5, "056311")),
    }
    groups, placement = build_groups(rows)
    chains = [_chain("056211", 1), _chain("056311", 2)]
    steps = item_steps(chains, [("056211-1", "056311-2")], [])
    links, _ = build_links(groups, placement, steps, [])
    (lk,) = links
    assert (lk.key, lk.relation, lk.decided_by) == (("G-0562M-1", "G-0563M-2"), "continued", "open")
    links, stale = build_links(
        groups, placement, steps, [Decision("G-0562M-1", "G-0563M-2", "confirm", "", "same services")]
    )
    assert not stale and (links[0].verified, links[0].decided_by) == ("confirmed", "curated")


@pytest.mark.parametrize(
    ("new_label", "decided_by"),
    [
        ("روغن‌ها، چربی‌ها و کره", "code"),  # only the conjunction differs
        ("روغن‌ها و چربی‌ها", "open"),  # the label lost a word
    ],
)
def test_related_codes_still_need_matching_labels(new_label, decided_by):
    rows = {
        1: _q(("s", 1, "x"), ("h", 1, 3, "0115", "روغن‌ها و چربی‌ها و کره"), ("i", 1, "011511")),
        2: _q(("s", 1, "x"), ("h", 1, 3, "0115 M", new_label), ("i", 1, "011511")),
    }
    groups, placement = build_groups(rows)
    links, _ = build_links(groups, placement, item_steps([_chain("011511", 1, 2)], [], []), [])
    assert [(lk.relation, lk.decided_by) for lk in links] == [("continued", decided_by)]


def test_decisions_need_a_note(tmp_path):
    path = tmp_path / "groups.csv"
    path.write_text("from_group,to_group,decision,relation,note\na-1,b-2,confirm,,\n", encoding="utf-8")
    with pytest.raises(ValueError, match="note"):
        load_decisions(path)


def test_groups_are_up_to_date(tmp_path):
    """output/4_groups/groups.csv, members.csv and links.csv must
    match output/2_corrected/ and the item links; if this fails, run
    `uv run hiesir-codebook build --no-extract`."""
    from hiesir_codebook.linking import groups

    root = Path(__file__).resolve().parents[1]
    groups.main(
        source=root / "output" / "2_corrected",
        items=root / "output" / "3_items",
        out=tmp_path,
        decisions=root / "curated" / "4_groups" / "links.csv",
    )
    for name in ("groups.csv", "members.csv", "links.csv", "suggested/links.csv"):
        assert (tmp_path / name).read_bytes() == (root / "output" / "4_groups" / name).read_bytes(), name
