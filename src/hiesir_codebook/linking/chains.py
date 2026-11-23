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
That needs each code printed once a year, which the structure check of
``output/2_corrected/`` guarantees; a code printed twice is an error.

How chains relate to each other (a reworded label, a new code, a merge) is
the job of the next stage, :mod:`hiesir_codebook.linking.relations`.

Output: ``chains.csv``, one row per chain.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .. import CORRECTED, ITEMS, csv_io
from .compare import MAX_GAP, YEARS, Item, load_year, relate


@dataclass
class Chain:
    id: str
    section: int
    code: str
    text: str
    years: list[int] = field(default_factory=list)


def build_chains(items_by_year: dict[int, list[Item]], max_gap: int = MAX_GAP) -> list[Chain]:
    """Chains of the items of every year.  Each code is printed once a year:
    the structure check of ``output/2_corrected/`` guarantees it (``duplicate``)."""
    years = sorted(items_by_year)
    chains: list[Chain] = []
    current: dict[str, Chain] = {}  # code -> its latest chain

    for yi, year in enumerate(years):
        window = set(years[max(0, yi - max_gap - 1) : yi])
        codes = [it.code for it in items_by_year[year]]
        if len(set(codes)) != len(codes):
            twice = sorted({c for c in codes if codes.count(c) > 1})
            raise ValueError(f"{year}: codes printed twice {twice}; fix them in curated/2_corrected/")
        for it in items_by_year[year]:
            c = current.get(it.code)
            if c is not None and c.years[-1] in window and relate(c.text, it.text).kind == "same":
                c.years.append(year)
                c.text = it.text
            else:
                current[it.code] = Chain(f"{it.code}-{year}", it.section, it.code, it.text, [year])
                chains.append(current[it.code])
    return chains


def missing_years(c: Chain, years: list[int]) -> list[int]:
    return [y for y in years if c.years[0] <= y <= c.years[-1] and y not in c.years]


def write_chains(chains: list[Chain], path: Path, years: list[int]) -> None:
    header = ["chain_id", "section", "expenditure_code", "first_year", "last_year", "missing_years", "text"]
    with csv_io.writer(path, header) as w:
        for c in sorted(chains, key=lambda c: (c.section, c.code, c.years[0])):
            missing = " ".join(map(str, missing_years(c, years)))
            w.writerow([c.id, c.section, c.code, c.years[0], c.years[-1], missing, c.text])


def read_chains(path: Path, years: list[int] = YEARS) -> list[Chain]:
    """Chains back from ``chains.csv`` (years rebuilt from the span and the
    missing years)."""
    out = []
    for r in csv_io.read(path):
        first, last = int(r["first_year"]), int(r["last_year"])
        missing = {int(y) for y in r["missing_years"].split()}
        ys = [y for y in years if first <= y <= last and y not in missing]
        out.append(Chain(r["chain_id"], int(r["section"]), r["expenditure_code"], r["text"], ys))
    return out


def main(*, source: Path = CORRECTED, out: Path = ITEMS / "chains.csv", max_gap: int = MAX_GAP) -> None:
    """Matching stage 1: chains, output/2_corrected/ -> output/3_items/chains.csv.

    Parameters
    ----------
    source
        The yearly CSVs.
    out
        Where the chains go.
    max_gap
        Questionnaires a chain may skip.
    """
    chains = build_chains({y: load_year(y, source) for y in YEARS}, max_gap)
    write_chains(chains, out, YEARS)
    print(f"{len(chains)} chains, {sum(c.years[-1] == YEARS[-1] for c in chains)} still asked in {YEARS[-1]}")
