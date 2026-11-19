# output/ — generated, do not edit

Everything here is written by the pipeline and is overwritten on every run:

```bash
uv run hiesir-codebook build            # all stages (reads data/pdf/ if present)
uv run hiesir-codebook build --no-extract   # keep 1_extracted/, rebuild the rest
```

| Folder | Written by | From |
|---|---|---|
| `1_extracted/` | `hiesir-codebook all` | the PDFs in `data/pdf/`, exactly as printed |
| `2_corrected/` | `python -m hiesir_codebook.correct` | `1_extracted/` + `curated/source.csv` and `curated/labels.csv` |
| `3_matched/` | `chains`, `relations` (links.csv, relations.csv), `match` | `2_corrected/` |
| `explorer/` | `python -m hiesir_codebook.explorer` | `2_corrected/`, `3_matched/`, `curated/source.csv`: one searchable HTML page |

To change a result, edit `curated/` (or the code) and rebuild. The files are
tracked so that every change to the extractor, a correction or the matcher
shows up as a diff; the tests fail when a folder is out of date.
