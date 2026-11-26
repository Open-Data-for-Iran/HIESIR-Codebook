"""Matching, groups: the group headers of the questionnaires across years.

A *group* is one printed group header, its section and its code as printed
(``0111``, ``01121, 01122``, ``0314 M``), followed through
``output/2_corrected/`` for as long as it is printed, skipping at most
``MAX_GAP`` questionnaires, like an item chain.  Its label may change; the
latest one is shown.  Only a header printed again for something else
starts a new group (:func:`reused`).  Every item of every year sits under the groups whose
headers are above it, one per level (2-4).

Where the items go tells how the groups relate.  When an item continues
from one year to the next (inside its chain, or through a change in
``output/3_items/changes.csv``: one that continues it, or a merge, split or
regrouping) and the group above it at
some level is a different one, the item *flows* from the old group to the
new one.  Every pair of groups with a flow is a group change; its shape
gives its type:

=========== ===================================================================
type        meaning
=========== ===================================================================
continued   the old group ends, the new one starts, and the items go from the
            one to the other: the same group under another code
            (``0313`` -> ``0313 M``, ``01192, 01193`` -> ``01192, 01193, 01194``)
split       the old group ends and its items go to several new ones
merged      several old groups end in one new group
regrouped   both at once
moved       items moved between groups printed both before and after: an
            item reorganised, or a wrong item change
=========== ===================================================================

``decided_by`` says who decided a group change.  The code decides it (``code``)
when it is not ``moved``, the codes are related (they share a code, or one
is the start of the other: ``096`` -> ``0961``, ``0313`` -> ``0313 M``), and
the labels match: identical, or differing only in spacing, ZWNJ,
punctuation, the conjunction (``،`` / ``و``), word order, generic words or
"etc." markers, as for item changes.  Every other one is ``open`` until a
row in ``curated/4_groups/changes.csv`` decides it (``curated``), with the
columns and decisions of ``curated/3_items/changes.csv``: ``from_group``,
``to_group``, ``decision`` (confirm, reject, amend, add), ``type`` (for
amend and add), ``note`` (why) and ``agent`` (who decided), with the
additions, rejections and amendments on top, as there.

A group's id is ``G-``, its code and its first year (``G-0111-1383``,
``G-01121+01122-1383``, ``G-0314M-1389``); a group change's is ``GL0001``.

Output (``output/4_groups/``):

* ``groups.csv``: one row per group;
* ``members.csv``: for every year and item, its group at each level,
  the crosswalk for summing items into groups;
* ``changes.csv``: the final group changes (decided by the code or in
  ``curated/4_groups/changes.csv``, and not rejected), with their type;
* ``suggested/changes.csv``: every group change the code found, with the
  type it found, and who decided it and how (``open``: not yet).
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field, replace
from pathlib import Path

from .. import CORRECTED, CURATED_GROUPS, GROUPS, ITEMS, csv_io
from .chains import Chain, read_chains
from .changes import CONTINUING, DECISION_TYPES, VERIFIED, decided_by, definite
from .compare import MAX_GAP, YEARS, compare

DECISIONS = CURATED_GROUPS / "changes.csv"
GROUP_TYPES = ("continued", "split", "merged", "regrouped", "moved")
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


def _items_below(rows: list[dict[str, str]]) -> dict[int, set[str]]:
    """For each header row (by index), the codes of the items printed under
    it, at any depth, until the next header at its level or above."""
    out: dict[int, set[str]] = {}
    open_: dict[int, int] = {}  # level -> index of its header row
    for i, r in enumerate(rows):
        if r["kind"] == "section":
            open_ = {}
        elif r["kind"] == "header":
            level = int(r["level"])
            open_ = {k: v for k, v in open_.items() if k < level}
            open_[level] = i
            out[i] = set()
        elif r["kind"] == "item" and r["expenditure_code"]:
            for i_header in open_.values():
                out[i_header].add(r["expenditure_code"])
    return out


def reused(g: Group, year: int, label: str, items: set[str], onward: dict[tuple[int, str], set[str]]) -> bool:
    """Is the header of ``g`` printed again in ``year`` for something else?
    Its label changes beyond a minor, broadened or narrowed wording, and none
    of the items it had the last time goes on under it: by its code, or
    through an item change (``onward``: (year, code) -> the codes it
    continues as in ``year``).  0631 A, «خدمات پزشکی» to 1394 and
    «خدمات بیمارستانی» from 1395, is *not* reused: its surgery items go on
    in the hospital services through a regrouping."""
    last = g.years[-1]
    if compare(g.labels[last], label).kind in ("same", "minor", "broadened", "narrowed"):
        return False
    before = g.items.get(last, set())
    return not any(({c} | onward.get((last, c), set())) & items for c in before)


def _slug(code: str) -> str:
    """'01121, 01122' -> '01121+01122'; '0314 M' -> '0314M'."""
    return "+".join(c.replace(" ", "") for c in code.split(", "))


def build_groups(
    rows_by_year: dict[int, list[dict[str, str]]], max_gap: int = MAX_GAP, steps: list[Step] = ()
) -> tuple[list[Group], Placement]:
    """The groups of the questionnaires (rows as in ``output/2_corrected/``)
    and the group of every item at each level.  ``steps`` (from
    :func:`item_steps`) tell which items go on, for :func:`reused`."""
    onward: dict[tuple[int, str], set[str]] = defaultdict(set)
    for _, before, after in steps:
        onward[before].add(after[1])
    years = sorted(rows_by_year)
    groups: list[Group] = []
    ids: set[str] = set()
    current: dict[tuple[int, str], Group] = {}
    placement: Placement = {}
    for yi, year in enumerate(years):
        window = set(years[max(0, yi - max_gap - 1) : yi + 1])
        stack: dict[int, Group] = {}
        below = _items_below(rows_by_year[year])
        for i, r in enumerate(rows_by_year[year]):
            if r["kind"] == "section":
                stack = {}
            elif r["kind"] == "header":
                key, level = (int(r["section"]), r["code"]), int(r["level"])
                g = current.get(key)
                if (
                    g is None
                    or g.years[-1] not in window
                    or (year not in g.labels and reused(g, year, r["description"], below[i], onward))
                ):
                    gid, n = f"G-{_slug(r['code'])}-{year}", 2
                    while gid in ids:  # the same code in another section
                        gid, n = f"G-{_slug(r['code'])}-{year}-{n}", n + 1
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
    chains: list[Chain],
    continuing: list[tuple[str, str]],
    breaking: list[tuple[list[str], list[str]] | tuple[list[str], list[str], int]],
) -> list[Step]:
    """Every step from one year to the next where an item continues: inside
    its chain, through a continuing change, or from each chain a breaking
    change ends to each it starts.  A breaking change may give its year: a chain on both
    sides goes on, so its own first or last year is not the change."""
    by_id = {c.id: c for c in chains}
    steps: list[Step] = []
    for c in chains:
        steps += [(c.id, (a, c.code), (b, c.code)) for a, b in zip(c.years, c.years[1:], strict=False)]
    pairs = [(a, b, None) for a, b in continuing]
    for srcs, dsts, *year in breaking:
        pairs += [(a, b, year[0] if year else None) for a in srcs for b in dsts if a != b]
    for a, b, year in pairs:
        ca, cb = by_id[a], by_id[b]
        if year is None:
            before, after = ca.years[-1], cb.years[0]
        else:
            before = max((y for y in ca.years if y < year), default=ca.years[-1])
            after = min((y for y in cb.years if y >= year), default=cb.years[0])
        steps.append((a, (before, ca.code), (after, cb.code)))
    return steps


@dataclass
class GroupChange:
    source: Group
    target: Group
    year: int
    items: set[str]  # item chains that went from source to target
    type: str = ""
    needs_verification: bool = False
    verified: str = ""
    note: str = ""
    id: str = ""
    found: GroupChange | None = None  # as the code found it, before any decision (None: added)

    @property
    def key(self) -> tuple[str, str]:
        return self.source.id, self.target.id

    @property
    def before(self) -> int | None:
        """The last year the source is printed before the change."""
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

    @property
    def final(self) -> bool:
        """In the results: decided (by the code or in ``curated/``) and not rejected."""
        return self.verified != "rejected" and self.decided_by != "open"


def find_changes(groups: list[Group], placement: Placement, steps: list[Step]) -> list[GroupChange]:
    """Group changes from the item flows, with their type."""
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
    changes = []
    for (a, b, y), items in flows.items():
        src, dst = by_id[a], by_id[b]
        if src.years[-1] < y and dst.years[0] == y:
            many_out, many_in = len(out_of[(a, y)]) > 1, len(into[(b, y)]) > 1
            kind = {
                (False, False): "continued",
                (True, False): "split",
                (False, True): "merged",
                (True, True): "regrouped",
            }[(many_out, many_in)]
        else:
            kind = "moved"
        ch = GroupChange(src, dst, y, items, kind)
        ch.needs_verification = not (
            kind != "moved" and related_codes(src.code, dst.code) and same_labels(ch.from_label, ch.to_label)
        )
        changes.append(ch)
    return changes


@dataclass
class Decision:
    from_group: str
    to_group: str
    decision: str
    type: str
    note: str

    def __str__(self) -> str:
        return f"{self.from_group} -> {self.to_group} {self.decision}"


def load_decisions(path: Path = DECISIONS) -> list[Decision]:
    if not path.exists():
        return []
    out = [
        Decision(r["from_group"], r["to_group"], r["decision"], r["type"], r["note"])
        for r in csv_io.read(path)
    ]
    for d in out:
        if d.decision not in DECISION_TYPES:
            raise ValueError(f"{path}: unknown decision {d.decision!r} ({d})")
        if d.decision in ("amend", "add") and d.type not in GROUP_TYPES:
            raise ValueError(f"{path}: {d.decision} needs a type, one of {', '.join(GROUP_TYPES)} ({d})")
        if not d.note.strip():
            raise ValueError(f"{path}: every decision needs a note ({d})")
    return out


def apply_decisions(
    changes: list[GroupChange], decisions: list[Decision], groups: list[Group]
) -> tuple[list[GroupChange], list[Decision]]:
    """Apply the curated decisions; return the changes and the stale decisions.
    Each change the code found keeps a copy of itself as found in ``found``."""
    for ch in changes:
        ch.found = replace(ch)
    by_key = {ch.key: ch for ch in changes}
    by_id = {g.id: g for g in groups}
    stale = []
    for d in decisions:
        ch = by_key.get((d.from_group, d.to_group))
        if d.decision == "add":
            if ch is not None or d.from_group not in by_id or d.to_group not in by_id:
                stale.append(d)
                continue
            dst = by_id[d.to_group]
            ch = GroupChange(by_id[d.from_group], dst, dst.years[0], set(), d.type)
            changes.append(ch)
        elif ch is None:
            stale.append(d)
            continue
        elif d.decision == "amend":
            ch.type = d.type
        ch.needs_verification, ch.verified, ch.note = False, VERIFIED[d.decision], d.note
    return changes, stale


def build_changes(
    groups: list[Group], placement: Placement, steps: list[Step], decisions: list[Decision]
) -> tuple[list[GroupChange], list[Decision]]:
    """Every group change, with the decisions applied, in order and numbered."""
    changes, stale = apply_decisions(find_changes(groups, placement, steps), decisions, groups)
    changes.sort(key=lambda ch: (ch.year, ch.source.section, ch.source.code, ch.target.code))
    for i, ch in enumerate(changes, 1):
        ch.id = f"GL{i:04d}"
    return changes, stale


# --- files ---------------------------------------------------------------------


def _read(path: Path) -> list[dict[str, str]]:
    return csv_io.read(path)


def read_changes(path: Path) -> tuple[list[tuple[str, str]], list[tuple[list[str], list[str], int]]]:
    """The final item changes of ``output/3_items/changes.csv``: the
    continuing ones (from chain, to chain), and the breaking ones (merges,
    splits and regroupings), with the year of each."""
    rows = _read(path)
    continuing = [(r["from_chains"], r["to_chains"]) for r in rows if r["type"] in CONTINUING]
    breaking = [
        (r["from_chains"].split(), r["to_chains"].split(), int(r["year"]))
        for r in rows
        if r["type"] not in CONTINUING
    ]
    return continuing, breaking


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


def write_changes(changes: list[GroupChange], path: Path, suggested: bool = False) -> None:
    """The final group changes; with ``suggested``, every change the code
    found, with its type as found and no note (the note is a decision's)."""
    note = [] if suggested else ["note"]
    with csv_io.writer(
        path,
        [
            "change_id",
            "from_group",
            "to_group",
            "type",
            "year",
            "items",
            "from_items",
            "to_items",
            "decided_by",
            "verified",
            *note,
            "from_label",
            "to_label",
            "item_chains",
        ],
    ) as w:
        for ch in changes:
            if not (ch.found is not None if suggested else ch.final):
                continue
            w.writerow(
                [
                    ch.id,
                    ch.source.id,
                    ch.target.id,
                    ch.found.type if suggested else ch.type,
                    ch.year,
                    len(ch.items),
                    len(ch.source.items.get(ch.before, ())) if ch.before else "",
                    len(ch.target.items.get(ch.year, ())),
                    ch.decided_by,
                    ch.verified,
                    *([] if suggested else [ch.note]),
                    ch.from_label,
                    ch.to_label,
                    " ".join(sorted(ch.items)),
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
        The folder with chains.csv and changes.csv.
    out
        Where groups.csv, members.csv and changes.csv go (the code's
        suggestions, before the decisions, in suggested/changes.csv).
    decisions
        The curated group decisions.
    max_gap
        Questionnaires a group may skip.
    """
    rows = {y: _read(source / f"questionnaire_{y}.csv") for y in YEARS}
    steps = item_steps(read_chains(items / "chains.csv"), *read_changes(items / "changes.csv"))
    groups, placement = build_groups(rows, max_gap, steps)
    changes, stale = build_changes(groups, placement, steps, load_decisions(decisions))
    write_groups(groups, out / "groups.csv")
    write_members(placement, out / "members.csv")
    write_changes(changes, out / "changes.csv")
    write_changes(changes, out / "suggested" / "changes.csv", suggested=True)
    kinds = Counter(ch.type for ch in changes)
    verified = Counter(ch.verified for ch in changes if ch.verified)
    print(
        f"{len(groups)} groups, {len(changes)} group changes ("
        + ", ".join(f"{k} {v}" for k, v in kinds.most_common())
        + f"): decided by the code {sum(ch.decided_by == 'code' for ch in changes)}, "
        + f"in {decisions.as_posix()}: "
        + (", ".join(f"{k} {v}" for k, v in verified.items()) or "0")
        + f", open: {sum(ch.decided_by == 'open' for ch in changes)}"
        + f"; final {sum(ch.final for ch in changes)}"
    )
    print(f"the code's suggestions, before the decisions -> {(out / 'suggested').as_posix()}/")
    for d in stale:
        print(f"stale group decision: {d}")
