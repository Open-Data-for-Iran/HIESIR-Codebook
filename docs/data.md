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
links = pd.read_csv("output/3_items/links.csv")
relations = pd.read_csv("output/3_items/relations.csv")

# join with the raw data, which stores codes as numbers
items = items.assign(Commodity_Code=items.expenditure_code.astype(int))
```

The same files can be downloaded from this site:
[2_corrected/questionnaire_1403.csv](2_corrected/questionnaire_1403.csv) (any year in place of 1403),
[3_items/chains.csv](3_items/chains.csv), [3_items/links.csv](3_items/links.csv), [3_items/relations.csv](3_items/relations.csv),
[4_groups/groups.csv](4_groups/groups.csv), [4_groups/members.csv](4_groups/members.csv) and [4_groups/links.csv](4_groups/links.csv).

| File | One row per | Details |
|---|---|---|
| `2_corrected/questionnaire_<year>.csv` | section, group header or item of that year | [CSV columns](#csv-columns) |
| `2_corrected/autocorrect/canonical.csv` | label printed in several ways, with the one wording its group gets and why | [Corrections](methods.md#corrections) |
| `2_corrected/autocorrect/words.csv` | word fixed automatically: learned from the groups of labels, folded (ی, ک, hamza), one form of a word an item prints two ways, or found with hazm's word list, with its kind, uses and evidence | [Corrections](methods.md#corrections) |
| `3_items/chains.csv` | item: one code with one label, followed while both stay the same | [Stage 1](methods.md#matching-items-across-years) |
| `3_items/links.csv` | 1 → 1 link that continues an item: same, recoded | [Stage 2](methods.md#matching-items-across-years) |
| `3_items/relations.csv` | relation between sets of items: merged, split, regrouped | [Stage 2](methods.md#matching-items-across-years) |
| `3_items/suggested/links.csv`, `relations.csv` | link or relation the code found, as it found it, with who decided it and how; rejected and open ones are only here | [Who decides](methods.md#matching-items-across-years) |
| `4_groups/groups.csv` | group header: one printed code, followed while it is printed | [Groups](methods.md#groups-across-years) |
| `4_groups/members.csv` | item and year: its group at levels 2, 3 and 4 | [Groups](methods.md#groups-across-years) |
| `4_groups/links.csv` | pair of groups that items moved between: continued, split, merged, regrouped, moved | [Groups](methods.md#groups-across-years) |
| `4_groups/suggested/links.csv` | group link the code found, as it found it, with who decided it and how | [Groups](methods.md#groups-across-years) |

`links.csv` and `relations.csv` are the results: every row in them was
decided, by the code or in `curated/`, and none is rejected. What the code
suggested before any decision is in `suggested/`, with the same ids.

## Folders

| Folder | Content | In git | Edited by |
|---|---|---|---|
| `data/` | external inputs: the PDFs, the code usage table | the code usage table and `pdfs.csv` (the PDFs are in a GitHub release) | nobody (only replaced) |
| `curated/` | hand-kept decisions: `2_corrected/` (`corrections.csv`: item and header fixes; `spelling.csv`; `words.csv`: words hazm lacks; `header_exceptions.csv`), `3_items/` (`links.csv`, `relations.csv`), `4_groups/` (`links.csv`): the decisions for the `output/` folder of the same name; `data/` (`code_corrections.csv`): wrong codes in the raw data, kept for later | yes | people |
| `output/` | every stage's result: `1_extracted/`, `2_corrected/`, `3_items/`, `4_groups/` and `metrics.json` (the figures of the build, which these pages quote) | yes | the pipeline only |
| `reports/` | review aids: `relation_evidence.csv` (household counts behind each link and relation) and `code_reuse.csv` (codes reused for another item) | no | the pipeline only |

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
