"""Matching, stage 3: series.

A *series* is the chains that continuing changes join (``same``: the label
reworded; ``recoded``: a new code): one good or service followed through
rewording and recoding, until a merge, split or regrouping ends it.  A
continuing change is always one chain to one, and a chain has at most one
onward and one into it, so a series is a row of chains, one after the
other, and has one code in each year it is asked.

Breaking changes (merges, splits and regroupings, the other rows of
``changes.csv``) join no series: they end some and start others.  ``starts``
and ``ends`` name the changes that started or ended a series, so a series
that begins in 1389 out of a merge is not taken for a new item.  A chain on
both sides of such a change goes on through it, so the change neither ends
nor starts its series.

Output: ``output/3_items/series.csv``, one row per series; its id is ``I-``,
the code and the first year of its first chain (``I-011111-1383``; the chain
is ``C-011111-1383``).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path

from .. import ITEMS, csv_io
from .chains import Chain, read_chains
from .changes import CONTINUING
from .compare import YEARS


@dataclass
class Series:
    chains: list[Chain]  # in order of their years
    starts: list[str]  # ids of the merges, splits and regroupings that started it
    ends: list[str]  # ids of those that ended it

    @property
    def id(self) -> str:
        first = self.chains[0]
        return f"I-{first.code}-{first.years[0]}"

    @property
    def years(self) -> list[int]:
        return [y for c in self.chains for y in c.years]

    @property
    def last(self) -> Chain:
        return self.chains[-1]

    @property
    def codes(self) -> list[str]:
        """Its codes, each once, in the order it used them."""
        return list(dict.fromkeys(c.code for c in self.chains))


def build_series(
    chains: list[Chain],
    continuing: list[tuple[str, str]],
    breaking: list[tuple[str, list[str], list[str]]] = (),
) -> list[Series]:
    """The series of ``chains``, joined by the ``continuing`` changes (from
    chain, to chain); ``breaking`` are the merges, splits and regroupings as
    (id, from chains, to chains)."""
    by_id = {c.id: c for c in chains}
    onward: dict[str, str] = {}
    into: dict[str, str] = {}
    for a, b in continuing:
        for x in (a, b):
            if x not in by_id:
                raise ValueError(f"change {a} -> {b}: no chain {x}")
        if a in onward or b in into:
            raise ValueError(
                f"change {a} -> {b}: a chain continues through one change onward and one into it"
            )
        onward[a], into[b] = b, a

    started: dict[str, list[str]] = defaultdict(list)
    ended: dict[str, list[str]] = defaultdict(list)
    for rid, before, after in breaking:
        for x in after:
            if x not in before:
                started[x].append(rid)
        for x in before:
            if x not in after:
                ended[x].append(rid)

    out = []
    for c in chains:
        if c.id in into:
            continue
        row = [c]
        while row[-1].id in onward:
            row.append(by_id[onward[row[-1].id]])
            if len(row) > len(chains):
                raise ValueError(f"changes from {c.id} run in a circle")
        for a, b in pairwise(row):
            if a.years[-1] >= b.years[0]:
                raise ValueError(f"series of {c.id}: {a.id} and {b.id} overlap in years")
        out.append(Series(row, started[row[0].id], ended[row[-1].id]))
    if sum(len(s.chains) for s in out) != len(chains):
        raise ValueError("changes run in a circle")
    return sorted(out, key=lambda s: (s.last.section, s.last.code, s.years[0]))


# --- files ---------------------------------------------------------------------


def read_changes(path: Path) -> tuple[list[tuple[str, str]], list[tuple[str, list[str], list[str]]]]:
    """The continuing changes of ``changes.csv`` (from chain, to chain), and
    the breaking ones (id, from chains, to chains)."""
    rows = csv_io.read(path)
    continuing = [(r["from_chains"], r["to_chains"]) for r in rows if r["type"] in CONTINUING]
    breaking = [
        (r["change_id"], r["from_chains"].split(), r["to_chains"].split())
        for r in rows
        if r["type"] not in CONTINUING
    ]
    return continuing, breaking


def write_series(series: list[Series], path: Path, years: list[int] = YEARS) -> None:
    header = [
        "series_id",
        "section",
        "first_year",
        "last_year",
        "missing_years",
        "codes",
        "chains",
        "starts",
        "ends",
        "text",
    ]
    with csv_io.writer(path, header) as w:
        for s in series:
            ys = s.years
            missing = " ".join(str(y) for y in years if ys[0] <= y <= ys[-1] and y not in ys)
            w.writerow(
                [
                    s.id,
                    s.last.section,
                    ys[0],
                    ys[-1],
                    missing,
                    " ".join(s.codes),
                    " ".join(c.id for c in s.chains),
                    " ".join(s.starts),
                    " ".join(s.ends),
                    s.last.text,
                ]
            )


def main(*, items: Path = ITEMS) -> None:
    """Matching stage 3: series, chains.csv + changes.csv -> output/3_items/series.csv.

    Parameters
    ----------
    items
        The folder with chains.csv and changes.csv; series.csv is written
        there.
    """
    series = build_series(read_chains(items / "chains.csv"), *read_changes(items / "changes.csv"))
    write_series(series, items / "series.csv")
    full = sum(s.years[0] == YEARS[0] and s.years[-1] == YEARS[-1] for s in series)
    recoded = sum(len(s.codes) > 1 for s in series)
    span = f"{YEARS[0]} to {YEARS[-1]}"
    print(f"{len(series)} series: {full} asked from {span}, {recoded} under more than one code")
