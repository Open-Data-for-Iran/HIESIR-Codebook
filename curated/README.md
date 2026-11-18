# curated/ — hand-kept decisions

These are the only data files anyone edits; every row says why.

| File | What it fixes | Applied by |
|---|---|---|
| `source.csv` | single items in a single year: wrong codes, wrong texts, missing sections | `correct` |
| `labels.csv` | spellings that recur across rows and years: typos, glued words, ZWNJs | `correct` |

After editing, run `uv run hbsir-questionnaire build --no-extract` and review
the diff in `output/`. See the main README for the column definitions.
