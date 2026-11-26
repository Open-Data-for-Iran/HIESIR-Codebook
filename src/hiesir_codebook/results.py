"""The results: one flat folder, one table per thing, for people who use the codebook.

Stages 1 to 4 each keep what the next stage needs; this one gathers what a
user of the codebook wants, without having to know the stages:

- ``items.csv``: every item of every year (year + expenditure code) with its
  chain, its series and its group at levels 2, 3 and 4: the crosswalk to
  join with the household data;
- ``chains.csv``, ``series.csv``, ``groups.csv``: one row each, with the
  Persian label and the English one;
- ``changes.csv`` and ``group_changes.csv``: the changes between chains and
  between groups; ``change_chains.csv`` is ``from_chains`` / ``to_chains``
  in long form, one row per chain on each side of a change.

The English labels are hand-kept: ``curated/3_items/labels_en.csv`` (per
chain) and ``curated/4_groups/labels_en.csv`` (per group).  A series is
labelled by its last chain, in English as in Persian.  Every text column is
``label_fa`` or ``label_en``.

Nothing here is decided anew: the stage only joins.  It checks that every
item has one chain and one series and a group at each level, and that every
chain and group has an English label and no label names a chain or group
that is gone.

Output: ``output/5_results/``.
"""

from __future__ import annotations

from pathlib import Path

from . import CORRECTED, CURATED_GROUPS, CURATED_ITEMS, GROUPS, ITEMS, RESULTS, csv_io
from .linking.chains import read_chains
from .linking.compare import YEARS

ITEM_COLUMNS = [
    "year",
    "expenditure_code",
    "section",
    "code",
    "sub",
    "label_fa",
    "label_en",
    "chain_id",
    "series_id",
    "group_l2",
    "group_l3",
    "group_l4",
    "page",
    "top",
    "bottom",
    "left",
    "right",
]
CHAIN_COLUMNS = [
    "chain_id",
    "series_id",
    "section",
    "expenditure_code",
    "first_year",
    "last_year",
    "missing_years",
    "label_fa",
    "label_en",
]
SERIES_COLUMNS = [
    "series_id",
    "section",
    "first_year",
    "last_year",
    "missing_years",
    "codes",
    "chains",
    "starts",
    "ends",
    "label_fa",
    "label_en",
]
GROUP_COLUMNS = [
    "group_id",
    "section",
    "level",
    "code",
    "parent_id",
    "first_year",
    "last_year",
    "missing_years",
    "items",
    "label_fa",
    "label_en",
]
CHANGE_COLUMNS = [
    "change_id",
    "type",
    "detail",
    "year",
    "from_chains",
    "to_chains",
    "score",
    "decided_by",
    "verified",
    "note",
    "from_label_fa",
    "to_label_fa",
]
CHANGE_CHAIN_COLUMNS = ["change_id", "side", "chain_id"]
GROUP_CHANGE_COLUMNS = [
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
    "note",
    "from_label_fa",
    "to_label_fa",
    "item_chains",
]


def read_labels(path: Path, key: str, ids: list[str]) -> dict[str, str]:
    """The English label of each of ``ids`` from ``path`` (columns ``key``,
    ``label_en``); every id must have one, and no row may name another id."""
    labels: dict[str, str] = {}
    for r in csv_io.read(path):
        if r[key] in labels:
            raise ValueError(f"{path.as_posix()}: {r[key]} has two English labels")
        labels[r[key]] = r["label_en"].strip()
    known = set(ids)
    gone = sorted(k for k in labels if k not in known)
    missing = [i for i in ids if not labels.get(i)]
    problems = []
    if missing:
        problems.append(f"no English label for {len(missing)}: {' '.join(missing[:10])}")
    if gone:
        problems.append(f"labels for {len(gone)} that no longer exist: {' '.join(gone[:10])}")
    if problems:
        raise ValueError(f"{path.as_posix()}: " + "; ".join(problems))
    return labels


