# HBSIR Questionnaire

Extracts the expenditure code list (sections, group headers, items) from the
HBSIR questionnaire PDFs.

The extracts live in `extracted/questionnaire_<year>.csv`, one file per year,
regenerated from the PDFs. Keeping them under version control shows exactly
what changes when the extractor changes or a PDF is replaced.

```bash
uv run hbsir-questionnaire all                  # write every extracted/questionnaire_<year>.csv
uv run hbsir-questionnaire 1382 1403            # or just some years
uv run python -m hbsir_questionnaire.validate   # check extracted codes against the raw data
uv run python -m hbsir_questionnaire.validate 1400 -v   # list the codes that differ
```

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

## How it works

- `pdf_text.py` rebuilds right-to-left text from glyph positions. Glyphs without
  a Unicode mapping (1382) are decoded through their glyph names, and ZWNJs are
  recovered where the font uses contextual glyph forms.
- `glyph_db.py` repairs fonts whose ToUnicode map is wrong (1395, 1396, 1399,
  1402: بخش extracts as لاوش). Each glyph's outline is hashed and looked up in
  `src/hbsir_questionnaire/data/glyph_db.json` (tracked), which is built from the clean PDFs. A font is treated as
  broken when its ToUnicode map disagrees with the database: clean PDFs agree
  100%, broken fonts disagree on 0.8% or more. To rebuild the database:
  `uv run python -m hbsir_questionnaire.build_glyph_db`.
- `parse.py` finds code lines and attaches wrapped description lines to them,
  using the table rules and column borders.
- `validate.py` checks each year's extracted codes against the codes that
  occur in the raw data (`data/commodity_code_occurrence_*.csv`).
- `utils.py` holds the Persian text normalisation helpers, usable on their own:
  `normalize_persian` (letters, digits, tatweel, spacing), `to_ascii_digits` /
  `to_persian_digits`, `canonical` (presentation forms → base letters),
  `normalize_visual` (fix-up for right-to-left glyph text) and `loose_key`
  (comparison that ignores spacing, ZWNJ and punctuation).

## Coverage

"Raw-data codes missing" counts codes that occur in that year's raw data but
were not found in the extract.

| Years | Raw-data codes missing | Notes |
|---|---|---|
| 1382 | 0 | Old 3+2 digit code scheme |
| 1383–1385 | 7, 3, 1 | |
| 1386–1389 | 9, 0, 5, 1 | Not reviewed in detail |
| 1390–1394 | 0–1 | |
| 1395–1400, 1402, 1403 | 0 | 1395, 1396, 1399 and 1402 go through the glyph repair |
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

## Development

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv run pytest                 # unit tests + regression against extracted/ (needs data/)
uv run pytest -m "not slow"   # unit tests only
uv run ruff check . && uv run ruff format --check .
```

The regression tests re-extract every year and compare byte-for-byte with
`extracted/`. When an extractor change is intended, regenerate with
`uv run hbsir-questionnaire all` and review the CSV diff before committing.

## License

MIT, see [LICENSE](LICENSE).
