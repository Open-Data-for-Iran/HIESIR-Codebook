"""The figures of the build, in one tracked file: ``output/metrics.json``.

Written at the end of every ``hiesir-codebook build``, so any change to the
curated decisions or the code shows its effect as a diff of this file, and
read by the documentation (``scripts/mkdocs_hooks.py``), which writes
``{{ changes.continuing.confirmed }}`` for the number of confirmed continuing
changes, so the pages
never quote an out-of-date figure.

    uv run hiesir-codebook metrics
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import polars as pl

from . import CORRECTED, CURATED_CORRECTED, EXTRACTED, GROUPS, ITEMS, OUTPUT, SUPPORTED_YEARS, csv_io
from .correction import corrections as step1
from .correction.fixes import Fixes, read_spelling
from .linking.chains import read_chains
from .linking.changes import BREAKING, CONTINUING, code_reuse
from .linking.compare import YEARS

OUT = OUTPUT / "metrics.json"
DECIDED_BY = ("code", "curated", "open")
VERIFIED = ("confirmed", "amended", "rejected", "added")


def _read(path: Path) -> list[dict[str, str]]:
    return csv_io.read(path)


def _span(years: list[int]) -> str:
    """[1383, 1386, 1390] -> "1383–1390"."""
    return f"{min(years)}–{max(years)}" if len(set(years)) > 1 else str(years[0])


def _all(folder: Path, name: str) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """The final rows of ``folder/name``, and every row: the final ones and
    the suggestions that are not (rejected or still open, in ``suggested/``)."""
    final = _read(folder / name)
    ids = {next(iter(r.values())) for r in final}
    rest = [r for r in _read(folder / "suggested" / name) if next(iter(r.values())) not in ids]
    return final, final + rest


def _kinds(
    final: list[dict[str, str]], rows: list[dict[str, str]], kinds: tuple[str, ...]
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """``final`` and ``rows`` (as from :func:`_all`) of the types ``kinds`` only."""
    return [r for r in final if r["type"] in kinds], [r for r in rows if r["type"] in kinds]


def _decisions(
    final: list[dict[str, str]], rows: list[dict[str, str]], kinds: tuple[str, ...] = ()
) -> dict[str, int]:
    """How many rows (suggested or added), how many are kept (final), who
    decided them and how; with ``kinds``, the kept rows of each type."""
    by = Counter(r["decided_by"] for r in rows)
    how = Counter(r["verified"] for r in rows)
    kept = final
    out = {"total": len(rows), "kept": len(kept)}
    out |= {k: by[k] for k in DECIDED_BY}
    out |= {k: how[k] for k in VERIFIED}
    types = Counter(r["type"] for r in kept)
    out |= {k: types[k] for k in kinds}
    return out


def _labels(extracted: Path, corrections: Path, fixes: Fixes) -> dict[str, int]:
    """How many descriptions (items, headers and section titles, all years)
    each label step of the correction changes: the columns of the traced table
    compared one with the next."""
    from .correction.correct import corrected

    df = corrected(SUPPORTED_YEARS, extracted, corrections, fixes)

    def changed(*pairs: tuple[str, str]) -> int:
        return df.select(pl.any_horizontal(pl.col(a) != pl.col(b) for a, b in pairs).sum()).item()

    return {
        "rows": df.height,
        "canonical": changed(("description", "canonical")),
        "punctuation": changed(("canonical", "house_style")),
        "autocorrect": changed(("letters", "words")),
        "spelling": changed(("house_style", "letters"), ("words", "spelling")),
    }


def compute(
    extracted: Path = EXTRACTED,
    corrected: Path = CORRECTED,
    curated: Path = CURATED_CORRECTED,
    items: Path = ITEMS,
    groups: Path = GROUPS,
) -> dict:
    """Every figure, as plain JSON-able data."""
    corrections = curated / "corrections.csv"
    labels = curated / "spelling.csv"
    auto = corrected / "autocorrect" / "words.csv"
    canonical = corrected / "autocorrect" / "canonical.csv"

    fixes = step1.load_corrections(corrections)
    label_fixes = Fixes.load(labels, auto, canonical)
    changed = _labels(extracted, corrections, label_fixes)
    auto_rows = csv_io.read(auto) if auto.exists() else []
    canonical_rows = csv_io.read(canonical) if canonical.exists() else []

    item_years = {}
    for y in SUPPORTED_YEARS:
        rows = _read(corrected / f"questionnaire_{y}.csv")
        item_years[str(y)] = sum(r["kind"] == "item" for r in rows)

    chains = read_chains(items / "chains.csv")
    final, rows = _all(items, "changes.csv")
    # as changes.main: a pair already related by any change is no reuse
    linked = {(a, b) for r in rows for a in r["from_chains"].split() for b in r["to_chains"].split()}
    reused = [p for p in code_reuse(chains, YEARS) if (p[0].id, p[1].id) not in linked]

    return {
        "questionnaires": {
            "years": len(SUPPORTED_YEARS),
            "items": sum(item_years.values()),
            "items_by_year": item_years,
        },
        "corrections": {
            "total": len(fixes),
            "years": _span([c.year for c in fixes]),
            **dict(sorted(Counter(c.action for c in fixes).items())),
        },
        "labels": {
            "total": changed["rows"],
            "canonical": changed["canonical"],
            "punctuation": changed["punctuation"],
            "spelling": changed["spelling"],
            "autocorrect": changed["autocorrect"],
        },
        "spelling": {"total": len(read_spelling(labels))},
        "canonical": {"total": len(canonical_rows)},
        "autocorrect": {
            "total": len(auto_rows),
            **dict(sorted(Counter(r["kind"] for r in auto_rows).items())),
        },
        "chains": {
            "total": len(chains),
            "asked_last_year": sum(c.years[-1] == YEARS[-1] for c in chains),
        },
        "changes": {
            "continuing": _decisions(*_kinds(final, rows, CONTINUING), CONTINUING),
            "breaking": _decisions(*_kinds(final, rows, BREAKING), BREAKING),
        },
        "code_reuse": len(reused),
        "groups": {
            "total": len(_read(groups / "groups.csv")),
            "changes": _decisions(
                *_all(groups, "changes.csv"), ("continued", "split", "merged", "regrouped", "moved")
            ),
        },
    }


def to_json(metrics: dict) -> str:
    return json.dumps(metrics, ensure_ascii=False, indent=2) + "\n"


def lookup(metrics: dict, key: str):
    """``lookup(m, "changes.continuing.confirmed")``: one figure by its dotted name."""
    value = metrics
    for part in key.split("."):
        if not isinstance(value, dict) or part not in value:
            raise KeyError(f"no metric {key!r} in {OUT.as_posix()}")
        value = value[part]
    if isinstance(value, dict):
        raise KeyError(f"{key!r} is a group of metrics, not one: {', '.join(value)}")
    return value


FIGURE = re.compile(r"\{\{\s*([\w.]+)\s*\}\}")
PERSIAN = str.maketrans("0123456789,", "۰۱۲۳۴۵۶۷۸۹٬")


def figure(value, lang: str = "en") -> str:
    """1064 -> "1,064" ("۱٬۰۶۴" in Farsi); text such as "1383–1390" as it is
    (in Persian digits in Farsi)."""
    text = f"{value:,}" if isinstance(value, int) else str(value)
    return text.translate(PERSIAN) if lang == "fa" else text


def fill(text: str, metrics: dict, lang: str = "en", where: str = "") -> str:
    """Every ``{{ name }}`` in a page replaced by its figure; an unknown name
    is an error, so a renamed metric cannot leave a page saying nothing."""

    def one(m: re.Match) -> str:
        try:
            return figure(lookup(metrics, m.group(1)), lang)
        except KeyError as e:
            raise ValueError(f"{where}: {e.args[0]}" if where else e.args[0]) from None

    return FIGURE.sub(one, text)


def build(out: Path = OUT, **kwargs) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(to_json(compute(**kwargs)))
    return out


def main(*, out: Path = OUT) -> None:
    """The figures of the build -> output/metrics.json.

    Parameters
    ----------
    out
        Where the figures go.
    """
    print(f"metrics -> {build(out).as_posix()}")
