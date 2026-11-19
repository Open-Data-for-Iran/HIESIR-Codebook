# output/ — generated, do not edit

Everything here is written by the pipeline and is overwritten on every run:

```bash
uv run hiesir-codebook build            # all stages (reads data/pdf/ if present)
uv run hiesir-codebook build --no-extract   # keep 1_extracted/, rebuild the rest
```

| Folder | Written by | From |
|---|---|---|
| `1_extracted/` | `hiesir-codebook all` | the PDFs in `data/pdf/`, exactly as printed |
| `2_corrected/` | `python -m hiesir_codebook.correct` | `1_extracted/` + `curated/2_corrected/corrections.csv` and `curated/2_corrected/spelling.csv` |
| `3_items/` | `python -m hiesir_codebook.chains` (chains.csv), `relations` (links.csv, relations.csv) | `2_corrected/` + `curated/3_items/` |
| `4_groups/` | `python -m hiesir_codebook.groups` (groups.csv, members.csv, links.csv) | `2_corrected/`, `3_items/` + `curated/4_groups/` |
| `explorer/` | `python -m hiesir_codebook.explorer` | `2_corrected/`, `3_items/`, `curated/2_corrected/corrections.csv`: one searchable HTML page |

To change a result, edit `curated/` (or the code) and rebuild. The files are
tracked so that every change to the extractor, a correction or the matcher
shows up as a diff; the tests fail when a folder is out of date.
