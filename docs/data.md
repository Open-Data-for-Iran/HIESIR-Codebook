# Data files

Where everything lives, what each column means, and how to load the files without losing the leading zeros.

!!! tip "Just looking up an item?"
    The [explorer](explorer.md) answers most questions without opening a CSV.

## Quick start

```python
import pandas as pd

TEXT = {"code": str, "sub": str, "expenditure_code": str}
q = pd.read_csv("output/2_corrected/questionnaire_1403.csv", dtype=TEXT)
items = q[q.kind == "item"]

chains = pd.read_csv("output/3_items/chains.csv", dtype={"expenditure_code": str})
changes = pd.read_csv("output/3_items/changes.csv")  # same, recoded, merged, split, regrouped
series = pd.read_csv("output/3_items/series.csv", dtype={"codes": str})  # chains that continuing changes join

# or the results: one table per thing, with English labels
crosswalk = pd.read_csv("output/5_results/items.csv", dtype={"expenditure_code": str, "code": str, "sub": str})

# join with the raw data, which stores codes as numbers
items = items.assign(Commodity_Code=items.expenditure_code.astype(int))
```

The same files can be downloaded from this site:
[2_corrected/questionnaire_1403.csv](2_corrected/questionnaire_1403.csv) (any year in place of 1403),
[3_items/chains.csv](3_items/chains.csv), [3_items/changes.csv](3_items/changes.csv), [3_items/series.csv](3_items/series.csv),
[4_groups/groups.csv](4_groups/groups.csv), [4_groups/members.csv](4_groups/members.csv) and [4_groups/changes.csv](4_groups/changes.csv); the results: [5_results/years.csv](5_results/years.csv), [5_results/pdfs.csv](5_results/pdfs.csv), [5_results/sections.csv](5_results/sections.csv), [5_results/headers.csv](5_results/headers.csv), [5_results/items.csv](5_results/items.csv), [5_results/chains.csv](5_results/chains.csv), [5_results/series.csv](5_results/series.csv), [5_results/groups.csv](5_results/groups.csv), [5_results/changes.csv](5_results/changes.csv), [5_results/change_chains.csv](5_results/change_chains.csv), [5_results/group_changes.csv](5_results/group_changes.csv), [5_results/code_corrections.csv](5_results/code_corrections.csv) and [5_results/code_usage.csv](5_results/code_usage.csv).

