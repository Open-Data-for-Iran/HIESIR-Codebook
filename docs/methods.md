# Methods

How the questionnaires are corrected, how items are matched across years, and what the verification found.

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

`output/3_matched/` links each item through the 1383–1403 questionnaires as a
*series*: the same thing asked about year after year, even when its wording
changes slightly, its code changes, or it is missing from a year.

```bash
uv run python -m hiesir_codebook.chains      # stage 1: output/2_corrected/ -> output/3_matched/chains.csv
uv run python -m hiesir_codebook.relations   # stage 2: chains.csv -> output/3_matched/links.csv, relations.csv
uv run python -m hiesir_codebook.match       # all at once (older one-pass matcher): output/2_corrected/ -> output/3_matched/
```

Matching is being rebuilt in stages.

**Stage 1, chains.** A *chain* is one expenditure code with one label,
followed from year to year while both stay the same (labels that differ only
in spacing, ZWNJ, punctuation, hamza or digit style count as the same). Any
other label change, or the code disappearing for more than two
questionnaires, starts a new chain. So every chain has one code and one
text, and every item of every year belongs to exactly one chain.
`chains.csv` has one row per chain: `chain_id` (code and first year, e.g.
`011114-1387`), `section`, `expenditure_code`, `first_year`, `last_year`,
`missing_years`, `text`.

**Stage 2, links and relations.** A relation joins a *set* of earlier
chains to a *set* of later chains; the shape gives the kind:

| `relation` | Shape | Example |
|---|---|---|
| `same` | 1 → 1, same code | برنج چمپا و آشی → برنج آشی |
| `recoded` | 1 → 1, new code | شیرینی خشک: 011837 → 011174 (1386) |
| `merged` | n → 1 | باغبانی + سرایداری + میراب → one item (1386); 21-inch + other TVs → all TVs (1390) |
| `split` | 1 → n | خدمات آمبولانس → G / NG (1395) |
| `regrouped` | n → m | added by hand, e.g. the 1395 dental items |

The two families do different jobs, so they are kept in separate files:

- **Links** (`same`, `recoded`; always 1 → 1) *continue* an item. The
  chains a link joins are one series, and the question to verify is how the
  label's scope changed. `links.csv` has `link_id` (`L0001`…),
  `from_chain`, `to_chain`, `relation`, `detail` (`minor`,
  `label_broadened`, `label_narrowed`, `label_reworded`, or empty when the
  label is the same), `year` (of the change), `score`,
  `needs_verification`, `verified`, `note`, and both texts for reading.
- **Relations** (`merged`, `split`, `regrouped`) *end* series and start
  others. The question is which chains belong on each side.
  `relations.csv` has the same columns, with `relation_id` (`R0001`…) and
  `from_chains` / `to_chains` (chain ids separated by spaces). A chain that
  goes on with its label unchanged can appear on both sides of a merge or
  split.

Both are found in one pass, because a merge is found by extending a link.
They must agree: a chain has at most one link onward and one link into it,
and a chain that a merge, split or regrouping ends (or starts) has no link
onward from it (or into it), unless it appears on both sides. The build
reports any breach, and a test fails on it.

The code finds the 1 → 1 relations within a code, recodings (a chain that
ends and a similar one that starts the next year under a new code), merges
(an ending chain whose label lives on in another; a "سایر X" item that
becomes "X" while the rest of its group vanishes), and splits (a new chain
whose label was part of an older one; an item asked for all providers that
becomes a G / NG pair). This reproduces every merge, split and recoding the
older one-pass matcher found.

When a code's new label is unrelated, the code was reused for another
item. That is no link, so nothing goes into `links.csv`; the 6
pairs (for example 053125: انواع آبگرمکن گازی → کولرگازی) are listed in
`reports/code_reuse.csv` for review.

**Verification.** A 1 → 1 relation is *definite* (`needs_verification`
False) when both labels carry the same content words, so only punctuation,
the conjunction (`،` / `و`), word order, spacing, generic words (`انواع`)
or "etc." markers (`و نظایر آن` / `و ...`) differ: `جگر، دل، قلوه` →
`جگر، دل و قلوه`. Every other relation, and every merge, split or
regrouping, needs a check. Everything is now settled: of 448 links, 162 are
definite and `curated/links.csv` decides the rest (201 confirmed, 73
changed, 8 rejected, 4 added); `curated/relations.csv` decides all 133
merges, splits and regroupings (93 confirmed, 14 rejected, 26 added).

Decisions go in `curated/links.csv` and `curated/relations.csv`, one row per
link or relation, named by its chains:

