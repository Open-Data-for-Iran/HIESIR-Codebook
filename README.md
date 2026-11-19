# HBSIR Questionnaire

Extracts the expenditure code list (sections, group headers, items) from the
HBSIR questionnaire PDFs.

The pipeline has three stages:

```
data/pdf ──extract──▶ 1_extracted ──correct──▶ 2_corrected ──chains──▶ 3_matched
                      as printed       ▲        as intended             chains.csv
                                   curated/
```

The repository separates what people write from what the pipeline writes:

| Folder | Content | In git | Edited by |
|---|---|---|---|
| `data/` | external inputs: the PDFs, the household occurrence tables | no | nobody (only replaced) |
| `curated/` | hand-kept decisions: `source.csv` (item fixes), `labels.csv` (spelling fixes) | yes | people |
| `output/` | every stage's result: `1_extracted/`, `2_corrected/`, `3_matched/` | yes | the pipeline only |
| `reports/` | review aids such as `hazm_suggestions.csv` | no | the pipeline only |

```bash
uv run hbsir-questionnaire build                 # regenerate every stage of output/
uv run hbsir-questionnaire build --no-extract    # keep 1_extracted/ (no PDFs needed)
uv run hbsir-questionnaire all                   # just extract: PDFs -> output/1_extracted/
uv run hbsir-questionnaire 1382 1403             # or just some years
uv run python -m hbsir_questionnaire.correct --check   # correct and check against the raw data
uv run python -m hbsir_questionnaire.validate    # check extracted codes against the raw data
```

`output/1_extracted/` reproduces each PDF exactly, typos included, so it
shows what changes when the extractor changes or a PDF is replaced. Every
deviation from the print is a row in `curated/`, applied to produce
`output/2_corrected/`, which has the same columns. `output/` is tracked so
that each change shows up as a diff, and the tests fail when a stage is out
of date; GitHub folds these files in diffs (`.gitattributes`).

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

## Corrections

`curated/source.csv` lists the errors in the questionnaires themselves,
one row per fix, each with its evidence:

