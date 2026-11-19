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

chains = pd.read_csv("output/3_matched/chains.csv", dtype={"expenditure_code": str})
links = pd.read_csv("output/3_matched/links.csv")
relations = pd.read_csv("output/3_matched/relations.csv")
relations = relations[relations.verified != "rejected"]

# join with the raw data, which stores codes as numbers
items = items.assign(Commodity_Code=items.expenditure_code.astype(int))
```

The same files can be downloaded from this site:
[2_corrected/questionnaire_1403.csv](2_corrected/questionnaire_1403.csv) (any year in place of 1403),
[3_matched/chains.csv](3_matched/chains.csv), [3_matched/links.csv](3_matched/links.csv) and [3_matched/relations.csv](3_matched/relations.csv).

| File | One row per | Details |
|---|---|---|
| `2_corrected/questionnaire_<year>.csv` | section, group header or item of that year | [CSV columns](#csv-columns) |
| `3_matched/chains.csv` | item: one code with one label, followed while both stay the same | [Stage 1](methods.md#matching-items-across-years) |
| `3_matched/links.csv` | 1 → 1 link that continues an item: same, recoded | [Stage 2](methods.md#matching-items-across-years) |
| `3_matched/relations.csv` | relation between sets of items: merged, split, regrouped | [Stage 2](methods.md#matching-items-across-years) |
| `3_matched/series.csv`, `codes.csv`, `history.csv`, `review.csv` | the older one-pass matcher's series | [Methods](methods.md#matching-items-across-years) |

## Folders

| Folder | Content | In git | Edited by |
|---|---|---|---|
| `data/` | external inputs: the PDFs, the household occurrence tables | no | nobody (only replaced) |
| `curated/` | hand-kept decisions: `source.csv` (item fixes), `labels.csv` (spelling fixes), `links.csv` and `relations.csv` (matching decisions) | yes | people |
| `output/` | every stage's result: `1_extracted/`, `2_corrected/`, `3_matched/`, and the `explorer/` page | yes | the pipeline only |
| `reports/` | review aids such as `hazm_suggestions.csv` | no | the pipeline only |

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

The inputs are kept out of git (see `.gitignore`) and are expected in `data/`:

```
data/
  pdf/Questionnaire <year>.pdf
  commodity_code_occurrence_1363-1382.csv
  commodity_code_occurrence_1383-1403.csv
```

Use `--data <folder>` to point the CLI somewhere else.
