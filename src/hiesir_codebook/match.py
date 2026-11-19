"""Link questionnaire items across years (1383 onwards).

Each item is followed through the corrected yearly questionnaires
(``output/2_corrected/``) as a *series*: the same thing asked about in successive
questionnaires, even when its wording changes slightly, its code changes,
or it is missing from a year.

Descriptions are compared with :mod:`hiesir_codebook.compare`.

Linking years
-------------
For every year, in order:

1. an item continues the series that last had its code, unless the texts
   are ``different`` -> the code was reused, a new series starts
   (``code_reused``);
2. a left-over item whose text matches a series whose code disappeared
   continues that series under the new code (``recoded``);
   If the old text was a residual "سایر X" (other X) and the new one is
   just "X", the related items of its code group that disappear the same
   year were folded into it: all of them are merged (1390: 21-inch TVs +
   other TVs -> all TVs);
3. a series whose item is now asked twice, once for public and once for
   other providers (see below), is closed as ``split_into`` the two new
   series, which start as ``split_from`` it;
4. a series that disappears while its text is contained in an item that
   continued another series is merged: both series end (``merged_into``)
   and the item starts a new series (``merged_from`` both);
5. a left-over item whose text was part of an item of the previous year is
   split out of it: that series ends (``split_into``) and both its item and
   the new one start new series (``split_from`` it);
6. any other left-over item starts a series (``code_reused`` if its code
   belonged to a series last year).

A series therefore stands for one comparable definition: merges and splits
end it, while wording changes (``minor``, ``broadened``, ``narrowed``,
``reworded``) and recodings keep it.  Follow ``related_series`` to go from
one series to its predecessors or successors.

Provider qualifiers (دولتی / خصوصی, G / NG) are handled as in
:mod:`hiesir_codebook.compare`: a series only continues into an item
for the same provider.

A series may skip up to ``MAX_GAP`` questionnaires (``reappeared``).

Output (change points only, like the YAML histories)
-----------------------------------------------------
``series.csv``   one row per series: years, missing years, latest code, how it ends
``codes.csv``    one row per series and code: the years it was asked under that
                 code; maps (expenditure code, year) in the raw data to a series
``history.csv``  the row that starts each series and one row per change; a
                 year without a row repeats the previous one
``review.csv``   the changes that need a human decision
"""

from __future__ import annotations

import argparse
import csv
import itertools
from dataclasses import dataclass, field
from pathlib import Path

from . import CORRECTED, MATCHED
from .compare import (
    MAX_GAP,
    YEARS,
    Item,
    Relation,
    compare,
    contained,
    load_year,
    relate,
    split_qualifier,
)
from .utils import loose_key, words

CONTINUES = ("same", "minor", "broadened", "narrowed", "reworded")
REVIEW_KINDS = (
    "reworded",
    "broadened",
    "narrowed",
    "recoded",
    "code_reused",
    "merged_from",
    "split_from",
    "reappeared",
)

# --- data ---------------------------------------------------------------------


@dataclass
class Change:
    year: int
    code: str
    text: str
    change: str  # "start" or one of CONTINUES / REVIEW_KINDS
    score: float | None = None
    prev_code: str = ""
    prev_text: str = ""
    related: str = ""  # series merged into / split from / split into


@dataclass
class Series:
    id: str
    section: int
    history: list[Change] = field(default_factory=list)
    years: list[int] = field(default_factory=list)
    text: str = ""  # wording in the latest year seen
    end: str = ""  # "merged_into <id>" / "split_into <id> <id>" when closed

    @property
    def code(self) -> str:
        live = [c for c in self.history if c.change not in ("merged_into", "split_into")]
        return live[-1].code


# --- linking ------------------------------------------------------------------


def _best(pairs):
    """Highest-scoring (candidate, relation) pair, or None."""
    pairs = [p for p in pairs if p[1] is not None]
    return max(pairs, key=lambda p: p[1].score) if pairs else None


def _rebase(s: Series, year: int, prev_text: str) -> None:
    """Undo the continuation of ``s`` into ``year``: it ends there instead."""
    if s.years[-1] == year:
        s.years.pop()
        s.history = [c for c in s.history if c.year != year]
        s.text = prev_text


