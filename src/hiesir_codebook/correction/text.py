"""Persian text as the correction steps read it: what a word is, and the folds
that make two spellings of it one key.

Each fold is one table of characters, applied the same way to a Python string
(``word_key("مؤسسات")``) and to a polars column (``word_key.expr("word")``),
so a lookup in Python and a join in polars always agree.  From the strictest to
the loosest:

=============== ==============================================================
fold            what it makes one
=============== ==============================================================
``letters``     the Arabic forms of ی and ک, and hamza (ئ أ إ ؤ ء): وسائل /
                وسایل, موسسات / مؤسسات; ZWNJs stay
``word_key``    that, and ZWNJs: the key of a word in hazm's list
``label_key``   that, and spaces, tatweel, tanwin, ة, the Latin comma, an ellipsis of
                any length, the separator of a list (``،`` or ``و``, as ``و``) and "and
                so on" (``و ...``, ``غیره``): the key of a group of labels
                (:mod:`.canonical`)
=============== ==============================================================

آ is never folded into ا: آب is not اب.
"""

from __future__ import annotations

import re

import polars as pl

from ..utils import ZWNJ

# --- words ------------------------------------------------------------------------

#: the characters of a Persian word: Arabic-script letters, and the ZWNJs inside it
LETTER = f"ء-يٹ-ۓ{ZWNJ}"
#: a Persian word
WORD = re.compile(f"[{LETTER}]+")
#: a stretch of words and the spaces between them, no marks
PHRASE = re.compile(f"[{LETTER} ]+")
#: a letter or digit: what a whole-word match may not touch (punctuation such as "،" may)
EDGE = f"[ء-ٟٮ-ۓە۰-۹{ZWNJ}A-Za-z0-9]"


def whole(pattern: str) -> str:
    """``pattern`` as whole words only: no letter or digit on either side."""
    return f"(?<!{EDGE}){pattern}(?!{EDGE})"


# --- folds ------------------------------------------------------------------------


class Fold:
    """A table of characters to replace (``""``: to drop), for strings and columns."""

    def __init__(self, pairs: dict[str, str]):
        self.pairs = pairs
        self._table = str.maketrans({k: v or None for k, v in pairs.items()})

    def __call__(self, s: str) -> str:
        return s.translate(self._table)

    def expr(self, column: str | pl.Expr) -> pl.Expr:
        col = pl.col(column) if isinstance(column, str) else column
        return col.str.replace_many(list(self.pairs), list(self.pairs.values()))

    def __or__(self, more: dict[str, str]) -> Fold:
        return Fold(self.pairs | more)


letters = Fold({"ي": "ی", "ك": "ک", "ئ": "ی", "أ": "ا", "إ": "ا", "ؤ": "و", "ء": ""})
word_key = letters | {ZWNJ: ""}
_label = word_key | {" ": "", " ": "", "ـ": "", "ة": "ه", ",": "،", "ً": ""}
_DOTS = r"\.+"

# what a label may write in more than one way without saying anything else,
# folded before the letters: (pattern, replacement in Python, in polars); the
# patterns need no lookaround, so polars' regex runs them alike
_PHRASES = (
    # "etc." as a word is an ellipsis
    (r"(^|[\s(،,])غیره($|[\s)،,.])", r"\1...\2", "${1}...${2}"),
    # an ellipsis, with the و or comma before it, says only "and so on": dropped
    (r"[\s،,]*(?:و\s*)?(?:\.\s*){2,}", "", ""),
    # items listed with a comma or with و: one separator, و (with the spaces
    # gone, the key then also equals a glued و: سروصورت / سر و صورت / سر، صورت)
    (r"\s*[،,]\s*(?:و\s+)?", " و ", " و "),
)


def label_key(label: str) -> str:
    """``label`` as its group knows it: the items of a list joined one way (و),
    without "and so on" (``و ...``, ``غیره``), then no spaces or ZWNJs, one
    form of each letter, an ellipsis of any length as one dot: ``لوله‌کشی آب و
    نصب کنتور`` and ``لوله‌کشی آب، نصب کنتور`` are one label."""
    for pattern, repl, _ in _PHRASES:
        label = re.sub(pattern, repl, label)
    return re.sub(_DOTS, ".", _label(label))


def label_key_expr(column: str) -> pl.Expr:
    """:func:`label_key` on a column."""
    col = pl.col(column)
    for pattern, _, repl in _PHRASES:
        col = col.str.replace_all(pattern, repl)
    return _label.expr(col).str.replace_all(_DOTS, ".")


def label_char(ch: str) -> str:
    """One character as :func:`label_key` folds it (``""``: dropped)."""
    return _label.pairs.get(ch, ch)


def bare(s: str) -> str:
    """``s`` without ZWNJs."""
    return s.replace(ZWNJ, "")


def years_text(years) -> str:
    """{1383, 1384, 1385, 1390} -> "1383-1385 1390"."""
    out: list[list[int]] = []
    for y in sorted(years):
        if out and y == out[-1][1] + 1:
            out[-1][1] = y
        else:
            out.append([y, y])
    return " ".join(str(a) if a == b else f"{a}-{b}" for a, b in out)
