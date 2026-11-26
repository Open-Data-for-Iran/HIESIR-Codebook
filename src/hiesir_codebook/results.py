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
  in long form, one row per chain on each side of a change;
- ``years.csv``: every year from the first questionnaire PDF to the last,
  and whether the codebook covers it; ``pdfs.csv``: the PDFs, with where to
  download them;
- ``sections.csv`` and ``headers.csv``: the sections and group headers as
  printed each year, each section with its English label and each header
  with its group;
- ``code_corrections.csv`` and ``code_usage.csv``: the wrong codes in the
  raw data and how many households used each code.  ``raw_code`` is the code
  as the raw data stores it, a number without its leading zero.

The English labels are hand-kept: ``curated/2_corrected/labels_en.csv``
(per section wording), ``curated/3_items/labels_en.csv`` (per chain) and
``curated/4_groups/labels_en.csv`` (per group).  A series is
labelled by its last chain, in English as in Persian.  Every text column is
``label_fa`` or ``label_en``.

Nothing here is decided anew: the stage only joins.  It checks that every
item has one chain and one series and a group at each level, and that every
section, chain and group has an English label and no label names a chain or group
that is gone.

Output: ``output/5_results/``.
"""

from __future__ import annotations

from pathlib import Path

from . import (
    CORRECTED,
    CURATED_CORRECTED,
    CURATED_DATA,
    CURATED_GROUPS,
    CURATED_ITEMS,
    DATA_DIR,
    GROUPS,
    ITEMS,
    RESULTS,
    SUPPORTED_YEARS,
    csv_io,
)
from .extraction.pdfs import RELEASE_URL
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
YEAR_COLUMNS = ["year", "status", "pdfs", "items", "note"]
PDF_COLUMNS = ["year", "area", "name", "kind", "bytes", "sha256", "url"]
SECTION_COLUMNS = ["year", "section", "label_fa", "label_en", "recall_period", "page"]
HEADER_COLUMNS = [
    "year",
    "section",
    "level",
    "code",
    "group_id",
    "label_fa",
    "page",
    "top",
    "bottom",
    "left",
    "right",
]
CODE_CORRECTION_COLUMNS = ["year", "raw_code", "expenditure_code", "reason"]
CODE_USAGE_COLUMNS = ["year", "raw_code", "households", "expenditure_share"]

OLD_CODE_SCHEME = 1382
YEAR_NOTES = {
    "covered": "",
    "old_code_scheme": "a text PDF, but its 3+2 digit codes are not matched across years",
    "scan_only": "the PDF is a scan, without a text layer to extract",
    "no_pdf": "no questionnaire PDF in the collection",
}


def recall_period(label: str) -> str:
    """The recall period a section's label names: ``12_months``, ``month`` or
    empty (section 10, education, prints none from 1384 on)."""
    if "12 ماه گذشته" in label:
        return "12_months"
    return "month" if "ماه گذشته" in label else ""


def read_labels(path: Path, key: str | tuple[str, ...], ids: list) -> dict:
    """The English label of each of ``ids`` from ``path`` (columns ``key``,
    ``label_en``); every id must have one, and no row may name another id.
    With several key columns, an id is the tuple of their values."""

    def id_of(r: dict[str, str]):
        return r[key] if isinstance(key, str) else tuple(r[k] for k in key)

    def show(ids) -> str:
        return " ".join(i if isinstance(i, str) else "/".join(i) for i in ids[:10])

    labels: dict = {}
    for r in csv_io.read(path):
        i = id_of(r)
        if i in labels:
            raise ValueError(f"{path.as_posix()}: {show([i])} has two English labels")
        labels[i] = r["label_en"].strip()
    known = set(ids)
    gone = sorted(k for k in labels if k not in known)
    missing = [i for i in ids if not labels.get(i)]
    problems = []
    if missing:
        problems.append(f"no English label for {len(missing)}: {show(missing)}")
    if gone:
        problems.append(f"labels for {len(gone)} that no longer exist: {show(gone)}")
    if problems:
        raise ValueError(f"{path.as_posix()}: " + "; ".join(problems))
    return labels


def build(
    corrected: Path = CORRECTED,
    items: Path = ITEMS,
    groups: Path = GROUPS,
    section_labels: Path = CURATED_CORRECTED / "labels_en.csv",
    chain_labels: Path = CURATED_ITEMS / "labels_en.csv",
    group_labels: Path = CURATED_GROUPS / "labels_en.csv",
    data: Path = DATA_DIR,
    code_corrections: Path = CURATED_DATA / "code_corrections.csv",
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

    # (section, code) -> [(years printed, group id)]: the group of a printed header
    printed: dict[tuple[str, str], list[tuple[set[int], str]]] = {}
    for g in group_rows:
        missing = {int(y) for y in g["missing_years"].split()}
        span = set(range(int(g["first_year"]), int(g["last_year"]) + 1)) - missing
        printed.setdefault((g["section"], g["code"]), []).append((span, g["group_id"]))

    item_rows, section_rows, header_rows = [], [], []
    for y in years:
        for r in csv_io.read(corrected / f"questionnaire_{y}.csv"):
            if r["kind"] == "section":
                section_rows.append(
                    {
                        "year": str(y),
                        "section": r["section"],
                        "label_fa": r["description"],
                        "label_en": "",
                        "recall_period": recall_period(r["description"]),
                        "page": r["page"],
                    }
                )
                continue
            if r["kind"] == "header":
                found = [gid for span, gid in printed.get((r["section"], r["code"]), ()) if y in span]
                if len(found) != 1:
                    raise ValueError(f"{y} header {r['section']} {r['code']}: in {len(found)} groups")
                header_rows.append(
                    {
                        "year": str(y),
                        "section": r["section"],
                        "level": r["level"],
                        "code": r["code"],
                        "group_id": found[0],
                        "label_fa": r["description"],
                        **{k: r[k] for k in ("page", "top", "bottom", "left", "right")},
                    }
                )
                continue
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
    wordings = list(dict.fromkeys((r["section"], r["label_fa"]) for r in section_rows))
    en_section = read_labels(section_labels, ("section", "label_fa"), wordings)
    for r in section_rows:
        r["label_en"] = en_section[r["section"], r["label_fa"]]

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
    items_of: dict[int, int] = {}
    for r in item_rows:
        items_of[int(r["year"])] = items_of.get(int(r["year"]), 0) + 1
    pdf_rows = csv_io.read(data / "pdfs.csv")
    pdfs_of: dict[int, int] = {}
    kinds: dict[int, str] = {}
    for r in pdf_rows:
        pdfs_of[int(r["year"])] = pdfs_of.get(int(r["year"]), 0) + 1
        kinds[int(r["year"])] = r["kind"]
    year_rows = []
    for y in range(min(pdfs_of), max(pdfs_of) + 1):
        if y in SUPPORTED_YEARS:
            status = "covered"
        elif y == OLD_CODE_SCHEME:
            status = "old_code_scheme"
        elif kinds.get(y) == "scan":
            status = "scan_only"
        else:
            status = "no_pdf"
        year_rows.append(
            {
                "year": str(y),
                "status": status,
                "pdfs": str(pdfs_of.get(y, 0)),
                "items": str(items_of.get(y, 0)) if status == "covered" else "",
                "note": YEAR_NOTES[status],
            }
        )
    out_pdfs = [
        {**{k: r[k] for k in PDF_COLUMNS[:6]}, "url": f"{RELEASE_URL}/{r['name']}"}
        for r in sorted(pdf_rows, key=lambda r: (int(r["year"]), r["area"]))
    ]
    out_code_corrections = [
        {
            "year": r["year"],
            "raw_code": r["data_code"],
            "expenditure_code": r["expenditure_code"],
            "reason": r["reason"],
        }
        for r in csv_io.read(code_corrections)
    ]
    out_code_usage = [
        {
            "year": r["year"],
            "raw_code": r["expenditure_code"],
            "households": r["occurrence"],
            "expenditure_share": r["expenditure_share"],
        }
        for r in csv_io.read(data / "code_usage.csv")
    ]
    return {
        "years.csv": (YEAR_COLUMNS, year_rows),
        "pdfs.csv": (PDF_COLUMNS, out_pdfs),
        "sections.csv": (SECTION_COLUMNS, section_rows),
        "headers.csv": (HEADER_COLUMNS, header_rows),
        "items.csv": (ITEM_COLUMNS, item_rows),
        "chains.csv": (CHAIN_COLUMNS, out_chains),
        "series.csv": (SERIES_COLUMNS, out_series),
        "groups.csv": (GROUP_COLUMNS, out_groups),
        "changes.csv": (CHANGE_COLUMNS, out_changes),
        "change_chains.csv": (CHANGE_CHAIN_COLUMNS, out_change_chains),
        "group_changes.csv": (GROUP_CHANGE_COLUMNS, out_group_changes),
        "code_corrections.csv": (CODE_CORRECTION_COLUMNS, out_code_corrections),
        "code_usage.csv": (CODE_USAGE_COLUMNS, out_code_usage),
    }


def main(
    *,
    corrected: Path = CORRECTED,
    items: Path = ITEMS,
    groups: Path = GROUPS,
    curated_corrected: Path = CURATED_CORRECTED,
    curated_items: Path = CURATED_ITEMS,
    curated_groups: Path = CURATED_GROUPS,
    curated_data: Path = CURATED_DATA,
    data: Path = DATA_DIR,
    out: Path = RESULTS,
) -> None:
    """The results, stages 2 to 4 + the English labels + data/ -> output/5_results/.

    Parameters
    ----------
    corrected
        The yearly CSVs.
    items
        The folder with chains.csv, changes.csv and series.csv.
    groups
        The folder with groups.csv, members.csv and changes.csv.
    curated_corrected
        The folder with labels_en.csv for the sections.
    curated_items
        The folder with labels_en.csv for the chains.
    curated_groups
        The folder with labels_en.csv for the groups.
    curated_data
        The folder with code_corrections.csv.
    data
        The folder with pdfs.csv and code_usage.csv.
    out
        Where the tables go.
    """
    tables = build(
        corrected,
        items,
        groups,
        curated_corrected / "labels_en.csv",
        curated_items / "labels_en.csv",
        curated_groups / "labels_en.csv",
        data,
        curated_data / "code_corrections.csv",
    )
    for name, (header, rows) in tables.items():
        csv_io.write(out / name, header, rows)
    print(
        ", ".join(f"{len(rows)} {name[:-4].replace('_', ' ')}" for name, (_, rows) in tables.items())
        + f" -> {out.as_posix()}/"
    )
