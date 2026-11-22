# HIESIR Codebook

The expenditure items of the Household Income and Expenditure Survey of Iran (HIES)
questionnaires, 1383–1403: extracted from the PDF forms, corrected, and
matched across years, so that the same item can be followed as its code and
wording change. (The 1382 form, with its older code scheme, is extracted and
corrected too, but not matched.)

- **Look up an item:** open the explorer, [`output/explorer/index.html`](output/explorer/index.html)
  (a single file, works offline). Search a code or Persian text to see the
  years it was asked, its code and label changes, what it was merged or split
  into, and whether it is comparable across years.
- **Read the documentation:** <https://open-data-for-iran.github.io/HIESIR-Codebook/>
  (in English and Farsi), built from [`docs/`](docs/):
  [data files](docs/data.md), [methods](docs/methods.md),
  [contributing](docs/contributing.md).

```
data/pdf ─extract─▶ 1_extracted ─correct─▶ 2_corrected ─match─▶ 3_items ─group─▶ 4_groups ─▶ explorer
                    as printed             as intended
                                     ▲                     ▲                ▲
                           curated/2_corrected/    curated/3_items/ curated/4_groups/
```

| Folder | Content | Edited by |
|---|---|---|
| `curated/` | hand-kept decisions, one row each with its reason | people |
| `output/` | every stage's result, tracked so each change shows as a diff | the pipeline only |
| `data/` | the PDFs (not in git: a GitHub release holds them) and the household occurrence tables (in git) | nobody |
| `docs/` | this documentation | people |

## Quick start

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv run hiesir-codebook build --no-extract   # rebuild output/ after editing curated/
uv run pytest -m "not slow"                     # tests, including "output/ is up to date"
uv run --group docs mkdocs serve                # preview the documentation site
```

Codes keep their leading zero (`011111`); the raw data stores them as numbers,
so join on `int(expenditure_code)`. See [data files](docs/data.md).

## License

MIT, see [LICENSE](LICENSE).
