# output/ — generated, do not edit

Everything here is written by the pipeline and is overwritten on every run:

```bash
uv run hiesir-codebook build            # all stages (reads data/pdf/ if present)
uv run hiesir-codebook build --no-extract   # keep 1_extracted/, rebuild the rest
```

| Folder | Written by | From |
|---|---|---|
| `1_extracted/` | `hiesir-codebook extract` | the PDFs in `data/pdf/`, exactly as printed |
| `2_corrected/` | `python -m hiesir_codebook.correction.correct`; `autocorrect/` by `python -m hiesir_codebook.correction.canonical` and `correction.autocorrect` | `1_extracted/` + `curated/2_corrected/` |
| `3_items/` | `python -m hiesir_codebook.linking.chains` (chains.csv), `linking.relations` (links.csv, relations.csv) | `2_corrected/` + `curated/3_items/` |
| `4_groups/` | `python -m hiesir_codebook.linking.groups` (groups.csv, members.csv, links.csv) | `2_corrected/`, `3_items/` + `curated/4_groups/` |
| `metrics.json` | `python -m hiesir_codebook.metrics` | every folder above: the figures the documentation quotes |

The explorer is not here: the documentation site makes its data from these
CSVs when it is built (`scripts/mkdocs_hooks.py`).

To change a result, edit `curated/` (or the code) and rebuild. The files are
tracked so that every change to the extractor, a correction or the matcher
shows up as a diff; the tests fail when a folder is out of date.
