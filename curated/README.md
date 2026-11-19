# curated/ — hand-kept decisions

These are the only data files anyone edits; every row says why. Each folder
holds the decisions applied to the `output/` folder of the same name.

| File | What it fixes | Applied by |
|---|---|---|
| `2_corrected/corrections.csv` | single items and group headers in a single year: wrong codes, wrong texts, missing sections | `correct` |
| `2_corrected/spelling.csv` | spellings that recur across rows and years: typos, glued words, ZWNJs | `correct` |
| `3_items/links.csv` | decisions on 1 → 1 links between chains (`from_chain` → `to_chain`, same or recoded): confirm, reject, change, add | `relations` |
| `3_items/relations.csv` | decisions on merges, splits and regroupings between chain sets (`from_chains` → `to_chains`): confirm, reject, change, add | `relations` |
| `4_groups/links.csv` | decisions on links between group headers (`from_group` → `to_group`: continued, split, merged, regrouped, moved): confirm, reject, change, add | `groups` |

After editing, run `uv run hiesir-codebook build --no-extract` and review
the diff in `output/`. The columns are described in `docs/methods.md`.
