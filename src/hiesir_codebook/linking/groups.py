"""Matching, groups: the group headers of the questionnaires across years.

A *group* is one printed group header, its section and its code as printed
(``0111``, ``01121, 01122``, ``0314 M``), followed through
``output/2_corrected/`` for as long as it is printed, skipping at most
``MAX_GAP`` questionnaires, like an item chain.  Its label may change; the
latest one is shown.  Every item of every year sits under the groups whose
headers are above it, one per level (2-4).

Where the items go tells how the groups relate.  When an item continues
from one year to the next (inside its chain, through a link, or through a
merge, split or regrouping that is not rejected) and the group above it at
some level is a different one, the item *flows* from the old group to the
new one.  Every pair of groups with a flow is a group link; its shape gives
its relation:

=========== ===================================================================
relation    meaning
=========== ===================================================================
continued   the old group ends, the new one starts, and the items go from the
            one to the other: the same group under another code
            (``0313`` -> ``0313 M``, ``01192, 01193`` -> ``01192, 01193, 01194``)
split       the old group ends and its items go to several new ones
merged      several old groups end in one new group
regrouped   both at once
moved       items moved between groups printed both before and after: an
            item reorganised, or a wrong item link
=========== ===================================================================

``decided_by`` says who decided a link.  The code decides it (``code``)
when it is not ``moved``, the codes are related (they share a code, or one
is the start of the other: ``096`` -> ``0961``, ``0313`` -> ``0313 M``), and
the labels match: identical, or differing only in spacing, ZWNJ,
punctuation, the conjunction (``،`` / ``و``), word order, generic words or
"etc." markers, as for item links.  Every other link is ``open`` until a
row in ``curated/4_groups/links.csv`` decides it (``curated``), with the
columns and decisions of ``curated/3_items/links.csv``: ``from_group``,
``to_group``, ``decision`` (confirm, reject, change, add), ``relation`` (for
change and add) and ``note`` (why).

Output (``output/4_groups/``):

* ``groups.csv``: one row per group;
* ``members.csv``: for every year and item, its group at each level,
  the crosswalk for summing items into groups;
* ``links.csv``: the group links, with their relation and decision.
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from .. import CORRECTED, CURATED_GROUPS, GROUPS, ITEMS, csv_io
from .chains import Chain, read_chains
from .compare import MAX_GAP, YEARS, compare
from .relations import DECISION_KINDS, VERIFIED, decided_by, definite

DECISIONS = CURATED_GROUPS / "links.csv"
RELATIONS = ("continued", "split", "merged", "regrouped", "moved")
LEVELS = (2, 3, 4)

# (year, expenditure code) -> {level: group id}
Placement = dict[tuple[int, str], dict[int, str]]
# (item chain id, (year, code) before, (year, code) after)
Step = tuple[str, tuple[int, str], tuple[int, str]]


@dataclass
class Group:
    id: str
    section: int
    code: str
    level: int
    labels: dict[int, str] = field(default_factory=dict)  # year -> label
    parents: dict[int, str] = field(default_factory=dict)  # year -> id of the group above
    items: dict[int, set[str]] = field(default_factory=dict)  # year -> items under it, at any depth

    @property
    def years(self) -> list[int]:
        return sorted(self.labels)

    @property
    def label(self) -> str:
        return self.labels[self.years[-1]]


def codes_of(code: str) -> set[str]:
    """'01121, 01122' -> {'01121', '01122'}; '0314 M' -> {'0314'}."""
    return {re.sub(r"\D", "", c) for c in code.split(",")}


def related_codes(a: str, b: str) -> bool:
    """Do two group codes share a code, or is one the start of the other?"""
    return any(x.startswith(y) or y.startswith(x) for x in codes_of(a) for y in codes_of(b))


def same_labels(a: str, b: str) -> bool:
    """Do two labels say the same thing, as far as the code can tell?
    Identical, or differing only in spacing, ZWNJ, punctuation, hamza, the
    conjunction, word order, generic words or "etc." markers."""
    return a == b or compare(a, b).kind == "same" or definite(a, b)


def _slug(code: str) -> str:
    """'01121, 01122' -> '01121+01122'; '0314 M' -> '0314M'."""
    return "+".join(c.replace(" ", "") for c in code.split(", "))


def build_groups(
    rows_by_year: dict[int, list[dict[str, str]]], max_gap: int = MAX_GAP
) -> tuple[list[Group], Placement]:
    """The groups of the questionnaires (rows as in ``output/2_corrected/``)
    and the group of every item at each level."""
    years = sorted(rows_by_year)
    groups: list[Group] = []
    ids: set[str] = set()
    current: dict[tuple[int, str], Group] = {}
    placement: Placement = {}
    for yi, year in enumerate(years):
        window = set(years[max(0, yi - max_gap - 1) : yi + 1])
        stack: dict[int, Group] = {}
        for r in rows_by_year[year]:
            if r["kind"] == "section":
                stack = {}
            elif r["kind"] == "header":
                key, level = (int(r["section"]), r["code"]), int(r["level"])
                g = current.get(key)
                if g is None or g.years[-1] not in window:
                    gid, n = f"{_slug(r['code'])}-{year}", 2
                    while gid in ids:  # the same code in another section
                        gid, n = f"{_slug(r['code'])}-{year}-{n}", n + 1
                    ids.add(gid)
                    g = current[key] = Group(gid, key[0], r["code"], level)
                    groups.append(g)
                g.labels.setdefault(year, r["description"])
                g.level = level
                stack = {k: v for k, v in stack.items() if k < level}
                if stack:
                    g.parents.setdefault(year, stack[max(stack)].id)
                stack[level] = g
            elif r["kind"] == "item" and r["expenditure_code"]:
                code = r["expenditure_code"]
                placement.setdefault((year, code), {k: v.id for k, v in stack.items()})
                for g in stack.values():
                    g.items.setdefault(year, set()).add(code)
    return groups, placement


def item_steps(
    chains: list[Chain], links: list[tuple[str, str]], relations: list[tuple[list[str], list[str]]]
) -> list[Step]:
    """Every step from one year to the next where an item continues: inside
    its chain, through a link, or from each chain a relation ends to each it
    starts."""
    by_id = {c.id: c for c in chains}
    steps: list[Step] = []
    for c in chains:
        steps += [(c.id, (a, c.code), (b, c.code)) for a, b in zip(c.years, c.years[1:], strict=False)]
    pairs = [*links, *((a, b) for srcs, dsts in relations for a in srcs for b in dsts if a != b)]
    for a, b in pairs:
        ca, cb = by_id[a], by_id[b]
        steps.append((a, (ca.years[-1], ca.code), (cb.years[0], cb.code)))
    return steps


@dataclass
class GroupLink:
    source: Group
    target: Group
    year: int
    items: set[str]  # item chains that went from source to target
    relation: str = ""
    needs_verification: bool = False
    verified: str = ""
    note: str = ""
    id: str = ""

    @property
    def key(self) -> tuple[str, str]:
        return self.source.id, self.target.id

    @property
    def before(self) -> int | None:
        """The last year the source is printed before the link."""
        ys = [y for y in self.source.years if y < self.year]
        return ys[-1] if ys else None

    @property
    def from_label(self) -> str:
        return self.source.labels[self.before] if self.before else self.source.label

    @property
    def to_label(self) -> str:
        return self.target.labels.get(self.year, self.target.label)

    @property
    def decided_by(self) -> str:
        return decided_by(self.needs_verification, self.verified)


def find_links(groups: list[Group], placement: Placement, steps: list[Step]) -> list[GroupLink]:
    """Group links from the item flows, with their relation."""
    by_id = {g.id: g for g in groups}
    flows: dict[tuple[str, str, int], set[str]] = defaultdict(set)
    for item, before, after in steps:
        pa, pb = placement.get(before), placement.get(after)
        if not pa or not pb:
            continue
        for lv in LEVELS:
            if lv in pa and lv in pb and pa[lv] != pb[lv]:
                flows[(pa[lv], pb[lv], after[0])].add(item)
    out_of: dict[tuple[str, int], set[str]] = defaultdict(set)
    into: dict[tuple[str, int], set[str]] = defaultdict(set)
    for a, b, y in flows:
        out_of[(a, y)].add(b)
        into[(b, y)].add(a)
    links = []
    for (a, b, y), items in flows.items():
        src, dst = by_id[a], by_id[b]
        if src.years[-1] < y and dst.years[0] == y:
            many_out, many_in = len(out_of[(a, y)]) > 1, len(into[(b, y)]) > 1
            relation = {
                (False, False): "continued",
                (True, False): "split",
                (False, True): "merged",
                (True, True): "regrouped",
            }[(many_out, many_in)]
        else:
            relation = "moved"
        lk = GroupLink(src, dst, y, items, relation)
        lk.needs_verification = not (
            relation != "moved"
            and related_codes(src.code, dst.code)
            and same_labels(lk.from_label, lk.to_label)
        )
        links.append(lk)
    return links


@dataclass
class Decision:
    from_group: str
    to_group: str
    decision: str
    relation: str
    note: str

    def __str__(self) -> str:
        return f"{self.from_group} -> {self.to_group} {self.decision}"


def load_decisions(path: Path = DECISIONS) -> list[Decision]:
    if not path.exists():
        return []
    out = [
        Decision(r["from_group"], r["to_group"], r["decision"], r["relation"], r["note"])
        for r in csv_io.read(path)
    ]
    for d in out:
        if d.decision not in DECISION_KINDS:
            raise ValueError(f"{path}: unknown decision {d.decision!r} ({d})")
        if d.decision in ("change", "add") and d.relation not in RELATIONS:
            raise ValueError(f"{path}: {d.decision} needs a relation, one of {', '.join(RELATIONS)} ({d})")
        if not d.note.strip():
            raise ValueError(f"{path}: every decision needs a note ({d})")
    return out


def apply_decisions(
    links: list[GroupLink], decisions: list[Decision], groups: list[Group]
) -> tuple[list[GroupLink], list[Decision]]:
    """Apply the curated decisions; return the links and the stale decisions."""
    by_key = {lk.key: lk for lk in links}
    by_id = {g.id: g for g in groups}
    stale = []
    for d in decisions:
        lk = by_key.get((d.from_group, d.to_group))
        if d.decision == "add":
            if lk is not None or d.from_group not in by_id or d.to_group not in by_id:
                stale.append(d)
                continue
            dst = by_id[d.to_group]
            lk = GroupLink(by_id[d.from_group], dst, dst.years[0], set(), d.relation)
            links.append(lk)
        elif lk is None:
            stale.append(d)
            continue
        elif d.decision == "change":
            lk.relation = d.relation
        lk.needs_verification, lk.verified, lk.note = False, VERIFIED[d.decision], d.note
    return links, stale


def build_links(
    groups: list[Group], placement: Placement, steps: list[Step], decisions: list[Decision]
) -> tuple[list[GroupLink], list[Decision]]:
    """Every group link, with the decisions applied, in order and numbered."""
    links, stale = apply_decisions(find_links(groups, placement, steps), decisions, groups)
    links.sort(key=lambda lk: (lk.year, lk.source.section, lk.source.code, lk.target.code))
    for i, lk in enumerate(links, 1):
        lk.id = f"G{i:04d}"
    return links, stale


# --- files ---------------------------------------------------------------------


def _read(path: Path) -> list[dict[str, str]]:
    return csv_io.read(path)


def read_links(path: Path) -> list[tuple[str, str]]:
    """The links of ``links.csv`` that are not rejected."""
    return [(r["from_chain"], r["to_chain"]) for r in _read(path) if r["verified"] != "rejected"]


def read_relations(path: Path) -> list[tuple[list[str], list[str]]]:
    """The merges, splits and regroupings of ``relations.csv`` that are not rejected."""
    return [
        (r["from_chains"].split(), r["to_chains"].split()) for r in _read(path) if r["verified"] != "rejected"
    ]


def write_groups(groups: list[Group], path: Path, years: list[int] = YEARS) -> None:
    with csv_io.writer(
        path,
        [
            "group_id",
            "section",
            "level",
            "code",
            "parent_id",
            "first_year",
            "last_year",
            "missing_years",
            "items",
            "label",
        ],
    ) as w:
        for g in groups:
            ys = g.years
            missing = " ".join(str(y) for y in years if ys[0] <= y <= ys[-1] and y not in g.labels)
            w.writerow(
                [
                    g.id,
                    g.section,
                    g.level,
                    g.code,
                    g.parents.get(ys[-1], ""),
                    ys[0],
                    ys[-1],
                    missing,
                    len(g.items.get(ys[-1], ())),
                    g.label,
                ]
            )


def write_members(placement: Placement, path: Path) -> None:
    with csv_io.writer(path, ["year", "expenditure_code", *(f"level_{lv}" for lv in LEVELS)]) as w:
        for (year, code), by_level in placement.items():
            w.writerow([year, code, *(by_level.get(lv, "") for lv in LEVELS)])


def write_links(links: list[GroupLink], path: Path) -> None:
    with csv_io.writer(
        path,
        [
            "link_id",
            "from_group",
            "to_group",
            "relation",
            "year",
            "items",
            "from_items",
            "to_items",
            "decided_by",
            "verified",
            "note",
            "from_label",
            "to_label",
            "item_chains",
        ],
    ) as w:
        for lk in links:
            w.writerow(
                [
                    lk.id,
                    lk.source.id,
                    lk.target.id,
                    lk.relation,
                    lk.year,
                    len(lk.items),
                    len(lk.source.items.get(lk.before, ())) if lk.before else "",
                    len(lk.target.items.get(lk.year, ())),
                    lk.decided_by,
                    lk.verified,
                    lk.note,
                    lk.from_label,
                    lk.to_label,
                    " ".join(sorted(lk.items)),
                ]
            )


def main(
    *,
    source: Path = CORRECTED,
    items: Path = ITEMS,
    out: Path = GROUPS,
    decisions: Path = DECISIONS,
    max_gap: int = MAX_GAP,
) -> None:
    """Group headers across years -> output/4_groups/.

    Parameters
    ----------
    source
        The yearly CSVs.
    items
        The folder with chains.csv, links.csv and relations.csv.
    out
        Where groups.csv, members.csv and links.csv go.
    decisions
        The curated group decisions.
    max_gap
        Questionnaires a group may skip.
    """
    rows = {y: _read(source / f"questionnaire_{y}.csv") for y in YEARS}
    groups, placement = build_groups(rows, max_gap)
    steps = item_steps(
        read_chains(items / "chains.csv"),
        read_links(items / "links.csv"),
        read_relations(items / "relations.csv"),
    )
    links, stale = build_links(groups, placement, steps, load_decisions(decisions))
    write_groups(groups, out / "groups.csv")
    write_members(placement, out / "members.csv")
    write_links(links, out / "links.csv")
    kinds = Counter(lk.relation for lk in links)
    verified = Counter(lk.verified for lk in links if lk.verified)
    print(
        f"{len(groups)} groups, {len(links)} group links ("
        + ", ".join(f"{k} {v}" for k, v in kinds.most_common())
        + f"): decided by the code {sum(lk.decided_by == 'code' for lk in links)}, "
        + f"in {decisions.as_posix()}: "
        + (", ".join(f"{k} {v}" for k, v in verified.items()) or "0")
        + f", open: {sum(lk.decided_by == 'open' for lk in links)}"
    )
    for d in stale:
        print(f"stale group decision: {d}")