def link(items_by_year: dict[int, list[Item]], max_gap: int = MAX_GAP) -> list[Series]:
    years = sorted(items_by_year)
    series: list[Series] = []
    used_ids: set[str] = set()

    def start(it: Item, change: Change) -> Series:
        # expenditure code first, so a code's series sort together: "011114-1383"
        sid, n = f"{it.code}-{it.year}", 2
        while sid in used_ids:  # same code twice in one year (a PDF typo)
            sid, n = f"{it.code}-{it.year}-{n}", n + 1
        used_ids.add(sid)
        s = Series(sid, it.section, [change], [it.year], it.text)
        series.append(s)
        return s

    def extend(s: Series, it: Item, change: Change | None) -> None:
        if change is not None:
            s.history.append(change)
        s.years.append(it.year)
        s.text = it.text

    for yi, year in enumerate(years):
        prev_year = years[yi - 1] if yi else None
        window = set(years[max(0, yi - max_gap - 1) : yi])
        open_ = [s for s in series if s.years[-1] in window and not s.end]
        prev_text = {s.id: s.text for s in open_}  # before this year's updates
        taken: dict[str, Item] = {}  # series id -> item that continued it
        pending: list[Item] = []

        # 1. same code: continue the series unless the text is unrelated
        by_code: dict[str, list[Series]] = {}
        for s in open_:
            by_code.setdefault(s.code, []).append(s)
        for it in items_by_year[year]:
            cands = [(s, relate(s.text, it.text)) for s in by_code.get(it.code, []) if s.id not in taken]
            hit = _best([(s, r) for s, r in cands if r.kind != "different"])
            if hit is None:
                pending.append(it)
                continue
            s, rel = hit
            taken[s.id] = it
            gap = s.years[-1] != prev_year
            if rel.kind == "same" and not gap:
                extend(s, it, None)
            else:
                kind = "reappeared" if gap and rel.kind == "same" else rel.kind
                extend(s, it, Change(year, it.code, it.text, kind, rel.score, s.code, s.text))

        # 2. code changed: match left-over items to series whose code disappeared
        orphans = [s for s in open_ if s.id not in taken]
        left: list[Item] = []
        for it in pending:
            hit = _best(
                (s, r)
                for s in orphans
                if s.id not in taken and s.section == it.section
                for r in [relate(s.text, it.text)]
                if r.kind in ("same", "minor", "broadened", "narrowed") and r.score >= 0.5
            )
            if hit is None:
                left.append(it)
                continue
            s, rel = hit
            taken[s.id] = it
            extend(s, it, Change(year, it.code, it.text, "recoded", rel.score, s.code, s.text))

        # 2b. collapsed groups: "سایر X" (other X) becomes "X" while related
        #     items of its code group disappear, e.g. 1390: 21-inch TVs +
        #     other TVs -> all TVs.  The residual and the items it absorbed are
        #     merged into a new series.
        residuals = {}
        for s in open_:
            if s.id in taken and "سایر" in words(prev_text[s.id]) and "سایر" not in words(taken[s.id].text):
                last = s.history[-1]
                residuals[s.id] = (
                    s,
                    (last.prev_code if last.year == year and last.prev_code else s.code)[:-1],
                )
        absorbed_by: dict[str, list[Series]] = {}
        for t in open_:
            if t.id in taken or t.end or t.years[-1] != prev_year:
                continue
            hit = _best(
                (s, r)
                for s, group in residuals.values()
                if s.section == t.section and t.code[:-1] == group
                for r in [relate(t.text, taken[s.id].text)]
                if r.kind != "different" and r.old_kept >= 0.5
            )
            if hit is not None:
                absorbed_by.setdefault(hit[0].id, []).append(t)
        for sid, gone in absorbed_by.items():
            s, it = residuals[sid][0], taken[sid]
            _rebase(s, year, prev_text[sid])
            del taken[sid]
            olds = [s, *gone]
            new = start(
                it,
                Change(
                    year,
                    it.code,
                    it.text,
                    "merged_from",
                    None,
                    s.code,
                    " | ".join(o.text for o in olds),
                    " ".join(o.id for o in olds),
                ),
            )
            for o in olds:
                o.history.append(Change(year, it.code, it.text, "merged_into", None, o.code, o.text, new.id))
                o.end = f"merged_into {new.id}"

        # 3. provider split: one series is now asked as a G / NG pair
        left = provider_splits(year, left, [s for s in open_ if s.id not in taken], start)

        # 4. merges: series gone this year whose text lives on in a continued
        #    item; the continuing series ends as well and a new one starts
        survivors = {s.id: s for s in open_ if s.id in taken}
        absorbed: dict[str, list[tuple[Series, Relation]]] = {}
        for s in open_:
            if s.id in taken or s.end or s.years[-1] != prev_year:
                continue
            hit = _best(
                (t, contained(s.text, taken[t.id].text))
                for t in survivors.values()
                if t.section == s.section and t.id != s.id
            )
            if hit is not None:
                absorbed.setdefault(hit[0].id, []).append((s, hit[1]))
        for tid, merged in absorbed.items():
            t, it = survivors[tid], taken[tid]
            _rebase(t, year, prev_text[t.id])
            olds = [t, *(m for m, _ in merged)]
            score = min(r.score for _, r in merged)
            new = start(
                it,
                Change(
                    year,
                    it.code,
                    it.text,
                    "merged_from",
                    score,
                    t.code,
                    " | ".join(o.text for o in olds),
                    " ".join(o.id for o in olds),
                ),
            )
            for o in olds:
                o.history.append(Change(year, it.code, it.text, "merged_into", score, o.code, o.text, new.id))
                o.end = f"merged_into {new.id}"

        # 5. new series: code reused, split out of last year's item, or new
        splits: dict[str, list[tuple[Item, Relation]]] = {}
        for it in left:
            reused = next((s for s in open_ if s.code == it.code and s.years[-1] == prev_year), None)
            if reused is not None:
                rel = relate(prev_text[reused.id], it.text)
                start(
                    it,
                    Change(
                        year, it.code, it.text, "code_reused", rel.score, reused.code, prev_text[reused.id]
                    ),
                )
                continue
            hit = _best(
                (s, contained(it.text, prev_text[s.id]))
                for s in open_
                if s.id in taken and s.section == it.section and prev_year in s.years
            )
            if hit is None:
                start(it, Change(year, it.code, it.text, "start"))
            else:
                splits.setdefault(hit[0].id, []).append((it, hit[1]))
        # the source series ends; its remaining item and the parts split out
        # of it start new series
        for sid, parts in splits.items():
            src = next(s for s in open_ if s.id == sid)
            if src.end:  # already closed by a merge this year
                for it, rel in parts:
                    start(
                        it,
                        Change(
                            year, it.code, it.text, "split_from", rel.score, src.code, prev_text[sid], sid
                        ),
                    )
                continue
            _rebase(src, year, prev_text[sid])
            rest = taken[sid]
            parts = [(rest, relate(src.text, rest.text)), *parts]
            new = [
                start(it, Change(year, it.code, it.text, "split_from", rel.score, src.code, src.text, sid))
                for it, rel in parts
            ]
            ids = " ".join(n.id for n in new)
            src.history.append(Change(year, "", "", "split_into", None, src.code, src.text, ids))
            src.end = f"split_into {ids}"
    return series


