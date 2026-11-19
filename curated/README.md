# curated/ — hand-kept decisions

These are the only data files anyone edits; every row says why.

| File | What it fixes | Applied by |
|---|---|---|
| `source.csv` | single items in a single year: wrong codes, wrong texts, missing sections | `correct` |
| `labels.csv` | spellings that recur across rows and years: typos, glued words, ZWNJs | `correct` |
| `links.csv` | decisions on 1 → 1 links between chains (`from_chain` → `to_chain`, same or recoded): confirm, reject, change, add | `relations` |
| `relations.csv` | decisions on merges, splits and regroupings between chain sets (`from_chains` → `to_chains`): confirm, reject, change, add | `relations` |

After editing, run `uv run hiesir-codebook build --no-extract` and review
the diff in `output/`. The columns are described in `docs/methods.md`.
