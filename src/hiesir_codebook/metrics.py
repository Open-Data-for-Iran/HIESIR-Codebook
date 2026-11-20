"""The figures of the build, in one tracked file: ``output/metrics.json``.

Written at the end of every ``hiesir-codebook build``, so any change to the
curated decisions or the code shows its effect as a diff of this file, and
read by the documentation (``scripts/mkdocs_hooks.py``), which writes
``{{ links.confirmed }}`` for the number of confirmed links, so the pages
never quote an out-of-date figure.

    uv run python -m hiesir_codebook.metrics
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path

from . import CORRECTED, CURATED_CORRECTED, EXTRACTED, GROUPS, ITEMS, OUTPUT, SUPPORTED_YEARS
from .correction import correct
from .linking.chains import read_chains
from .linking.compare import YEARS
from .linking.relations import code_reuse

OUT = OUTPUT / "metrics.json"
DECIDED_BY = ("code", "curated", "open")
VERIFIED = ("confirmed", "changed", "rejected", "added")


def _read(path: Path) -> list[dict[str, str]]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _span(years: list[int]) -> str:
    """[1383, 1386, 1390] -> "1383–1390"."""
    return f"{min(years)}–{max(years)}" if len(set(years)) > 1 else str(years[0])


def _decisions(rows: list[dict[str, str]], kinds: tuple[str, ...] = ()) -> dict[str, int]:
    """How many rows, how many are kept (not rejected), who decided them and
    how; with ``kinds``, the kept rows of each relation."""
    by = Counter(r["decided_by"] for r in rows)
    how = Counter(r["verified"] for r in rows)
    kept = [r for r in rows if r["verified"] != "rejected"]
    out = {"total": len(rows), "kept": len(kept)}
    out |= {k: by[k] for k in DECIDED_BY}
    out |= {k: how[k] for k in VERIFIED}
    rel = Counter(r["relation"] for r in kept)
    out |= {k: rel[k] for k in kinds}
    return out


def _labels(
    extracted: Path, corrections: Path, labels: Path, suggestions: Path, decisions: Path
) -> dict[str, int]:
    """How many descriptions (items, headers and section titles, all years)
    each step of the correction changes, replayed in the order correct.apply
    runs them."""
    fixes = correct.load_corrections(corrections)
    label_fixes = correct.load_label_fixes(labels)
    sugg_fixes, _ = correct.suggestion_fixes(suggestions, decisions)
    n = Counter()
    for year in SUPPORTED_YEARS:
        rows = correct.read_rows(extracted / f"questionnaire_{year}.csv")
        for r in correct.apply(year, rows, fixes, extracted, tidy=False):
            t0 = r["description"]
            t1 = correct.house_style(t0)
            t2 = correct.fix_label(t1, year, label_fixes)
            t3 = correct.fix_label(t2, year, sugg_fixes)
            n["rows"] += 1
            n["punctuation"] += t1 != t0
            n["spelling"] += t2 != t1
            n["suggestions"] += t3 != t2
    return dict(n)


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
    suggestions = corrected / "spelling_suggestions.csv"
    decisions = curated / "spelling_suggestions.csv"

    fixes = correct.load_corrections(corrections)
    changed = _labels(extracted, corrections, labels, suggestions, decisions)
    sugg = _read(suggestions)
    accepted, _ = correct.suggestion_fixes(suggestions, decisions)

    item_years = {}
    for y in SUPPORTED_YEARS:
        rows = _read(corrected / f"questionnaire_{y}.csv")
        item_years[str(y)] = sum(r["kind"] == "item" for r in rows)

    chains = read_chains(items / "chains.csv")
    link_rows = _read(items / "links.csv")
    relation_rows = _read(items / "relations.csv")
    # as relations.main: a pair already related in any way is no reuse
    linked = {(r["from_chain"], r["to_chain"]) for r in link_rows} | {
        (a, b) for r in relation_rows for a in r["from_chains"].split() for b in r["to_chains"].split()
    }
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
            "punctuation": changed["punctuation"],
            "spelling": changed["spelling"],
            "suggestions": changed["suggestions"],
        },
        "spelling": {"total": len(correct.load_label_fixes(labels))},
        "suggestions": {
            "total": len(sugg),
            "auto": sum(r["apply"] == "yes" for r in sugg),
            "decisions": len(correct.load_decisions(decisions)),
            "applied": len(accepted),
        },
        "chains": {
            "total": len(chains),
            "asked_last_year": sum(c.years[-1] == YEARS[-1] for c in chains),
        },
        "links": _decisions(link_rows, ("same", "recoded")),
        "relations": _decisions(relation_rows, ("merged", "split", "regrouped")),
        "code_reuse": len(reused),
        "groups": {
            "total": len(_read(groups / "groups.csv")),
            "links": _decisions(
                _read(groups / "links.csv"), ("continued", "split", "merged", "regrouped", "moved")
            ),
        },
    }


def to_json(metrics: dict) -> str:
    return json.dumps(metrics, ensure_ascii=False, indent=2) + "\n"


def lookup(metrics: dict, key: str):
    """``lookup(m, "links.confirmed")``: one figure by its dotted name."""
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


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="python -m hiesir_codebook.metrics", description=__doc__)
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)
    print(f"metrics -> {build(args.out).as_posix()}")


if __name__ == "__main__":
    main()