def provider_splits(year: int, items: list[Item], orphans: list[Series], start) -> list[Item]:
    """Close each orphan series for all providers whose text matches a new
    public / private pair as ``split_into`` the pair; return the items that
    were not used."""
    pairs: dict[tuple[int, str], dict[str, Item]] = {}
    for it in items:
        base, q = split_qualifier(it.text)
        if q:
            pairs.setdefault((it.section, loose_key(base)), {})[q] = it
    # best matches first, so a weak candidate cannot take another pair's series
    cands = []
    for (section, _), pair in pairs.items():
        if set(pair) != {"public", "private"}:
            continue
        base = split_qualifier(pair["public"].text)[0]
        for s in orphans:
            if s.end or s.section != section or split_qualifier(s.text)[1]:
                continue
            r = compare(s.text, base)
            if r.kind in CONTINUES and r.score >= 0.5:
                cands.append((r.score, s, pair, base, r))
    used: set[int] = set()
    for _, s, pair, base, rel in sorted(cands, key=lambda c: -c[0]):
        if s.end or id(pair["public"]) in used:
            continue
        new = [
            start(it, Change(year, it.code, it.text, "split_from", rel.score, s.code, s.text, s.id))
            for it in (pair["public"], pair["private"])
        ]
        ids = " ".join(n.id for n in new)
        s.history.append(Change(year, "", base, "split_into", rel.score, s.code, s.text, ids))
        s.end = f"split_into {ids}"
        used.update(id(it) for it in pair.values())
    return [it for it in items if id(it) not in used]


