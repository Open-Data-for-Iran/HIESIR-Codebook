"""Suggest label fixes for curated/2_corrected/spelling.csv, using hazm as an advisor.

hazm is not a dependency of the project; run this with a temporary install:

    uv run --with hazm python scripts/suggest_labels.py

It normalises every description in output/2_corrected/ with hazm's Normalizer (only
the options that fit the house style: affix spacing, ZWNJ, diacritics,
Unicode variants; no Persian digits, no punctuation restyling), brings the
result back to the house punctuation style, and lists each word-level
change with how many descriptions it affects.  Nothing is applied: review
reports/hazm_suggestions.csv and copy the rows you accept into
curated/2_corrected/spelling.csv.
"""

from __future__ import annotations

import csv
import difflib
import re
from collections import defaultdict

from hazm import Normalizer

from hiesir_codebook import CORRECTED, REPORTS
from hiesir_codebook.correct import load_label_fixes
from hiesir_codebook.utils import tidy_punctuation

OUT = REPORTS / "hazm_suggestions.csv"

normalizer = Normalizer(
    correct_spacing=True,  # ها / های / تر / ترین / می with ZWNJ, spacing
    remove_diacritics=True,  # stray shadda, fatha ...
    remove_specials_chars=False,
    decrease_repeated_chars=False,
    persian_style=False,  # keep our quotes and dots
    persian_numbers=False,  # keep ASCII digits
    unicodes_replacement=True,
    seperate_mi=True,
)


ZWNJ = "‌"
_EDGE = "()[]«»،؛:.!؟"


def trim(find: str, replace: str) -> tuple[str, str]:
    """Drop punctuation both sides share at the edges: 'سیب زمینی،' / 'سیب‌زمینی،'."""
    while find and replace and find[-1] == replace[-1] and find[-1] in _EDGE:
        find, replace = find[:-1], replace[:-1]
    while find and replace and find[0] == replace[0] and find[0] in _EDGE:
        find, replace = find[1:], replace[1:]
    return find.strip(), replace.strip()


def kind(find: str, replace: str) -> str:
    """plural: ها / های attached with a ZWNJ (the standard spelling);
    compound: two words joined with a ZWNJ (optional, a style choice);
    other: anything else (diacritics, letters, spacing)."""
    if find.replace(" ", "").replace(ZWNJ, "") != replace.replace(" ", "").replace(ZWNJ, ""):
        return "other"
    if re.search(f"{ZWNJ}(ها|های|هایی)(?![؀-ۿ])", replace):
        return "plural"
    if ZWNJ in replace:
        return "compound"
    return "other"


def years_text(years: set[int]) -> str:
    """{1383, 1384, 1385, 1390} -> '1383-1385 1390'."""
    ys = sorted(years)
    out, start = [], ys[0]
    for a, b in zip(ys, [*ys[1:], None], strict=True):
        if b is None or b != a + 1:
            out.append(str(start) if start == a else f"{start}-{a}")
            start = b
    return " ".join(out)


def main() -> None:
    labels: dict[str, set[int]] = defaultdict(set)
    for path in sorted(CORRECTED.glob("questionnaire_*.csv")):
        year = int(path.stem.split("_")[1])
        with open(path, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                if r["description"]:
                    labels[r["description"]].add(year)

    known = {fx.find for fx in load_label_fixes()}
    found: dict[tuple[str, str], dict] = {}
    for text, years in labels.items():
        new = tidy_punctuation(normalizer.normalize(text))
        if new == text:
            continue
        a, b = text.split(" "), new.split(" ")
        for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
            if op == "equal":
                continue
            find, replace = trim(" ".join(a[i1:i2]), " ".join(b[j1:j2]))
            if not find or find == replace or find in known:
                continue
            s = found.setdefault((find, replace), {"labels": 0, "years": set(), "example": text})
            s["labels"] += 1
            s["years"] |= years

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["kind", "find", "replace", "labels", "years", "example"])
        rows = sorted(found.items(), key=lambda kv: (kind(*kv[0]), -kv[1]["labels"], kv[0]))
        for (find, replace), s in rows:
            w.writerow(
                [kind(find, replace), find, replace, s["labels"], years_text(s["years"]), s["example"]]
            )
    print(f"{len(found)} suggestions from {len(labels)} distinct labels -> {OUT}")


if __name__ == "__main__":
    main()
