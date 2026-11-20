"""Matching, stage 1: chains.

A *chain* is one expenditure code with one label, followed through the
corrected questionnaires (``output/2_corrected/``) for as long as both stay the same.
Labels count as the same when they differ only in spacing, ZWNJ,
punctuation, hamza or digit style (``same`` in
:func:`hiesir_codebook.linking.compare.compare`).

A chain ends when its code disappears for more than ``MAX_GAP``
questionnaires in a row, or when its label changes in any other way; the
changed label starts a new chain.  So every chain has exactly one code and
one text, and every item of every year belongs to exactly one chain.

How chains relate to each other (a reworded label, a new code, a merge) is
the job of the next stage, :mod:`hiesir_codebook.linking.relations`.

Output: ``chains.csv``, one row per chain.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass, field
from pathlib import Path

from .. import CORRECTED, ITEMS
from .compare import MAX_GAP, YEARS, Item, load_year, relate


@dataclass
class Chain:
    id: str
    section: int
    code: str
    text: str
    years: list[int] = field(default_factory=list)


def build_chains(items_by_year: dict[int, list[Item]], max_gap: int = MAX_GAP) -> list[Chain]:
    years = sorted(items_by_year)
    chains: list[Chain] = []
    ids: set[str] = set()
    current: dict[str, Chain] = {}  # code -> its latest chain

    for yi, year in enumerate(years):
        window = set(years[max(0, yi - max_gap - 1) : yi])
        seen: set[str] = set()
        for it in items_by_year[year]:
            c = current.get(it.code)
            if (
                it.code not in seen
                and c is not None
                and c.years[-1] in window
                and relate(c.text, it.text).kind == "same"
            ):
                c.years.append(year)
                c.text = it.text
            else:
                cid, n = f"{it.code}-{year}", 2
                while cid in ids:  # same code printed twice in one year
                    cid, n = f"{it.code}-{year}-{n}", n + 1
                ids.add(cid)
                current[it.code] = Chain(cid, it.section, it.code, it.text, [year])
                chains.append(current[it.code])
            seen.add(it.code)
    return chains


def missing_years(c: Chain, years: list[int]) -> list[int]:
    return [y for y in years if c.years[0] <= y <= c.years[-1] and y not in c.years]


def write_chains(chains: list[Chain], path: Path, years: list[int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(
            ["chain_id", "section", "expenditure_code", "first_year", "last_year", "missing_years", "text"]
        )
        for c in sorted(chains, key=lambda c: (c.section, c.code, c.years[0])):
            missing = " ".join(map(str, missing_years(c, years)))
            w.writerow([c.id, c.section, c.code, c.years[0], c.years[-1], missing, c.text])


def read_chains(path: Path, years: list[int] = YEARS) -> list[Chain]:
    """Chains back from ``chains.csv`` (years rebuilt from the span and the
    missing years)."""
    out = []
    with open(path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            first, last = int(r["first_year"]), int(r["last_year"])
            missing = {int(y) for y in r["missing_years"].split()}
            ys = [y for y in years if first <= y <= last and y not in missing]
            out.append(Chain(r["chain_id"], int(r["section"]), r["expenditure_code"], r["text"], ys))
    return out


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(
        prog="python -m hiesir_codebook.linking.chains", description="Matching stage 1: chains."
    )
    ap.add_argument(
        "--source", type=Path, default=CORRECTED, help="yearly CSVs (default: output/2_corrected/)"
    )
    ap.add_argument("--out", type=Path, default=ITEMS / "chains.csv")
    ap.add_argument("--max-gap", type=int, default=MAX_GAP, help="questionnaires a chain may skip")
    args = ap.parse_args(argv)
    chains = build_chains({y: load_year(y, args.source) for y in YEARS}, args.max_gap)
    write_chains(chains, args.out, YEARS)
    print(f"{len(chains)} chains, {sum(c.years[-1] == YEARS[-1] for c in chains)} still asked in {YEARS[-1]}")


if __name__ == "__main__":
    main()