def build(
    corrected: Path = CORRECTED,
    items: Path = ITEMS,
    groups: Path = GROUPS,
    chain_labels: Path = CURATED_ITEMS / "labels_en.csv",
    group_labels: Path = CURATED_GROUPS / "labels_en.csv",
    years: list[int] = YEARS,
) -> dict[str, tuple[list[str], list[dict[str, str]]]]:
    """Every results table, by file name: (columns, rows)."""
    chains = read_chains(items / "chains.csv", years)
    chain_rows = {r["chain_id"]: r for r in csv_io.read(items / "chains.csv")}
    series_rows = csv_io.read(items / "series.csv")
    group_rows = csv_io.read(groups / "groups.csv")
    en_chain = read_labels(chain_labels, "chain_id", list(chain_rows))
    en_group = read_labels(group_labels, "group_id", [r["group_id"] for r in group_rows])

    # chain -> series, and (year, code) -> chain
    series_of: dict[str, str] = {}
    for s in series_rows:
        for c in s["chains"].split():
            if c in series_of:
                raise ValueError(f"chain {c} is in two series: {series_of[c]} and {s['series_id']}")
            series_of[c] = s["series_id"]
    no_series = [c for c in chain_rows if c not in series_of]
    if no_series:
        raise ValueError(f"chains in no series: {' '.join(no_series[:10])}")
    chain_of: dict[tuple[int, str], str] = {}
    for c in chains:
        for y in c.years:
            chain_of[y, c.code] = c.id
    member = {(int(r["year"]), r["expenditure_code"]): r for r in csv_io.read(groups / "members.csv")}

    item_rows = []
    for y in years:
        for r in csv_io.read(corrected / f"questionnaire_{y}.csv"):
            if r["kind"] != "item" or not r["expenditure_code"]:
                continue
            key = (y, r["expenditure_code"])
            if key not in chain_of:
                raise ValueError(f"{y} {key[1]}: an item in no chain")
            if key not in member:
                raise ValueError(f"{y} {key[1]}: an item in no group (members.csv)")
            cid, m = chain_of[key], member[key]
            item_rows.append(
                {
                    "year": str(y),
                    "expenditure_code": key[1],
                    "section": r["section"],
                    "code": r["code"],
                    "sub": r["sub"],
                    "label_fa": r["description"],
                    "label_en": en_chain[cid],
                    "chain_id": cid,
                    "series_id": series_of[cid],
                    "group_l2": m["level_2"],
                    "group_l3": m["level_3"],
                    "group_l4": m["level_4"],
                    **{k: r[k] for k in ("page", "top", "bottom", "left", "right")},
                }
            )
    if len(item_rows) != len(chain_of):
        raise ValueError(f"{len(item_rows)} items but the chains name {len(chain_of)}")

    out_chains = [
        {
            "chain_id": cid,
            "series_id": series_of[cid],
            **{k: r[k] for k in CHAIN_COLUMNS[2:7]},
            "label_fa": r["text"],
            "label_en": en_chain[cid],
        }
        for cid, r in chain_rows.items()
    ]
    out_series = [
        {
            **{k: s[k] for k in SERIES_COLUMNS[:9]},
            "label_fa": s["text"],
            "label_en": en_chain[s["chains"].split()[-1]],
        }
        for s in series_rows
    ]
    out_groups = [
        {**{k: g[k] for k in GROUP_COLUMNS[:9]}, "label_fa": g["label"], "label_en": en_group[g["group_id"]]}
        for g in group_rows
    ]
    item_changes = csv_io.read(items / "changes.csv")
    out_changes = [
        {
            **{k: c[k] for k in CHANGE_COLUMNS[:10]},
            "from_label_fa": c["from_text"],
            "to_label_fa": c["to_text"],
        }
        for c in item_changes
    ]
    out_change_chains = [
        {"change_id": c["change_id"], "side": side, "chain_id": x}
        for c in item_changes
        for side in ("from", "to")
        for x in c[f"{side}_chains"].split()
    ]
    out_group_changes = [
        {
            **{k: c[k] for k in GROUP_CHANGE_COLUMNS[:11]},
            "from_label_fa": c["from_label"],
            "to_label_fa": c["to_label"],
            "item_chains": c["item_chains"],
        }
        for c in csv_io.read(groups / "changes.csv")
    ]
    return {
        "items.csv": (ITEM_COLUMNS, item_rows),
        "chains.csv": (CHAIN_COLUMNS, out_chains),
        "series.csv": (SERIES_COLUMNS, out_series),
        "groups.csv": (GROUP_COLUMNS, out_groups),
        "changes.csv": (CHANGE_COLUMNS, out_changes),
        "change_chains.csv": (CHANGE_CHAIN_COLUMNS, out_change_chains),
        "group_changes.csv": (GROUP_CHANGE_COLUMNS, out_group_changes),
    }


def main(
    *,
    corrected: Path = CORRECTED,
    items: Path = ITEMS,
    groups: Path = GROUPS,
    curated_items: Path = CURATED_ITEMS,
    curated_groups: Path = CURATED_GROUPS,
    out: Path = RESULTS,
) -> None:
    """The results, stages 2 to 4 + the English labels -> output/5_results/.

    Parameters
    ----------
    corrected
        The yearly CSVs.
    items
        The folder with chains.csv, changes.csv and series.csv.
    groups
        The folder with groups.csv, members.csv and changes.csv.
    curated_items
        The folder with labels_en.csv for the chains.
    curated_groups
        The folder with labels_en.csv for the groups.
    out
        Where the tables go.
    """
    tables = build(
        corrected,
        items,
        groups,
        curated_items / "labels_en.csv",
        curated_groups / "labels_en.csv",
    )
    for name, (header, rows) in tables.items():
        csv_io.write(out / name, header, rows)
    print(
        ", ".join(f"{len(rows)} {name[:-4].replace('_', ' ')}" for name, (_, rows) in tables.items())
        + f" -> {out.as_posix()}/"
    )