| File | One row per | Details |
|---|---|---|
| `2_corrected/questionnaire_<year>.csv` | section, group header or item of that year | [CSV columns](#csv-columns) |
| `2_corrected/autocorrect/canonical.csv` | label printed in several ways, with the one wording its group gets and why | [Corrections](methods.md#corrections) |
| `2_corrected/autocorrect/words.csv` | word fixed automatically: learned from the groups of labels, folded (ی, ک, hamza), one form of a word an item prints two ways, or found with hazm's word list, with its kind, uses and evidence | [Corrections](methods.md#corrections) |
| `3_items/chains.csv` | item: one code with one label, followed while both stay the same | [Stage 1](methods.md#matching-items-across-years) |
| `3_items/changes.csv` | change between chains: a continuing one (same, recoded, 1 → 1), or a merge, split or regrouping between sets of chains | [Stage 2](methods.md#matching-items-across-years) |
| `3_items/series.csv` | series: the chains that continuing changes join, one good or service followed until a merge, split or regrouping ends it | [Stage 3](methods.md#matching-items-across-years) |
| `3_items/suggested/changes.csv` | change the code found, as it found it, with who decided it and how; rejected and open ones are only here | [Who decides](methods.md#matching-items-across-years) |
| `4_groups/groups.csv` | group header: one printed code, followed while it is printed | [Groups](methods.md#groups-across-years) |
| `4_groups/members.csv` | item and year: its group at levels 2, 3 and 4 | [Groups](methods.md#groups-across-years) |
| `4_groups/changes.csv` | pair of groups that items moved between: continued, split, merged, regrouped, moved | [Groups](methods.md#groups-across-years) |
| `4_groups/suggested/changes.csv` | group change the code found, as it found it, with who decided it and how | [Groups](methods.md#groups-across-years) |
| `5_results/items.csv` | item and year: its Persian and English label, chain, series and group at levels 2, 3 and 4, and where it is printed: the crosswalk to join with the household data | [Results](#results) |
| `5_results/chains.csv`, `series.csv`, `groups.csv` | chain, series or group, with `label_fa` and `label_en` (a series is labelled by its last chain) | [Results](#results) |
| `5_results/changes.csv`, `group_changes.csv` | change between chains or between groups, as in `3_items/` and `4_groups/`, text columns named `from_label_fa` / `to_label_fa` | [Results](#results) |
| `5_results/change_chains.csv` | chain on one side of a change: `from_chains` / `to_chains` in long form | [Results](#results) |
| `5_results/years.csv` | year from 1363 to 1403: `covered`, `old_code_scheme` (1382), `scan_only` or `no_pdf`, with its PDFs and items | [Results](#results) |
| `5_results/pdfs.csv` | questionnaire PDF: `data/pdfs.csv` with its download `url` | [Results](#results) |
| `5_results/sections.csv`, `headers.csv` | section or group header as printed that year; a section with its `label_en` and `recall_period` (`month`, `12_months`), a header with its `group_id`; `page` and the box are empty where nothing was printed (1383 section 2: page 14 of that PDF is blank, the section is copied from 1384) | [Results](#results) |
| `5_results/code_corrections.csv`, `code_usage.csv` | `curated/data/code_corrections.csv` and `data/code_usage.csv`, the raw data's code as `raw_code`, `occurrence` as `households` | [Results](#results) |

The `changes.csv` files outside `suggested/` are the results: every row in them was
decided, by the code or in `curated/`, and none is rejected. What the code
suggested before any decision is in `suggested/`, with the same ids.

## Results

`output/5_results/` gathers what a user of the codebook needs into one flat
folder, without knowing the stages. Nothing in it is decided anew: it joins
`2_corrected/`, `3_items/` and `4_groups/` with the English labels kept by
hand in `curated/2_corrected/labels_en.csv` (one per section wording),
`curated/3_items/labels_en.csv` (one per chain) and
`curated/4_groups/labels_en.csv` (one per group). Every text column is
`label_fa` or `label_en`.

The English labels take their wording from COICOP's English titles where
those fit the Persian; they are not a COICOP classification. A term with no
proper English name stays in English letters (`Charghad`, `Kalbas`). Each
label file has a `note` with what was checked and a `source` with where.

The build checks that every item has one chain, one series and a group, and
that every chain and group has an English label and no label names one that
is gone.

The same files, without the BOM, are released as a data package: a zip
with a `datapackage.json` that gives every column its type, meaning and
allowed values, and the keys between the files. `uv run hiesir-codebook
bundle` makes it in `dist/bundle/` and checks it against its own schema;
it is tagged `data-v<version>`. A patch version corrects data, a minor one
adds a year, changes, columns or files, and a major one renames or removes
a column.

## Folders

| Folder | Content | In git | Edited by |
|---|---|---|---|
| `data/` | external inputs: the PDFs, the code usage table | the code usage table and `pdfs.csv` (the PDFs are in a GitHub release) | nobody (only replaced) |
| `curated/` | hand-kept decisions: `2_corrected/` (`corrections.csv`: item and header fixes; `spelling.csv`; `words.csv`: words hazm lacks; `header_exceptions.csv`; `labels_en.csv`: English labels of sections), `3_items/` (`changes.csv`; `labels_en.csv`: English labels of chains), `4_groups/` (`changes.csv`; `labels_en.csv`: English labels of groups): the decisions for the `output/` folder of the same name; `data/` (`code_corrections.csv`): wrong codes in the raw data, kept for later | yes | people |
| `output/` | every stage's result: `1_extracted/`, `2_corrected/`, `3_items/`, `4_groups/`, `5_results/` and `metrics.json` (the figures of the build, which these pages quote) | yes | the pipeline only |
| `reports/` | review aids: `change_evidence.csv` (household counts behind each change) and `code_reuse.csv` (codes reused for another item) | no | the pipeline only |

## CSV columns

| Column | Meaning |
|---|---|
| `section` | بخش number |
| `kind` | `section`, `header` (group row) or `item` |
| `level` | 2–4 for group headers, 5 for items |
| `code` | code as printed, normalised: `0111`, `091 A`, `01111, 01112` |
| `sub` | two-digit item sub-code |
| `expenditure_code` | full code of an item: `code` digits followed by `sub` (`0111` + `11` → `011111`); empty for sections and headers |
| `description` | item description, or the full section title for section rows |
| `page` | 1-based PDF page |
| `top`, `bottom`, `left`, `right` | the table row it is printed in on that page, in points (1/72 inch) from the page's top-left corner: between the row's rules and across the table's outer borders (where a row has no rule, the extent of its code line and wrapped description lines); empty for rows not printed in the PDF, such as a section copied from another year. The explorer uses them to highlight the row on the printed form |

"Expenditure code" covers goods and services alike (rent, tuition, insurance,
transfers), following the questionnaire's "شرح هزینه". It is the same code the
raw data calls `Commodity_Code`.

Codes are text and keep their leading zero (`011111`): COICOP divisions 01–09
start with 0, and the zero is part of the code. The raw data stores codes as
numbers (`11111`), so join on `int(expenditure_code)`. In pandas, read with
`dtype={"code": str, "sub": str, "expenditure_code": str}`. Opening a CSV
directly in Excel strips the zeros on screen, so use Data → From Text/CSV and
set those columns to Text.

The files are UTF-8 with a BOM so Excel displays the Persian text correctly,
with LF line endings (enforced by `.gitattributes`) so diffs are clean on every OS.

## Coverage

"Raw-data codes missing" counts codes that occur in that year's raw data but
not in the questionnaire, before → after the corrections.

| Years | Raw-data codes missing | Notes |
|---|---|---|
| 1383 | 7 → 1 | Section 2 page blank in the PDF; the one left, `231`, is not an item code |
| 1384 | 1 → 0 | |
| 1385 | 0 | |
| 1386 | 9 → 0 | Code typos on page 27 and elsewhere |
| 1387–1389 | 0, 5, 1 | The ones left are reported by 1–2 households each |
| 1390–1403 | 0 | 1395, 1396, 1399 and 1402 go through the glyph repair |
| 1363–1381 | n/a | Scanned images only; needs OCR |

During development the extracts were also checked against the earlier
hand-made workbooks: item codes matched, and 96–99% of descriptions matched
for 1390–1403. The remaining differences were manual edits (typo fixes,
Persian digits, later wording), not extraction errors.

## Input files

The PDFs are kept out of git (see `.gitignore`; the `questionnaires` release holds them,
and `data/pdfs.csv` lists them with their size and SHA-256; `hiesir-codebook pdfs download`
fetches and checks them); the code usage table is in git. All are expected in `data/`:

```
data/
  pdf/questionnaire_<year>[_urban|_rural].pdf
  pdfs.csv
  code_usage.csv
```

The code usage table is in long format, one row per year and code (1363–1403):
`year`, `expenditure_code` (a number, as the raw data stores it: `11111`),
`occurrence` (households that reported it) and `expenditure_share` (its percent
of that year's expenditure; may be empty).

Use `--data <folder>` to point the CLI somewhere else.
