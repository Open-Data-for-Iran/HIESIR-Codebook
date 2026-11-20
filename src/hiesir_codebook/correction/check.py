"""Label check: a review aid for the corrected labels (``output/2_corrected/``).

It changes nothing; it lists, in ``reports/label_check.csv``, what may still
be misspelled, for a person to decide (a decision goes to
``curated/2_corrected/spelling.csv``):

========= =====================================================================
kind      what it finds
========= =====================================================================
unknown   a word hazm's dictionary does not know, nor as a plural, with
          ی / ای / تر ... or as a ZWNJ compound of known words.  Most are
          right (terms the dictionary lacks: لیزیک, بتادین); some are glued
          (جانفتی) or typos.  ``other`` gives how other years write the
          same letters for the same code, when that is all known words
variant   the same code reads with the same letters but other spacing or
          ZWNJs in other years (سرو صورت / سر و صورت, موتورسیکلت / موتور
          سیکلت).  ``find`` is the span in the fewer years, ``other`` the span
          in the most years; either may be the right one
========= =====================================================================

The ``unknown`` rows need hazm (``uv run --python 3.13 --extra hazm python -m
hiesir_codebook.correction.check``); without it only the ``variant`` rows are
written.
"""

from __future__ import annotations

import argparse
import csv
import difflib
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from .. import CORRECTED, REPORTS
from .spelling import _GAPS, _PERSIAN_ONLY, _WORD, Lexicon, known, other_form, years_text

REPORT = REPORTS / "label_check.csv"
COLUMNS = ["kind", "find", "other", "uses", "codes", "years", "other_years", "example"]


@dataclass
class Label:
    year: int
    key: str  # one item, header or section across years
    text: str


@dataclass
class Finding:
    kind: str
    find: str
    other: str = ""
    uses: int = 0
    codes: set[str] = field(default_factory=set)
    years: set[int] = field(default_factory=set)
    other_years: set[int] = field(default_factory=set)
    examples: set[str] = field(default_factory=set)


def _words(text: str) -> list[str]:
    return [w for w in _WORD.findall(text) if _PERSIAN_ONLY.fullmatch(w)]


def check(labels: Iterable[Label], lex: Lexicon | None) -> list[Finding]:
    labels = list(labels)
    by_key: dict[str, list[Label]] = defaultdict(list)
    for lb in labels:
        by_key[lb.key].append(lb)
    found: dict[tuple[str, str, str], Finding] = {}

    def add(kind: str, find: str, other: str, lb: Label, other_years: Iterable[int] = ()) -> None:
        f = found.setdefault((kind, find, other), Finding(kind, find, other))
        f.uses += 1
        f.codes.add(lb.key)
        f.years.add(lb.year)
        f.other_years.update(other_years)
        f.examples.add(lb.text)

    if lex is not None:
        for lb in labels:
            for w in _words(lb.text):
                if not known(w, lex):
                    siblings = sorted(
                        (s for s in by_key[lb.key] if s.year != lb.year), key=lambda s: abs(s.year - lb.year)
                    )
                    other = other_form(w, ((s.year, s.text) for s in siblings), lex)
                    add("unknown", w, other[0] if other else "", lb, [other[1]] if other else [])

    for group in by_key.values():
        same_letters: dict[str, list[Label]] = defaultdict(list)
        for lb in group:
            same_letters[_GAPS.sub("", lb.text)].append(lb)
        for forms in same_letters.values():
            count = Counter(lb.text for lb in forms)
            if len(count) < 2:
                continue
            top = max(count, key=lambda t: (count[t], t))
            top_years = {lb.year for lb in forms if lb.text == top}
            for lb in forms:
                if lb.text == top:
                    continue
                a, b = lb.text.split(), top.split()
                for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
                    if op != "equal":
                        add("variant", " ".join(a[i1:i2]), " ".join(b[j1:j2]), lb, top_years)
    order = {"unknown": 0, "variant": 1}
    return sorted(found.values(), key=lambda f: (order[f.kind], f.other == "", -f.uses, f.find))


def read_labels(corrected: Path = CORRECTED) -> list[Label]:
    out = []
    for path in sorted(corrected.glob("questionnaire_*.csv")):
        year = int(path.stem.rsplit("_", 1)[-1])
        with open(path, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                code = r["expenditure_code"] or r["code"] or r["section"]
                out.append(Label(year, f"{r['kind']} {code}", r["description"]))
    return out


def write_report(findings: list[Finding], path: Path = REPORT) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(COLUMNS)
        for x in findings:
            w.writerow(
                [
                    x.kind,
                    x.find,
                    x.other,
                    x.uses,
                    len(x.codes),
                    years_text(x.years),
                    years_text(x.other_years),
                    min(x.examples, key=lambda s: (len(s), s)),
                ]
            )


def _lexicon() -> Lexicon | None:
    try:
        from .spelling import hazm_lexicon

        return hazm_lexicon()
    except SystemExit:  # hazm is not installed
        return None


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(
        prog="python -m hiesir_codebook.correction.check", description=__doc__.split("\n")[0]
    )
    ap.add_argument("--corrected", type=Path, default=CORRECTED)
    ap.add_argument("--out", type=Path, default=REPORT)
    args = ap.parse_args(argv)
    lex = _lexicon()
    findings = check(read_labels(args.corrected), lex)
    write_report(findings, args.out)
    kinds = Counter(f.kind for f in findings)
    with_other = sum(1 for f in findings if f.kind == "unknown" and f.other)
    note = "" if lex is not None else " (no hazm: unknown words not checked)"
    print(
        f"label check -> {args.out.as_posix()}: {kinds['unknown']} unknown words "
        f"({with_other} written otherwise in other years), {kinds['variant']} variants across years{note}"
    )


if __name__ == "__main__":
    main()
