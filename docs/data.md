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
relations = relations[relations.verified != "rejected"]

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
| `2_corrected/spelling_suggestions.csv` | spelling suggestion from hazm's dictionary, with whether the build applies it | [Corrections](methods.md#corrections) |
| `3_items/chains.csv` | item: one code with one label, followed while both stay the same | [Stage 1](methods.md#matching-items-across-years) |
| `3_items/links.csv` | 1 → 1 link that continues an item: same, recoded | [Stage 2](methods.md#matching-items-across-years) |
| `3_items/relations.csv` | relation between sets of items: merged, split, regrouped | [Stage 2](methods.md#matching-items-across-years) |
| `4_groups/groups.csv` | group header: one printed code, followed while it is printed | [Groups](methods.md#groups-across-years) |
| `4_groups/members.csv` | item and year: its group at levels 2, 3 and 4 | [Groups](methods.md#groups-across-years) |
| `4_groups/links.csv` | pair of groups that items moved between: continued, split, merged, regrouped, moved | [Groups](methods.md#groups-across-years) |

## Folders

| Folder | Content | In git | Edited by |
|---|---|---|---|
| `data/` | external inputs: the PDFs, the household occurrence tables | the occurrence tables and `pdfs.csv` (the PDFs are in a GitHub release) | nobody (only replaced) |
| `curated/` | hand-kept decisions: `2_corrected/` (`corrections.csv`: item and header fixes; `spelling.csv`), `3_items/` (`links.csv`, `relations.csv`) and `4_groups/` (`links.csv`): the decisions for the `output/` folder of the same name | yes | people |
| `output/` | every stage's result: `1_extracted/`, `2_corrected/`, `3_items/`, `4_groups/`, the `explorer/` page, and `metrics.json` (the figures of the build, which these pages quote) | yes | the pipeline only |
| `reports/` | review aids: `relation_evidence.csv` (household counts behind each link and relation) and `code_reuse.csv` (codes reused for another item) and `label_check.csv` (words that may still be misspelled) | no | the pipeline only |

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
| 1382 | 0 | Old 3+2 digit code scheme |
| 1383 | 7 → 1 | Section 2 page blank in the PDF; the one left, `231`, is not an item code |
| 1384 | 1 → 0 | |
| 1385 | 0 | |
| 1386 | 9 → 0 | Code typos on page 27 and elsewhere |
| 1387–1389 | 0, 5, 1 | The ones left are reported by 1–2 households each |
| 1390–1400, 1402, 1403 | 0 | 1395, 1396, 1399 and 1402 go through the glyph repair |
| 1401 | n/a | The PDF is a data dictionary, not a questionnaire |
| 1363–1381 | n/a | Scanned images only; needs OCR |

During development the extracts were also checked against the earlier
hand-made workbooks: item codes matched, and 96–99% of descriptions matched
for 1390–1403. The remaining differences were manual edits (typo fixes,
Persian digits, later wording), not extraction errors.

## Input files

The PDFs are kept out of git (see `.gitignore`; the `questionnaires` release holds them,
and `data/pdfs.csv` lists them with their size and SHA-256; `hiesir-codebook pdfs download`
fetches and checks them); the two household occurrence tables are in git. All are expected in `data/`:

```
data/
  pdf/questionnaire_<year>[_urban|_rural].pdf
  pdfs.csv
  commodity_code_occurrence_1363-1382.csv
  commodity_code_occurrence_1383-1403.csv
```

Use `--data <folder>` to point the CLI somewhere else.