| Column | Meaning |
|---|---|
| `year` | questionnaire year |
| `action` | `recode` (set an item's expenditure code), `retext` (set its description), `delete` (remove an item, with any group header left empty), or `add_section` (copy a section missing from the PDF from another year) |
| `expenditure_code`, `description` | the item as printed; the description tells two rows apart when a code is printed twice |
| `value` | the corrected code or text (for `add_section`: the source year, with the section number in `description`) |
| `reason` | evidence: neighbouring years, the raw data |

The first corrections fix the 1386 code typos (the imputed-rent items printed
under 0412 instead of 0421/0422, 0144 for 0411, 0341 for 0431, 0736 for 0735),
1384's 102216 for 103116, two 1386 descriptions copied from the wrong row, a
cell label read into a 1387 description, and section 2 (tobacco), whose page
is blank in the 1383 PDF (copied from 1384 without 023111, which no
household reports in 1383).

After the listed fixes every description is brought to one punctuation
style (`utils.tidy_punctuation`), about 2,500 rows in all:

- "،", "؛", ":", "؟", "!" attach to the word before them and are followed by
  one space: `آرد ، رشته ،غلات` → `آرد، رشته، غلات`;
- a Latin comma between words becomes "،" (`1,000` stays);
- a repeated mark is written once: `دیس،،` → `دیس،`;
- the conjunction و after a ZWNJ becomes its own word: `وسایل‌و لوازم` → `وسایل و لوازم`;
- an opening bracket has one space before it and none after, a closing one
  none before and one after: `نان ماشینی( لواش )سنگک` → `نان ماشینی (لواش) سنگک`;
- two or more dots, spaced or not, become `...` with a space before it
  (except after an opening bracket) and before a following word:
  `و. . .` → `و ...`, `و...وسایر` → `و ... وسایر`;
- a Persian word and a number get a space between them: `در12ماه` → `در 12 ماه`,
  `پژو405` → `پژو 405` (Latin `MP3` stays);
- a slash between words gets a space on each side: `دبیرستان/ متوسطه` →
  `دبیرستان / متوسطه` (`1/2` stays).

Then `curated/labels.csv` fixes spellings that recur across rows and
years, applied to every description in file order:

| Column | Meaning |
|---|---|
| `find` | the wrong form (may be several words), as it reads after the punctuation rules |
| `replace` | the right form |
| `match` | `word`: whole words only (`بجز` does not touch `بجزروانی`); `text`: anywhere in the label |
| `years` | empty for all years, or years and ranges: `1386`, `1383-1385 1390` |
| `reason` | why |

Its 935 rows change about 7,600 descriptions:

- typos (`دیبرستان` → `دبیرستان`, `رایو` → `رادیو`, `کارت کدملی` → `کارت ملی`),
  one spelling per word (`بجز` → `به جز`, `جابجایی` → `جابه‌جایی`, `پینگ‌پنگ`,
  ی preferred over ئ where both are in use: `ویدیو`, `آینه`, `تزیینی`);
- a و glued to the next word (`وپلاستیکی` → `و پلاستیکی`), words glued
  together or joined by a stray ZWNJ (`لباسزیر` → `لباس زیر`,
  `پزشک‌متخصص` → `پزشک متخصص`), following how the questionnaires
  themselves usually write the pair;
- ZWNJs that standard spelling requires: plural `ها`/`های`, `ه` + `ای`, `می`;
- compounds written with a ZWNJ where the questionnaires write them joined
  (`ثبت‌نام`, `سیب‌زمینی`, `پاک‌کن`); compounds they always write spaced stay
  spaced (`سی دی`, `پرداخت شده`). `--check` lists how many descriptions each row
changed, and the run warns about rows that match nothing.

**hazm as an advisor.** [hazm](https://github.com/roshan-research/hazm) is
not a dependency: it only suggests rows for `labels.csv`.

```bash
uv run --with hazm python scripts/suggest_labels.py   # -> reports/hazm_suggestions.csv
```

The script runs hazm's normalizer (affix spacing, ZWNJ, diacritics; no
Persian digits, no punctuation restyling) over every corrected label and
lists each word-level change with how many labels it affects, sorted into
`plural` (ها/های attached with a ZWNJ, the standard spelling), `compound`
(two words joined with a ZWNJ, e.g. `پرداخت‌شده`, optional), and `other`.
Nothing is applied: accepted rows are copied into `labels.csv` with a reason.

`--check` tests both against the household occurrence table:

- each correction: a recoded item's new code must be reported by households
  that year, a deleted item's code must not be, and every item copied into a
  year must be reported in it;
- each corrected questionnaire: a code that households report but the
  questionnaire lacks, or a code printed twice, points to a typo or an
  extraction miss.

All corrections are backed by the data, and every year from 1383 to 1403
passes.

## Matching items across years

Matching is built in stages, each a separate step with its own output in
`output/3_matched/`.

```bash
uv run python -m hbsir_questionnaire.chains      # stage 1: output/2_corrected/ -> output/3_matched/chains.csv
```

**Stage 1, chains.** A *chain* is one expenditure code with one label,
followed from year to year while both stay the same (labels that differ only
in spacing, ZWNJ, punctuation, hamza or digit style count as the same). Any
other label change, or the code disappearing for more than two
questionnaires, starts a new chain. So every chain has one code and one
text, and every item of every year belongs to exactly one chain.
`chains.csv` has one row per chain: `chain_id` (code and first year, e.g.
`011114-1387`), `section`, `expenditure_code`, `first_year`, `last_year`,
`missing_years`, `text`.

How chains relate to each other (a changed label, a new code, a merge or a
split) is the next stage.

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
- `correct.py` applies `curated/source.csv` and `curated/labels.csv`
  to `output/1_extracted/` and checks the result against the household occurrence
  table. `scripts/suggest_labels.py` uses hazm to suggest rows for
  `labels.csv`.
- `compare.py` compares two descriptions (`same`, `minor`, `broadened`, ...)
  and handles provider qualifiers; shared by the matching stages.
- `chains.py` builds the chains (matching stage 1, see above).
- `validate.py` checks each year's extracted codes against the codes that
  occur in the raw data (`data/commodity_code_occurrence_*.csv`).
- `utils.py` holds the Persian text normalisation helpers, usable on their own:
  `normalize_persian` (letters, digits, tatweel, spacing), `to_ascii_digits` /
  `to_persian_digits`, `canonical` (presentation forms → base letters),
  `normalize_visual` (fix-up for right-to-left glyph text) and `loose_key`
  (comparison that ignores spacing, ZWNJ and punctuation).

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

## Development

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv run pytest                 # unit tests + regression against output/1_extracted/ (needs data/)
uv run pytest -m "not slow"   # unit tests only
uv run ruff check . && uv run ruff format --check .
```

The regression tests re-extract every year and compare byte-for-byte with
`output/1_extracted/`. When an extractor change is intended, regenerate with
`uv run hbsir-questionnaire all` and review the CSV diff before committing.
Fast tests also check that `output/2_corrected/` and `output/3_matched/chains.csv`
are up to date; after changing `curated/` or the code, run
`uv run hbsir-questionnaire build --no-extract` and review the diff.

## License

MIT, see [LICENSE](LICENSE).