| Column | Meaning |
|---|---|
| `from_chain`, `to_chain` (links.csv) | one chain id each |
| `from_chains`, `to_chains` (relations.csv) | the chains of each side, ids separated by spaces |
| `decision` | `confirm` (right as found), `reject` (not related this way), `change` (right chains, use `relation`/`detail` instead), or `add` (a relation the code missed, e.g. a regrouping) |
| `relation`, `detail` | for `change` and `add` |
| `note` | why |

The 1 → 1 decisions were checked against the household occurrence table
(`data/commodity_code_occurrence_1383-1403.csv`). The note gives the
households reporting the old code in the year before the change and the new
code in the year of the change, as a ratio relative to the other codes of the
same group, so that survey-wide swings such as 1387 or the 1399 COVID year
cancel out. It also says whether that ratio fits the scope change: a
broadened label should not lose many households, and a narrowed one should
not gain many. Counts under 100 are too few to tell. Where the
label reading was wrong, the row is a `change`. Dropping a qualifier or an
exclusion (`در منزل`, `ساخت داخل`, `به جز بهمن`) broadens an item, and
adding one (`ذرت` → `ذرت شیرین`) narrows it. The comparison counts words, so
it reads these the other way round.

`relations` computes this evidence for every relation on each build and
writes it to `reports/relation_evidence.csv`, with the columns
`before_year`, `before`, `after`, `group`, `ratio` and `verdict` (`fits`,
`does not fit`, `too few`, `no data`). It also prints the verdicts of the
links and relations still to verify. A test checks that the evidence quoted
in the curated notes is still what the code computes.

Merges and splits need a different yardstick, because the table counts
households, not purchases: a household that reported two codes that are
later merged counts once afterwards. So after a merge the count lies between
the largest source and the sum of the sources. Before a split, the source
lies between the largest target and the sum of the targets. The evidence
gives this range (`expected x0.32-1.67`). A sibling code only enters the
group comparison when one chain asks it in both years, so a code reused for
another item does not distort it.

What the verification found:

- **Wrong direction.** Dropping a qualifier broadens an item, adding one
  narrows it, and compare reads both the other way round (77 changes, see
  above).
- **"Outside the home" items (1386).** 062315, 062321, 062323, 062328 and
  062331 ended when their "at home" twins dropped `در منزل`. These are
  merges, not broadenings: vaccination at home (233 households) plus
  outside (3,520) became one item (3,909).
- **Hospital services (1386).** Each hospital type's seven cost items
  (admin, bed, food, emergency, ambulance, drugs, equipment, 063411–063447)
  became one item (063418/28/38/48). The code had sent the drug items to
  special-disease drugs and the admin items to the urine test.
- **The 1395 health redesign.** Outpatient and inpatient care were
  regrouped and split by provider (G/NG): visits, dental care, radiology,
  lab tests, paramedical services, dialysis and chemotherapy, medical
  devices and inpatient bills. The visits at hospitals (0631, 0633) joined
  the outpatient items. These are `add`ed regroupings. Medicines split into
  with and without a prescription, and addiction treatment by place.
- **New items mistaken for splits.** When the old item held its households
  and the new one is not carved out of it, the split is rejected: bread
  dough (011166) is not the yeast of 011934; children's sportswear (031262)
  and other non-durables (056154) are new.
- **Left out of merges.** The tonsil and appendix surgeries (1386),
  hearing-aid repair (1386) and game meat 011219, which went to 011221 (it
  added `شکار`), not to the game birds.

Where the counts still do not fit, the note says why, for example: landline
phones declining as mobiles spread; internet cafés closing under COVID in
1399; reports moving between insurance codes; a survey-wide jump with the
label unchanged (125112 in 1384, 127119 in 1387). Three notes leave the
cause open: 053312 halving in 1390, the 1386 public surgery fees halving, and
dialysis and chemotherapy rising from 36 to 207 households in 1395.

Each file only takes its own kind: a `change` or `add` with `merged` in
`curated/links.csv`, or with `same` in `curated/relations.csv`, is an
error. To change the chains of a relation, reject it and add the right one;
when a merge replaces a link (the "outside the home" items), reject the link.
`links.csv` and `relations.csv` record each decision in `verified` (`confirmed`,
`rejected`, `changed`, `added`) and the `note`; rejected relations stay in
the file but later stages ignore them. A decision whose relation is not
found (for example after a label correction merged two chains) is reported
as stale, and the tests fail until it is updated. The rows still to check
are those with `needs_verification` True.

Recodings, merges and splits are links between chains; the rest of this
section describes how `match.py` currently finds them in one pass.

Two descriptions are compared with spacing, ZWNJ, punctuation, hamza and
digit style ignored, then by character similarity (typos, joined words) and
by overlap of content words (scope changes). The result is one of `same`,
`minor`, `broadened`, `narrowed`, `reworded` or `different`. A `reworded`
pair must still share its head noun, so آبگرمکن گازی → کولرگازی counts as
`different`.

