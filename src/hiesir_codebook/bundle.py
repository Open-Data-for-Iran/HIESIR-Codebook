"""The data release: ``output/5_results/`` as a Frictionless data package.

    uv run hiesir-codebook bundle

writes ``dist/bundle/hies-expenditure-codebook-v<version>/`` and its zip:

- every CSV of ``output/5_results/``, byte for byte but without the BOM
  (the bundle is for programs; the Excel release is for people);
- ``datapackage.json``: the version, the commit it was built from, the
  licence, how to cite it, and a schema for every file: each column's type,
  what it means, the values it may take, the primary key and the foreign
  keys between the files;
- ``README.md``: a short guide.

Then it checks the bundle against its own schema (:func:`check`).  Nothing
is tracked: ``dist/`` is ignored, the release is made whenever one is due.

The schema is a contract.  The version says what changed:

- patch: corrections to the data;
- minor: a new year, new changes, new columns or files;
- major: a column renamed or removed, or its meaning changed.

The release is tagged ``data-v<version>``, apart from the questionnaire
PDFs (``questionnaires``) and the Excel workbooks.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

from . import RESULTS, csv_io
from .excel import REPOSITORY, SITE

DATA_VERSION = "0.2.0"
NAME = "hies-expenditure-codebook"
TAG = f"data-v{DATA_VERSION}"
BUNDLE = Path("dist") / "bundle"

CODE = r"[0-9]{5,6}"
CHAIN = rf"C-{CODE}-[0-9]{{4}}"
SERIES = rf"I-{CODE}-[0-9]{{4}}"
GROUP = r"G-[0-9A-Z+]+-[0-9]{4}(-[0-9]+)?"


def _list(one: str) -> str:
    return rf"^{one}( {one})*$"


# column -> (type, what it means, constraints); a file may mean something else
# by a column (OVERRIDES)
FIELDS: dict[str, tuple[str, str, dict]] = {
    "year": ("integer", "Survey year, in the Iranian (Solar Hijri) calendar.", {"required": True}),
    "expenditure_code": (
        "string",
        "The item's code as the questionnaire prints it, with its leading zero (011111). "
        "The raw data's Commodity_Code stores it as a number: join on int(expenditure_code).",
        {"pattern": f"^{CODE}$"},
    ),
    "raw_code": (
        "integer",
        "The code as the raw data's Commodity_Code stores it: a number, without the leading zero.",
        {"required": True},
    ),
    "section": ("integer", "The questionnaire section, 1 to 14.", {"minimum": 1, "maximum": 14}),
    "code": ("string", "The code printed in the code column of the questionnaire.", {}),
    "sub": ("string", "The sub-code printed next to the code (the last two digits of the item's code).", {}),
    "level": ("integer", "Group level: 2 (division), 3 (group) or 4 (class).", {"enum": [2, 3, 4]}),
    "label_fa": ("string", "The label in Persian, as printed (corrected).", {}),
    "label_en": (
        "string",
        "An English label, kept by hand. Worded after COICOP's English titles where they fit; "
        "a term with no proper English name is written in English letters (Charghad). "
        "Not a COICOP classification.",
        {},
    ),
    "chain_id": (
        "string",
        "A chain: one code with one label, followed across the years while both stay the same. "
        "C-<code>-<first year>.",
        {"pattern": f"^{CHAIN}$"},
    ),
    "series_id": (
        "string",
        "A series: the chains that continuing changes (same, recoded) join, one good or service "
        "followed until a merge, split or regrouping. I-<code>-<first year>.",
        {"pattern": f"^{SERIES}$"},
    ),
    "group_id": (
        "string",
        "A group header followed across the years. G-<code>-<first year>.",
        {"pattern": f"^{GROUP}$"},
    ),
    "group_l2": ("string", "The item's group at level 2 that year.", {"pattern": f"^{GROUP}$"}),
    "group_l3": ("string", "The item's group at level 3 that year.", {"pattern": f"^{GROUP}$"}),
    "group_l4": (
        "string",
        "The item's group at level 4 that year; empty where the questionnaire prints no level 4 header.",
        {"pattern": f"^{GROUP}$"},
    ),
    "parent_id": ("string", "The group one level up, in the group's last year.", {"pattern": f"^{GROUP}$"}),
    "page": (
        "integer",
        "The page of the PDF it is printed on; empty with top, bottom, left and right where it is "
        "not printed: a section copied from another year (1383 section 2, page 14 of that PDF "
        "is blank, copied from 1384; see the correction in curated/2_corrected/corrections.csv).",
        {},
    ),
    "top": ("number", "Where it is printed on the page, in PDF points from the top.", {}),
    "bottom": ("number", "Where it is printed on the page, in PDF points from the top.", {}),
    "left": ("number", "Where it is printed on the page, in PDF points from the left.", {}),
    "right": ("number", "Where it is printed on the page, in PDF points from the left.", {}),
    "first_year": ("integer", "The first year it is printed.", {"required": True}),
    "last_year": ("integer", "The last year it is printed.", {"required": True}),
    "missing_years": (
        "string",
        "Years between the first and the last in which it is not printed, space-separated.",
        {"pattern": _list("[0-9]{4}")},
    ),
    "codes": (
        "string",
        "The codes of the series' chains, space-separated, in order.",
        {"pattern": _list(CODE)},
    ),
    "chains": ("string", "The series' chains, space-separated, in order.", {"pattern": _list(CHAIN)}),
    "starts": (
        "string",
        "The change the series starts with (a merge, split or regrouping); empty: none.",
        {},
    ),
    "ends": ("string", "The change the series ends with (a merge, split or regrouping); empty: none.", {}),
    "items": ("integer", "Items under the group, at any depth, in its last year.", {}),
    "change_id": ("string", "A change between chains. L<number>.", {"pattern": "^L[0-9]{4}$"}),
    "type": (
        "string",
        "same, recoded (1 to 1, the item goes on), merged, split or regrouped (between sets of chains).",
        {"enum": ["same", "recoded", "merged", "split", "regrouped"], "required": True},
    ),
    "detail": (
        "string",
        "How the label changed in a continuing change: minor, label_broadened, label_narrowed, "
        "label_reworded; empty: not at all.",
        {"enum": ["minor", "label_broadened", "label_narrowed", "label_reworded"]},
    ),
    "from_chains": ("string", "The chains before the change, space-separated.", {"pattern": _list(CHAIN)}),
    "to_chains": ("string", "The chains after the change, space-separated.", {"pattern": _list(CHAIN)}),
    "score": ("number", "How alike the labels are, 0 to 1, for a 1 to 1 change; empty otherwise.", {}),
    "decided_by": (
        "string",
        "code: found and sure without a decision; curated: decided by a row in curated/ (verified says how).",
        {"enum": ["code", "curated"], "required": True},
    ),
    "verified": (
        "string",
        "How curated/ decided it: confirmed, amended or added; empty: by the code alone.",
        {"enum": ["confirmed", "amended", "added"]},
    ),
    "note": ("string", "Why, in a sentence.", {}),
    "from_label_fa": ("string", "The Persian label(s) before the change.", {}),
    "to_label_fa": ("string", "The Persian label(s) after the change.", {}),
    "side": ("string", "from: before the change; to: after it.", {"enum": ["from", "to"], "required": True}),
    "from_group": ("string", "The group the items moved from.", {"pattern": f"^{GROUP}$"}),
    "to_group": ("string", "The group the items moved to.", {"pattern": f"^{GROUP}$"}),
    "from_items": ("integer", "Items under the group before, that year.", {}),
    "to_items": ("integer", "Items under the group after, that year.", {}),
    "item_chains": ("string", "The item chains that moved, space-separated.", {"pattern": _list(CHAIN)}),
    "status": (
        "string",
        "covered: in the codebook; old_code_scheme: a text PDF whose 3+2 digit codes are not matched; "
        "scan_only: the PDF is a scan; no_pdf: no questionnaire PDF in the collection.",
        {"enum": ["covered", "old_code_scheme", "scan_only", "no_pdf"], "required": True},
    ),
    "pdfs": ("integer", "Questionnaire PDFs of the year (two where urban and rural were apart).", {}),
    "area": ("string", "urban or rural; empty: one questionnaire for both.", {"enum": ["urban", "rural"]}),
    "name": ("string", "The PDF's file name.", {"required": True}),
    "kind": (
        "string",
        "extracted: in the codebook; text: has a text layer, left out (1382); scan: images only.",
        {"enum": ["extracted", "text", "scan"]},
    ),
    "bytes": ("integer", "The PDF's size.", {}),
    "sha256": ("string", "The PDF's SHA-256.", {"pattern": "^[0-9a-f]{64}$"}),
    "url": ("string", "Where to download the PDF.", {}),
    "recall_period": (
        "string",
        "The period the section asks about: month (the past month) or 12_months (the past 12 months); "
        "empty where the label names none.",
        {"enum": ["month", "12_months"]},
    ),
    "reason": ("string", "Why the code is wrong, and the evidence.", {}),
    "households": ("integer", "Households that reported the code that year.", {}),
    "expenditure_share": ("number", "The code's percent of that year's expenditure; empty: unknown.", {}),
}
OVERRIDES: dict[tuple[str, str], tuple[str, str, dict]] = {
    ("years.csv", "items"): ("integer", "Items in the codebook that year; empty: not covered.", {}),
    ("years.csv", "note"): ("string", "What the status means.", {}),
    ("group_changes.csv", "change_id"): (
        "string",
        "A change between groups. GL<number>.",
        {"pattern": "^GL[0-9]{4}$"},
    ),
    ("group_changes.csv", "type"): (
        "string",
        "continued, split, merged, regrouped, or moved (items left for a group that existed already).",
        {"enum": ["continued", "split", "merged", "regrouped", "moved"], "required": True},
    ),
    ("group_changes.csv", "items"): ("integer", "Item chains that moved.", {}),
    ("group_changes.csv", "from_label_fa"): ("string", "The Persian label of the group before.", {}),
    ("group_changes.csv", "to_label_fa"): ("string", "The Persian label of the group after.", {}),
    ("change_chains.csv", "change_id"): FIELDS["change_id"],
    ("headers.csv", "code"): (
        "string",
        "The group code as printed: digits, maybe several ('01121, 01122'), maybe with an M or A "
        "suffix (the recall period's part of a group split between both).",
        {"required": True},
    ),
    ("code_corrections.csv", "expenditure_code"): (
        "string",
        "The code the raw code stands for; empty: it stands for no item (drop it).",
        {"pattern": f"^{CODE}$"},
    ),
}

# file -> (what one row is, primary key, foreign keys: (columns, file, columns))
RESOURCES: dict[str, tuple[str, list[str], list[tuple[list[str], str, list[str]]]]] = {
    "years.csv": ("A survey year, and whether the codebook covers it.", ["year"], []),
    "pdfs.csv": ("A questionnaire PDF.", ["name"], [(["year"], "years", ["year"])]),
    "sections.csv": (
        "A section, as printed that year.",
        ["year", "section"],
        [(["year"], "years", ["year"])],
    ),
    "headers.csv": (
        "A group header, as printed that year, with its group across years.",
        ["year", "section", "level", "code"],
        [(["group_id"], "groups", ["group_id"]), (["year"], "years", ["year"])],
    ),
    "items.csv": (
        "An item of a year: the crosswalk from year and code to chain, series and groups.",
        ["year", "expenditure_code"],
        [
            (["chain_id"], "chains", ["chain_id"]),
            (["series_id"], "series", ["series_id"]),
            (["group_l2"], "groups", ["group_id"]),
            (["group_l3"], "groups", ["group_id"]),
            (["group_l4"], "groups", ["group_id"]),
            (["year"], "years", ["year"]),
        ],
    ),
    "chains.csv": (
        "A chain: one code with one label, while both stay the same.",
        ["chain_id"],
        [(["series_id"], "series", ["series_id"])],
    ),
    "series.csv": ("A series: chains joined by continuing changes.", ["series_id"], []),
    "groups.csv": (
        "A group header across years.",
        ["group_id"],
        [(["parent_id"], "groups", ["group_id"])],
    ),
    "changes.csv": ("A change between chains.", ["change_id"], []),
    "change_chains.csv": (
        "A chain on one side of a change: from_chains and to_chains of changes.csv in long form.",
        ["change_id", "side", "chain_id"],
        [(["change_id"], "changes", ["change_id"]), (["chain_id"], "chains", ["chain_id"])],
    ),
    "group_changes.csv": (
        "A pair of groups that items moved between.",
        ["change_id"],
        [(["from_group"], "groups", ["group_id"]), (["to_group"], "groups", ["group_id"])],
    ),
    "code_corrections.csv": (
        "A wrong code in the raw data, and the code it stands for.",
        ["year", "raw_code"],
        [(["year"], "years", ["year"])],
    ),
    "code_usage.csv": (
        "A code of the raw data in a year: how many households reported it, and its share of expenditure.",
        ["year", "raw_code"],
        [(["year"], "years", ["year"])],
    ),
}


def field(file: str, column: str) -> dict:
    kind, description, constraints = OVERRIDES.get((file, column)) or FIELDS[column]
    out = {"name": column, "type": kind, "description": description}
    if constraints:
        out["constraints"] = constraints
    return out


def package(results: Path = RESULTS, commit: str = "", created: str = "") -> dict:
    """The datapackage.json of the CSVs in ``results``."""
    names = sorted(p.name for p in results.glob("*.csv"))
    if set(names) != set(RESOURCES):
        raise ValueError(f"the files are not those the schema knows: {sorted(set(names) ^ set(RESOURCES))}")
    resources = []
    for file, (title, key, foreign) in RESOURCES.items():
        with open(results / file, encoding=csv_io.ENCODING) as f:
            header = f.readline().rstrip("\n").split(",")
        schema: dict = {"fields": [field(file, c) for c in header], "missingValues": [""]}
        if key:
            schema["primaryKey"] = key
        if foreign:
            schema["foreignKeys"] = [
                {"fields": cols, "reference": {"resource": "" if ref == file[:-4] else ref, "fields": to}}
                for cols, ref, to in foreign
            ]
        resources.append(
            {
                "name": file[:-4],
                "path": file,
                "profile": "tabular-data-resource",
                "description": title,
                "format": "csv",
                "mediatype": "text/csv",
                "encoding": "utf-8",
                "dialect": {"delimiter": ",", "lineTerminator": "\n", "header": True},
                "schema": schema,
            }
        )
    return {
        "profile": "tabular-data-package",
        "name": NAME,
        "title": "HIES expenditure codebook",
        "description": (
            "The expenditure items of the questionnaires of the Household Income and Expenditure "
            "Survey of Iran (HIES), 1383-1403: extracted from the PDF forms, corrected, and matched "
            "across years, with English labels. Join items.csv with the household data on year and "
            "int(expenditure_code) = Commodity_Code."
        ),
        "version": DATA_VERSION,
        "homepage": SITE,
        "sources": [
            {
                "title": "The HIES questionnaires (Statistical Centre of Iran)",
                "path": f"{REPOSITORY}/releases/tag/questionnaires",
            }
        ],
        "licenses": [{"name": "MIT", "path": f"{REPOSITORY}/blob/main/LICENSE", "title": "MIT License"}],
        "contributors": [{"title": "Mohammad Amin Alavian", "role": "author"}],
        "citation": f"Alavian, M. A. HIES expenditure codebook, version {DATA_VERSION}. {REPOSITORY}",
        "repository": REPOSITORY,
        "commit": commit,
        "created": created,
        "conventions": {
            "encoding": "UTF-8 without a BOM",
            "missing": "an empty field is a missing value",
            "lists": "space-separated ids",
            "codes": "codes and ids are strings: expenditure_code keeps its leading zero; raw_code is "
            "the number the raw data stores",
            "versioning": "patch: corrections to the data; minor: a new year, new changes, new columns "
            "or files; major: a column renamed or removed, or its meaning changed",
        },
        "resources": resources,
    }


README = """# HIES expenditure codebook, version {version}

