# output/ — generated, do not edit

Everything here is written by the pipeline and is overwritten on every run:

```bash
uv run hiesir-codebook build            # all stages (reads data/pdf/ if present)
uv run hiesir-codebook build --no-extract   # keep 1_extracted/, rebuild the rest
```

| Folder | Written by | From |
|---|---|---|
| `1_extracted/` | `hiesir-codebook extract` | the PDFs in `data/pdf/`, exactly as printed |
| `2_corrected/` | `hiesir-codebook correct`; `autocorrect/` (canonical.csv, words.csv) by `hiesir-codebook autocorrect` | `1_extracted/` + `curated/2_corrected/` |
| `3_items/` | `hiesir-codebook chains` (chains.csv), `changes` (changes.csv; the code's suggestions in suggested/), `series` (series.csv) | `2_corrected/` + `curated/3_items/` |
| `4_groups/` | `hiesir-codebook groups` (groups.csv, members.csv, changes.csv; the code's suggestions in suggested/) | `2_corrected/`, `3_items/` + `curated/4_groups/` |
| `5_results/` | `hiesir-codebook results` (years.csv, pdfs.csv, sections.csv, headers.csv, items.csv, chains.csv, series.csv, groups.csv, changes.csv, change_chains.csv, group_changes.csv, code_corrections.csv, code_usage.csv: one flat table per thing, with English labels; `hiesir-codebook bundle` releases them as a data package) | `2_corrected/`, `3_items/`, `4_groups/`, `data/` + `curated/*/labels_en.csv`, `curated/data/` |
| `metrics.json` | `hiesir-codebook metrics` | every folder above: the figures the documentation quotes |

`suggested/` holds every change the code found, before any
decision in `curated/`, with who decided it and how (`open`: not yet). The
files next to it hold only the results: decided and not rejected.

The explorer is not here: the documentation site makes its data from these
CSVs when it is built (`scripts/mkdocs_hooks.py`).

To change a result, edit `curated/` (or the code) and rebuild. The files are
tracked so that every change to the extractor, a correction or the matcher
shows up as a diff; the tests fail when a folder is out of date.