# --- output -------------------------------------------------------------------


def _write(path: Path, header: list[str], rows) -> None:
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def code_periods(s: Series) -> list[tuple[str, int, int]]:
    """(expenditure code, first year, last year) for each stretch of years in
    which the series was asked under one code; one entry unless recoded."""
    live = [c for c in s.history if c.change not in ("merged_into", "split_into")]

    def code_in(year: int) -> str:
        return [c.code for c in live if c.year <= year][-1]

    out = []
    for code, ys in itertools.groupby(s.years, key=code_in):
        ys = list(ys)
        out.append((code, ys[0], ys[-1]))
    return out


def write_outputs(series: list[Series], out_dir: Path, years: list[int]) -> dict[str, int]:
    out_dir.mkdir(parents=True, exist_ok=True)
    order = sorted(series, key=lambda s: (s.section, s.history[0].code, s.history[0].year))

    def series_row(s: Series) -> list:
        span = [y for y in years if s.years[0] <= y <= s.years[-1]]
        missing = " ".join(str(y) for y in span if y not in s.years)
        end = s.end or ("" if s.years[-1] == years[-1] else "dropped")
        return [s.id, s.section, s.years[0], s.years[-1], missing, s.code, len(s.history) - 1, end, s.text]

    _write(
        out_dir / "series.csv",
        [
            "series_id",
            "section",
            "first_year",
            "last_year",
            "missing_years",
            "expenditure_code",
            "n_changes",
            "end",
            "text",
        ],
        (series_row(s) for s in order),
    )
    _write(
        out_dir / "codes.csv",
        ["series_id", "expenditure_code", "first_year", "last_year"],
        ([s.id, *period] for s in order for period in code_periods(s)),
    )
    _write(
        out_dir / "history.csv",
        ["series_id", "from_year", "expenditure_code", "change", "score", "related_series", "text"],
        (
            [s.id, c.year, c.code, c.change, "" if c.score is None else c.score, c.related, c.text]
            for s in order
            for c in s.history
        ),
    )
    review = [
        [s.id, c.year, c.change, c.score, c.related, c.prev_code, c.code, c.prev_text, c.text, ""]
        for s in order
        for c in s.history
        if c.change in REVIEW_KINDS
    ]
    _write(
        out_dir / "review.csv",
        [
            "series_id",
            "year",
            "change",
            "score",
            "related_series",
            "prev_code",
            "code",
            "prev_text",
            "text",
            "decision",
        ],
        review,
    )
    counts: dict[str, int] = {"series": len(series), "review": len(review)}
    for s in series:
        for c in s.history:
            counts[c.change] = counts.get(c.change, 0) + 1
    return counts


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(
        prog="python -m hiesir_codebook.match", description="Link items across years."
    )
    ap.add_argument(
        "--source",
        type=Path,
        default=CORRECTED,
        help="folder with the yearly CSVs (default: output/2_corrected/)",
    )
    ap.add_argument("--out", type=Path, default=MATCHED, help="output folder (default: output/3_matched/)")
    ap.add_argument("--max-gap", type=int, default=MAX_GAP, help="questionnaires a series may skip")
    args = ap.parse_args(argv)
    items = {y: load_year(y, args.source) for y in YEARS}
    counts = write_outputs(link(items, args.max_gap), args.out, YEARS)
    print(" ".join(f"{k}={v}" for k, v in counts.items()))


if __name__ == "__main__":
    main()
