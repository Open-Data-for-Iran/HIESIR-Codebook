"""Correction step 5: the spelling of each description.

After the structure (:mod:`.corrections`, step 1), the canonical wording
(:mod:`.canonical`, step 2), the house style (:mod:`.rules`, step 3) and the
automatic fixes from hazm's word list (:mod:`.autocorrect`, step 4),
``curated/2_corrected/spelling.csv`` fixes the
spellings that recur across rows and years and that hazm cannot settle
(typos, glued words, missing ZWNJs, compounds), applied to every description
in file order.  Its ``text`` rows fix letters inside words (تزئین -> تزیین)
and run earlier, with the house style; where a ``word`` row matches, the
automatic fixes leave that stretch of the label to it.

========== ===================================================================
find       the wrong form (may be several words), as it reads after the
           house style; ZWNJs are ignored (شدهباشد finds شده‌باشد)
replace    the right form
match      ``word``: only as whole words (not inside a longer word);
           ``text``: anywhere in the label
years      empty for all years, else years and ranges: ``1386``,
           ``1383-1385``, ``1383-1385 1390``
reason     why
========== ===================================================================
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

from .. import CURATED_CORRECTED, csv_io
from ..utils import ZWNJ, parse_years

LABELS = CURATED_CORRECTED / "spelling.csv"
# a letter or digit of a word (Arabic-script letters, not punctuation such as "،")
_WORD_CHAR = f"[ء-ٟٮ-ۓە۰-۹{ZWNJ}A-Za-z0-9]"


@dataclass
class LabelFix:
    find: str
    replace: str
    match: str  # "word" (whole words only) | "text" (anywhere)
    years: frozenset[int] | None  # None = all years
    reason: str

    @cached_property
    def pattern(self) -> re.Pattern:
        # blind to ZWNJs: a fix for شدهباشد also finds شده‌باشد, since where the
        # PDF shows a ZWNJ the extractor keeps it and a fix should still apply
        p = f"{ZWNJ}?".join(re.escape(ch) for ch in self.find.replace(ZWNJ, ""))
        if self.match == "word":
            edge = _WORD_CHAR  # letters and digits, not "،" or "؛"
            p = f"(?<!{edge}){p}(?!{edge})"
        return re.compile(p)


def load_label_fixes(path: Path = LABELS) -> list[LabelFix]:
    if not path.exists():
        return []
    out = [
        LabelFix(r["find"], r["replace"], r["match"] or "word", parse_years(r["years"]), r["reason"])
        for r in csv_io.read(path)
    ]
    for fx in out:
        if fx.match not in ("word", "text"):
            raise ValueError(f"{path}: match must be 'word' or 'text', got {fx.match!r} ({fx.find})")
        if not fx.find or not fx.reason.strip():
            raise ValueError(f"{path}: every row needs find and reason ({fx.find})")
    return out


def fix_label(text: str, year: int, fixes: list[LabelFix], hits: dict[str, int] | None = None) -> str:
    """Apply the label fixes for ``year`` to one description, in order;
    ``hits`` counts the descriptions each fix matched."""
    bare = text.replace(ZWNJ, "")
    for fx in fixes:
        if fx.years is not None and year not in fx.years:
            continue
        # the substring test is a cheap filter before the regex
        if fx.find.replace(ZWNJ, "") not in bare:
            continue
        new, n = fx.pattern.subn(fx.replace, text)
        if n and hits is not None:
            hits[fx.find] = hits.get(fx.find, 0) + 1
        if new != text:
            text, bare = new, new.replace(ZWNJ, "")
    return text