A series stands for one comparable definition. Wording changes and new
codes keep the series; merges and splits end it and start new series, so
the values of one `series_id` can be compared across all of its years.

| Change | Meaning |
|---|---|
| `start` | first appearance |
| `minor` / `broadened` / `narrowed` / `reworded` | same code, wording changed (scope changes are listed for review) |
| `recoded` | same item under a new code |
| `reappeared` | back after being missing for up to two questionnaires |
| `code_reused` | the code now means something unrelated, so a new series starts |
| `merged_into` | the series ends because its item was combined with others (`related_series`: the new series) |
| `merged_from` | a new series for the combined item (`related_series`: all the series it combines) |
| `split_into` | the series ends because its item was divided (`related_series`: the new series) |
| `split_from` | a new series for one of the parts (`related_series`: the series it came from) |

A group can also collapse into its residual item: in 1390 "سایر انواع
تلویزیون رنگی داخلی" (other domestic colour TVs) became "انواع تلویزیون رنگی
داخلی" (all of them) while the 21-inch item disappeared. When a "سایر X" item
becomes "X" and related items of its code group vanish that year, they are
all merged into a new series (six cases: TVs and new cars in 1390,
collections and surgery fees in 1386).

For example, in 1386 هزینه باغبانی (`044414-1383`) absorbed سرایداری and
میراب: all three series end as `merged_into 044414-1386`, and
`044414-1386` starts as `merged_from` them. Follow `related_series` to go
from a series to its predecessors or successors.

Many health services are asked once per kind of provider: "(دولتی)" /
"(خصوصی)" in 1383–1394, and "G" / "NG" from 1395. G covers centres owned by
the medical universities and NG all other providers, including social
security, the armed forces, private and charity, so NG covers more than
خصوصی did. The qualifier stays in the text but is left out of the
comparison, and a series only continues into an item for the same provider:
دولتی → G, خصوصی → NG. An item asked for all providers that becomes a G/NG
pair is recorded as a split (e.g. خدمات آمبولانس in 1395).

The files store change points only, like the year-keyed histories in
`commodities.yaml`: a series whose text never changes has a single row.
A series is identified by the expenditure code and year it started with,
e.g. `011114-1383`, so all series that ever used a code sort together.

| File | Content |
|---|---|
| `series.csv` | one row per series: first/last year, missing years, latest expenditure code, how it ends (`merged_into`, `split_into`, `dropped`, or empty if still asked in 1403) |
| `codes.csv` | one row per series and code: the years the series was asked under that code. Only the 11 recoded series have more than one row. Each (expenditure code, year) belongs to exactly one series, so this is the table to join the raw data on |
| `history.csv` | the starting row of each series plus one row per change; years without a row keep the previous text |
| `review.csv` | every non-trivial change (rewordings, scope changes, recodings, merges, splits, reuse), with old and new text side by side and an empty `decision` column |

## How it works

- `pdf_text.py` rebuilds right-to-left text from glyph positions. Glyphs without
  a Unicode mapping (1382) are decoded through their glyph names, and ZWNJs are
  recovered where the font uses contextual glyph forms.
- `glyph_db.py` repairs fonts whose ToUnicode map is wrong (1395, 1396, 1399,
  1402: بخش extracts as لاوش). Each glyph's outline is hashed and looked up in
  `src/hiesir_codebook/data/glyph_db.json` (tracked), which is built from the clean PDFs. A font is treated as
  broken when its ToUnicode map disagrees with the database: clean PDFs agree
  100%, broken fonts disagree on 0.8% or more. To rebuild the database:
  `uv run python -m hiesir_codebook.build_glyph_db`.
- `parse.py` finds code lines and attaches wrapped description lines to them,
  using the table rules and column borders.
- `correct.py` applies `curated/source.csv` and `curated/labels.csv`
  to `output/1_extracted/` and checks the result against the household occurrence
  table. `scripts/suggest_labels.py` uses hazm to suggest rows for
  `labels.csv`.
- `compare.py` compares two descriptions (`same`, `minor`, `broadened`, ...)
  and handles provider qualifiers; shared by the matching stages.
- `chains.py` builds the chains (matching stage 1), `relations.py` links them
  (stage 2), `match.py` is the older one-pass matcher (see above).
- `validate.py` checks each year's extracted codes against the codes that
  occur in the raw data (`data/commodity_code_occurrence_*.csv`).
- `utils.py` holds the Persian text normalisation helpers, usable on their own:
  `normalize_persian` (letters, digits, tatweel, spacing), `to_ascii_digits` /
  `to_persian_digits`, `canonical` (presentation forms → base letters),
  `normalize_visual` (fix-up for right-to-left glyph text) and `loose_key`
  (comparison that ignores spacing, ZWNJ and punctuation).