The expenditure items of the questionnaires of Iran's Household Income and
Expenditure Survey, 1383-1403: extracted from the PDF forms, corrected and
matched across years, with English labels.

Start with `items.csv`: one row per year and expenditure code, with its
chain, series and groups. Join it with the household data on `year` and
`int(expenditure_code)` = `Commodity_Code`.

```python
import pandas as pd
items = pd.read_csv("items.csv", dtype={{"expenditure_code": str, "code": str, "sub": str}})
```

| File | One row per |
|---|---|
{files}

`datapackage.json` describes every column, its type and the keys between
the files (a Frictionless data package). UTF-8 without a BOM; an empty field
is missing; lists are space-separated ids.

- Documentation and explorer: {site}
- Source and issues: {repository} (built from commit `{commit}`)
- Licence: MIT
"""


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def write(results: Path, out: Path, commit: str, created: str) -> Path:
    """The bundle in ``out/<name>-v<version>/`` and its zip; returns the folder."""
    folder = out / f"{NAME}-v{DATA_VERSION}"
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    pkg = package(results, commit, created)
    for r in pkg["resources"]:
        data = (results / r["path"]).read_bytes()
        (folder / r["path"]).write_bytes(data.removeprefix(b"\xef\xbb\xbf"))
    (folder / "datapackage.json").write_text(
        json.dumps(pkg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    files = "\n".join(f"| `{r['path']}` | {r['description']} |" for r in pkg["resources"])
    (folder / "README.md").write_text(
        README.format(
            version=DATA_VERSION, files=files, site=SITE, repository=REPOSITORY, commit=commit or "?"
        ),
        encoding="utf-8",
        newline="\n",
    )
    shutil.make_archive(str(folder), "zip", out, folder.name)
    return folder


def _value(kind: str, text: str) -> object:
    if kind == "integer":
        return int(text)
    if kind == "number":
        return float(text)
    return text


def check(folder: Path) -> None:
    """Every file of the bundle against datapackage.json: no BOM, the columns,
    each value's type and constraints, the primary keys and the foreign keys."""
    pkg = json.loads((folder / "datapackage.json").read_text(encoding="utf-8"))
    problems: list[str] = []
    keys: dict[str, dict[tuple[str, ...], set[tuple]]] = {}
    tables: dict[str, list[dict[str, str]]] = {}
    for r in pkg["resources"]:
        raw = (folder / r["path"]).read_bytes()
        if raw.startswith(b"\xef\xbb\xbf"):
            problems.append(f"{r['path']}: has a BOM")
        rows = csv_io.read(folder / r["path"])
        tables[r["name"]] = rows
        fields = r["schema"]["fields"]
        header = raw.split(b"\n", 1)[0].decode("utf-8-sig").split(",")
        if header != [f["name"] for f in fields]:
            problems.append(f"{r['path']}: columns {header} are not the schema's")
        for f in fields:
            c, kind, rules = f["name"], f["type"], f.get("constraints", {})
            pattern = re.compile(rules["pattern"]) if "pattern" in rules else None
            for i, row in enumerate(rows, start=2):
                text = row[c]
                if text == "":
                    if rules.get("required"):
                        problems.append(f"{r['path']}:{i} {c} is empty")
                    continue
                try:
                    v = _value(kind, text)
                except ValueError:
                    problems.append(f"{r['path']}:{i} {c}={text!r} is not {kind}")
                    continue
                if pattern and not pattern.match(text):
                    problems.append(f"{r['path']}:{i} {c}={text!r} does not match {rules['pattern']}")
                if "enum" in rules and v not in rules["enum"]:
                    problems.append(f"{r['path']}:{i} {c}={text!r} is not one of {rules['enum']}")
                if ("minimum" in rules and v < rules["minimum"]) or (
                    "maximum" in rules and v > rules["maximum"]
                ):
                    problems.append(f"{r['path']}:{i} {c}={text!r} out of range")
        pk = r["schema"].get("primaryKey")
        if pk:
            seen = [tuple(row[c] for c in pk) for row in rows]
            if len(seen) != len(set(seen)):
                problems.append(f"{r['path']}: {len(seen) - len(set(seen))} rows repeat the key {pk}")
    for r in pkg["resources"]:
        for fk in r["schema"].get("foreignKeys", []):
            ref = fk["reference"]["resource"] or r["name"]
            to = tuple(fk["reference"]["fields"])
            have = keys.setdefault(ref, {}).setdefault(to, {tuple(x[c] for c in to) for x in tables[ref]})
            for i, row in enumerate(tables[r["name"]], start=2):
                v = tuple(row[c] for c in fk["fields"])
                if all(v) and v not in have:
                    problems.append(f"{r['path']}:{i} {fk['fields']}={v} is not in {ref}")
                    break
    if problems:
        raise ValueError(f"{folder.as_posix()}: {len(problems)} problems:\n" + "\n".join(problems[:30]))


def main(*, results: Path = RESULTS, out: Path = BUNDLE) -> None:
    """The data release: output/5_results/ as a data package -> dist/bundle/.

    Parameters
    ----------
    results
        The folder with the results CSVs.
    out
        Where the bundle and its zip go.
    """
    commit = _git("rev-parse", "HEAD")
    if _git("status", "--porcelain", "--", results.as_posix()):
        print(f"warning: {results.as_posix()} has changes that are not committed")
        commit += "-dirty"
    folder = write(results, out, commit, _git("log", "-1", "--format=%cI"))
    check(folder)
    print(
        f"{len(RESOURCES)} files + datapackage.json + README.md -> {folder.as_posix()}/ and {folder.name}.zip"
    )
    print(f"to release: gh release create {TAG} {folder.as_posix()}.zip --title 'Data {DATA_VERSION}'")
