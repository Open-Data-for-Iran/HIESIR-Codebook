"""Comparing questionnaire item descriptions, shared by the matching stages.

:func:`compare` tells how description ``new`` relates to ``old``:

========== ==================================================================
same       equal once spacing, ZWNJ, punctuation, hamza and digits are ignored
minor      near-identical wording (typo, و ↔ ،, plural form)
broadened  the new text keeps the old one and adds to it
narrowed   the new text is a part of the old one
reworded   clearly related, but rephrased (both still name the same thing)
different  unrelated text
========== ==================================================================

Provider qualifiers
-------------------
Many health services are asked twice, once per kind of provider:

- 1383-1394: "... (دولتی)" (public) and "... (خصوصی)" (private);
- from 1395: "... G" for centres owned by the medical universities and
  "... NG" for all other providers (social security, armed forces, private,
  charity ...), as defined at the foot of each health page.

:func:`relate` leaves the qualifier out of the comparison and treats items
for different providers as ``different``: دولتی matches G and خصوصی NG
(note that NG covers more than خصوصی did).
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from pathlib import Path

from .. import csv_io
from ..utils import loose_key, words

# questionnaires with COICOP-based codes (the 1401 PDF is not a questionnaire)
YEARS = [*range(1383, 1401), 1402, 1403]
MAX_GAP = 2  # how many questionnaires a series may skip

#: provider qualifier at the end of a description
QUALIFIER_RE = re.compile(r"\s*\((دولتی|خصوصی)\)$|\s+(N?G)$")
PROVIDERS = {"دولتی": "public", "G": "public", "خصوصی": "private", "NG": "private"}


def split_qualifier(text: str) -> tuple[str, str]:
    """Description without its provider qualifier, and the provider:
    'خدمات آمبولانس G' -> ('خدمات آمبولانس', 'public'),
    'ویزیت روانپزشک (خصوصی)' -> ('ویزیت روانپزشک', 'private'),
    no qualifier -> (text, '')."""
    m = QUALIFIER_RE.search(text)
    if m is None:
        return text, ""
    return text[: m.start()], PROVIDERS[m.group(1) or m.group(2)]


# --- comparing descriptions ---------------------------------------------------


@dataclass(frozen=True)
class Relation:
    kind: str
    score: float  # 0-1, higher = more similar
    old_kept: float = 0.0  # share of the old text's words found in the new text
    new_kept: float = 0.0  # share of the new text's words found in the old text


def _found(w: str, b: list[str], b_joined: str) -> int | None:
    """Index of the word in ``b`` matching ``w`` (equal or one letter apart),
    -1 if ``w`` only appears inside the joined text ("قهوه جوش" in
    "قهوه‌جوش"), None if absent.  Short words must match exactly: "شیر"
    (milk) is not found inside "شیرینی" (sweets)."""
    if w in b:
        return b.index(w)
    if len(w) <= 3:
        return None
    best, best_r = None, 0.75 - 1e-9
    for i, v in enumerate(b):
        # cheap upper bounds first: the length ratio and quick_ratio
        if 2 * min(len(w), len(v)) / (len(w) + len(v)) <= best_r:
            continue
        m = difflib.SequenceMatcher(None, w, v)
        if m.quick_ratio() <= best_r:
            continue
        r = m.ratio()
        if r > best_r:
            best, best_r = i, r
    if best is not None:
        return best
    return -1 if w in b_joined else None


def _overlap(a: list[str], b: list[str], b_joined: str) -> int:
    """Number of words of ``a`` found in ``b`` (each word of ``b`` used once).
    Two words of ``a`` that ``b`` writes as one count as two found ("ظرف شویی"
    / "ظرفشویی"), however short."""
    left = list(b)
    n = 0
    k = 0
    while k < len(a):
        if k + 1 < len(a) and a[k] + a[k + 1] in left:
            left.remove(a[k] + a[k + 1])
            n += 2
            k += 2
            continue
        i = _found(a[k], left, b_joined)
        if i is not None:
            n += 1
            if i >= 0:
                left.pop(i)
        k += 1
    return n


#: words that do not change what an item covers ("and the like", "kinds of"),
#: in the form words() returns them (hamza and madda dropped: آن -> ان)
ETC_WORDS = frozenset(["نظایر", "ان", "غیره", "امثال", "اینها", "مانند", "اقسام"])


_ETC_RE = re.compile(f"و?(?:{'|'.join(sorted(ETC_WORDS, key=len, reverse=True))})+")


def is_etc(w: str) -> bool:
    """An "etc." word, also when glued: "نظایر", "ان", "ونظایران" (و نظایر آن)."""
    return bool(_ETC_RE.fullmatch(w))


def _missing(a: list[str], b: list[str], b_joined: str) -> list[str]:
    """Content words of ``a`` not found in ``b`` ("etc." words ignored)."""
    left = list(b)
    out = []
    for w in a:
        if is_etc(w):
            continue
        i = _found(w, left, b_joined)
        if i is None:
            out.append(w)
        elif i >= 0:
            left.pop(i)
    return out


# words that open many descriptions without saying what the item is
_GENERIC_HEADS = frozenset(["سایر", "کلیه", "هزینه", "هزینهها", "هزینههای", "خرید", "اجرت", "تهیه"])


def _head(ws: list[str]) -> str | None:
    """The head noun: Persian descriptions name the thing first
    ("آبگرمکن گازی", "کولر گازی"), after generic words like سایر or هزینه."""
    return next((w for w in ws if w not in _GENERIC_HEADS), ws[0] if ws else None)


def compare(old: str, new: str) -> Relation:
    """How does description ``new`` relate to ``old``?

    Words added or dropped decide first (``broadened`` / ``narrowed``); only
    when content words change on both sides do near-identical texts count as
    ``minor`` (a respelled word, a typo)."""
    ka, kb = loose_key(old), loose_key(new)
    if ka == kb:
        return Relation("same", 1.0, 1.0, 1.0)
    char = difflib.SequenceMatcher(None, ka, kb).ratio()
    wa, wb = words(old), words(new)
    old_kept = _overlap(wa, wb, kb) / max(1, len(wa))
    new_kept = _overlap(wb, wa, ka) / max(1, len(wb))
    m = old_kept * len(wa)
    jaccard = m / max(1, len(wa) + len(wb) - m)
    score = round(max(char, jaccard), 3)

    def rel(kind: str) -> Relation:
        return Relation(kind, score, round(old_kept, 3), round(new_kept, 3))

    # content words first: a whole word added or dropped changes what the item
    # covers, however similar the rest ("گاو و گوساله" -> "گاو و گوساله، شتر")
    removed, added = _missing(wa, wb, kb), _missing(wb, wa, ka)
    if not removed and not added:
        return rel("minor")  # spelling, spacing, punctuation, "etc."
    if added and not removed:
        return rel("broadened")
    if removed and not added:
        return rel("narrowed")
    if char >= 0.9 or jaccard >= 0.85:
        return rel("minor")
    if old_kept >= 0.85 and len(wb) > len(wa):
        return rel("broadened")
    if new_kept >= 0.85 and len(wa) > len(wb):
        return rel("narrowed")
    # rephrased, as long as both still name the same thing: sharing only a
    # qualifier ("گازی" in آبگرمکن گازی / کولرگازی) is not enough
    ha, hb = _head(wa), _head(wb)
    same_head = (ha is not None and _found(ha, wb, kb) is not None) or (
        hb is not None and _found(hb, wa, ka) is not None
    )
    if same_head and (jaccard >= 0.25 or max(old_kept, new_kept) >= 0.5 or char >= 0.6):
        return rel("reworded")
    return rel("different")


def relate(old: str, new: str) -> Relation:
    """:func:`compare` for item texts that may carry a provider qualifier:
    the providers must agree and the qualifiers are left out of the comparison."""
    (a, qa), (b, qb) = split_qualifier(old), split_qualifier(new)
    if qa != qb:
        return Relation("different", 0.0)
    return compare(a, b)


def contained(part: str, whole: str) -> Relation | None:
    """``part`` is (mostly) contained in ``whole``: the basis of merges and splits.
    A provider-specific part may be contained in an item for all providers."""
    (a, qa), (b, qb) = split_qualifier(part), split_qualifier(whole)
    rel = compare(a, b) if qa == qb or not qb else Relation("different", 0.0)
    if rel.kind != "different" and rel.old_kept >= 0.8 and len(words(part)) >= 1:
        return rel
    return None


# --- data ---------------------------------------------------------------------


@dataclass
class Item:
    year: int
    section: int
    code: str  # expenditure code, e.g. "011111"
    text: str


def load_year(year: int, source: Path) -> list[Item]:
    return [
        Item(year, int(r["section"]), r["expenditure_code"], r["description"])
        for r in csv_io.read(source / f"questionnaire_{year}.csv")
        if r["kind"] == "item" and r["expenditure_code"]
    ]
