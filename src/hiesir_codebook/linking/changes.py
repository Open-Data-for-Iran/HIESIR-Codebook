"""Matching, stage 2: the changes between chains.

Reads ``output/3_items/chains.csv`` (stage 1).  A change is what happened to
an item between two years: it joins a *set* of earlier chains to a *set* of
later chains, and its shape gives its ``type``:

========== ======== =========================================================
type       shape    meaning
========== ======== =========================================================
same       1 -> 1   the same code with a changed label
recoded    1 -> 1   the same item under a new code
merged     n -> 1   several items combined into one
split      1 -> n   one item divided into several
regrouped  n -> m   items reorganised (only from curated decisions so far)
========== ======== =========================================================

For 1 -> 1 changes ``detail`` says how the label changed: ``minor``
(wording only), ``label_broadened``, ``label_narrowed``, ``label_reworded``,
or empty when the label is the same.

All changes share one table (``output/3_items/changes.csv``, decided in
``curated/3_items/changes.csv``), and the type says what each does:

* ``same`` and ``recoded`` (always 1 -> 1) are *continuing* changes: the
  chains they join form one series (stage 3);
* ``merged``, ``split`` and ``regrouped`` are *breaking* changes: they end
  series and start others.

Suggestions and results are kept apart.  ``output/3_items/suggested/changes.csv``
holds every change the code found, as it found it, with who decided it and
how (``open``: not yet); ``output/3_items/changes.csv`` holds only the final
ones: decided by the code or in ``curated/``, and not rejected.  The two
share ids (``L0001``).

They are found together, since a merge is found by extending a continuing
change.  A chain continues through at most one change each way, and a chain
that goes into a merge, split or regrouping (without also continuing on its
other side) has no continuing change onward from it; ``conflicts`` reports
any breach.

How changes are found, year by year
-----------------------------------
1. consecutive chains of the same code whose labels are related: ``same``;
2. a chain that ends and a chain that starts the next year, in the same
   section and with similar labels, or in another section with the same
   label, is ``recoded`` (best matches first);
3. an item for all providers that is now asked as a public / private pair
   (دولتی / خصوصی, G / NG) is ``split`` into the pair;
4. a chain that ends while its label is contained in a chain that continues
   another one is ``merged`` into it; so are the items of a code group that
   vanish when its "سایر X" (other X) item becomes "X" (1390: 21-inch TVs +
   other TVs -> all TVs);
5. a chain that starts with a label that was part of a chain of the year
   before is ``split`` from it.

When the new label of a code is unrelated, the code was reused for another
item: that is *no* change.  These pairs are listed in
``reports/code_reuse.csv`` for review.  Chains more than ``MAX_GAP``
questionnaires apart are not related.

Verification
------------
A 1 -> 1 change is *definite* (``decided_by`` ``code``) when both
labels carry the same content words: only punctuation, the conjunction
(، / و), word order, spacing, generic words (انواع، اقسام) or "etc." markers
(و نظایر آن، و ...، غیره) differ.  Every other 1 -> 1 change, and every merge,
split or regrouping, needs a human decision.

Decisions are kept in ``curated/3_items/changes.csv``, one row per change:

============ ================================================================
from_chains  the earlier chains, ids separated by spaces
to_chains    the later chains
decision     ``confirm``: the change is right as found
             ``reject``: the chains are not related this way
             ``amend``: right chains, but use ``type``/``detail``
             ``add``: a change the code did not find (e.g. a regrouping)
type         for ``amend`` and ``add``
detail       for ``amend`` and ``add`` (may be empty)
note         why
agent        who decided (the person or the AI model and its effort)
============ ================================================================

To correct the chains of a change, reject it and add the right one.  The
output records each decision in ``verified`` (``confirmed``, ``rejected``,
``amended``, ``added``); a decided change no longer needs verification.
Rejected and open changes are only in ``suggested/``, where the decision
on each suggestion stays visible.  A decision whose change was not found (or, for ``add``,
already exists or names unknown chains) is reported as stale.

The rows that do what the code would not do on its own come first, in
the order of :data:`DECISION_ORDER` (``add``, ``reject``, ``amend``), and
the confirmations last; inside each block the rows follow the chain ids
(:func:`decision_order`).
"""

from __future__ import annotations

import difflib
import itertools
from collections import Counter
from dataclasses import dataclass, field, replace
from functools import cache
from pathlib import Path

from .. import CURATED_ITEMS, ITEMS, REPORTS, csv_io
from ..usage import CODE_USAGE, Occurrence, load_occurrence
from ..utils import loose_key, words
from .chains import Chain, read_chains
from .compare import MAX_GAP, YEARS, compare, contained, is_etc, relate, split_qualifier

DECISIONS = CURATED_ITEMS / "changes.csv"
CONTINUING = ("same", "recoded")  # the series continues
BREAKING = ("merged", "split", "regrouped")  # series end and others start
TYPES = CONTINUING + BREAKING
DECISION_TYPES = ("confirm", "reject", "amend", "add")
DECISION_ORDER = ("add", "reject", "amend", "confirm")  # the order of the blocks in curated/
VERIFIED = {"confirm": "confirmed", "reject": "rejected", "amend": "amended", "add": "added"}
DETAILS = {
    "same": "",
    "minor": "minor",
    "broadened": "label_broadened",
    "narrowed": "label_narrowed",
    "reworded": "label_reworded",
}
CONTINUES = ("same", "minor", "broadened", "narrowed", "reworded")
DECIDED_BY = ("code", "curated", "open")


def decision_order(rows: list[dict[str, str]], key: tuple[str, ...]) -> list[dict[str, str]]:
    """Curated decision rows in their order: the blocks of
    :data:`DECISION_ORDER` (what the code would not do on its own on top),
    and inside each block by the ``key`` columns (the ids it decides on)."""
    return sorted(rows, key=lambda r: (DECISION_ORDER.index(r["decision"]), *(r[k] for k in key)))


def decided_by(needs_verification: bool, verified: str) -> str:
    """Who decided a change: ``curated`` (a row in ``curated/``;
    ``verified`` says how), ``code`` (found and sure without one) or
    ``open`` (found, not sure, not decided yet)."""
    if verified:
        return "curated"
    return "open" if needs_verification else "code"


# --- definite label changes ---------------------------------------------------


def _content(text: str) -> tuple[list[str], str]:
    base, provider = split_qualifier(text)
    return [w for w in words(base) if not is_etc(w)], provider


def definite(old: str, new: str) -> bool:
    """Do the two labels carry the same content words?  True when only
    punctuation, the conjunction, word order, spacing, generic words or
    "etc." markers differ: "جگر، دل، قلوه" / "جگر، دل و قلوه"."""
    (a, pa), (b, pb) = _content(old), _content(new)
    return pa == pb and (Counter(a) == Counter(b) or "".join(a) == "".join(b))


# --- changes ------------------------------------------------------------------


@dataclass
class Change:
    sources: list[Chain]
    targets: list[Chain]
    type: str
    detail: str = ""
    score: float | None = None
    needs_verification: bool = True
    verified: str = ""
    note: str = ""
    id: str = ""
    at: int | None = None  # the year of the change, when not the targets' first year
    found: Change | None = None  # as the code found it, before any decision (None: added)

    @property
    def key(self) -> tuple[frozenset[str], frozenset[str]]:
        return frozenset(c.id for c in self.sources), frozenset(c.id for c in self.targets)

    @property
    def year(self) -> int:
        return self.at if self.at is not None else min(c.years[0] for c in self.targets)

    @property
    def section(self) -> int:
        return self.sources[0].section

    @property
    def is_continuing(self) -> bool:
        """A 1 -> 1 continuation (same item), as opposed to a merge, split or regrouping."""
        return self.type in CONTINUING

    @property
    def rejected(self) -> bool:
        return self.verified == "rejected"

    @property
    def decided_by(self) -> str:
        return decided_by(self.needs_verification, self.verified)

    @property
    def final(self) -> bool:
        """In the results: decided (by the code or in ``curated/``) and not rejected."""
        return not self.rejected and self.decided_by != "open"

    def reshape(self) -> None:
        """Name the change after its shape once chains were added to it."""
        n, m = len(self.sources), len(self.targets)
        if n > 1 or m > 1:
            self.type = "regrouped" if n > 1 and m > 1 else ("merged" if n > 1 else "split")
            self.detail, self.needs_verification = "", True


def _one_to_one(a: Chain, b: Chain, type_: str, rel) -> Change:
    """A 1 -> 1 change; definite when the labels carry the same content."""
    if rel.kind != "same" and definite(a.text, b.text):
        return Change([a], [b], type_, "minor", rel.score, needs_verification=False)
    return Change([a], [b], type_, DETAILS[rel.kind], rel.score, needs_verification=rel.kind != "same")


def _consecutive(chains: list[Chain], years: list[int], max_gap: int):
    """(earlier chain, next chain of the same code, comparison of their labels)."""
    by_code: dict[str, list[Chain]] = {}
    for c in chains:
        by_code.setdefault(c.code, []).append(c)
    for cs in by_code.values():
        cs.sort(key=lambda c: c.years[0])
        for a, b in itertools.pairwise(cs):
            if years.index(b.years[0]) - years.index(a.years[-1]) <= max_gap + 1:  # not too far apart
                yield a, b, relate(a.text, b.text)


def code_reuse(
    chains: list[Chain], years: list[int] = YEARS, max_gap: int = MAX_GAP
) -> list[tuple[Chain, Chain, float]]:
    """Consecutive chains of one code whose labels are unrelated: the code was
    reused for another item, so the chains are *not* related."""
    return [
        (a, b, rel.score) for a, b, rel in _consecutive(chains, years, max_gap) if rel.kind == "different"
    ]


@dataclass
class _Year:
    """The chains that end before and start in one questionnaire year."""

    prev: int  # the questionnaire before this one
    ending: list[Chain]  # last asked within MAX_GAP questionnaires, not related yet
    starting: list[Chain]  # first asked this year, not related yet
    continuing: list[Chain]  # asked, with the same label, the year before and this year
    one_to_one: list[Change] = field(default_factory=list)

    def just_ended(self) -> list[Chain]:
        """Merges and splits only involve chains last asked the year before."""
        return [c for c in self.ending if c.years[-1] == self.prev]

    @property
    def index(self) -> dict[str, list[Chain]]:
        """Continuing chains by their content words, to find candidates fast."""
        if not hasattr(self, "_index"):
            self._index: dict[str, list[Chain]] = {}
            for c in self.continuing:
                for w in _keywords(c.text):
                    self._index.setdefault(w, []).append(c)
        return self._index

    def continuing_like(self, c: Chain) -> list[Chain]:
        """Continuing chains of ``c``'s section that share a content word with it."""
        found = {x.id: x for w in _keywords(c.text) for x in self.index.get(w, ())}
        found.update({x.id: x for x in self.by_section.get(c.section, ()) if _share_words(c.text, x.text)})
        return [x for x in found.values() if x.id != c.id]

    @property
    def by_section(self) -> dict[int, list[Chain]]:
        if not hasattr(self, "_by_section"):
            self._by_section: dict[int, list[Chain]] = {}
            for c in self.continuing:
                self._by_section.setdefault(c.section, []).append(c)
        return self._by_section


# generic words that say little about which item a label names
_GENERIC = frozenset(["سایر", "کلیه", "هزینه", "هزینههای", "خرید", "اجرت", "تهیه", "انواع", "شامل", "مربوط"])


@cache
def _keywords(text: str) -> frozenset[str]:
    return frozenset(w for w in words(text) if not is_etc(w) and w not in _GENERIC and len(w) > 1)


@cache
def _share_words(a: str, b: str) -> bool:
    """A cheap test before a full comparison: do the labels share a content
    word, also inside a glued token ("چاقوجیبی" / "چاقو جیبی")?"""
    ka, kb = _keywords(a), _keywords(b)
    if ka & kb:
        return True
    ja, jb = loose_key(a), loose_key(b)
    return any(w in jb for w in ka if len(w) > 3) or any(w in ja for w in kb if len(w) > 3)


def find_changes(chains: list[Chain], years: list[int] = YEARS, max_gap: int = MAX_GAP) -> list[Change]:
    chains = sorted(chains, key=lambda c: c.id)  # the result must not depend on the input order
    changes = [
        _one_to_one(a, b, "same", rel)
        for a, b, rel in _consecutive(chains, years, max_gap)
        if rel.kind != "different"
    ]
    has_out = {c.id for r in changes for c in r.sources}
    has_in = {c.id for r in changes for c in r.targets}
    for yi in range(1, len(years)):
        year = years[yi]
        window = set(years[max(0, yi - max_gap - 1) : yi])
        prev = years[yi - 1]
        y = _Year(
            prev,
            [c for c in chains if c.years[-1] in window and c.id not in has_out],
            [c for c in chains if c.years[0] == year and c.id not in has_in],
            [c for c in chains if prev in c.years and year in c.years],
        )
        new = _provider_splits(y) + _recodes(y)
        y.one_to_one = [r for r in changes if r.year == year and len(r.sources) == len(r.targets) == 1]
        y.one_to_one += [r for r in new if len(r.targets) == 1]
        new += _merges(y)
        new += _splits(y)
        for r in new:
            r.at = year
        changes += new
        for r in new + y.one_to_one:
            has_out.update(c.id for c in r.sources)
            has_in.update(c.id for c in r.targets)
    return changes


def _best_first(cands):
    """Greedy assignment: highest score first, each chain used once."""
    used: set[str] = set()
    for score, a, b, *rest in sorted(cands, key=lambda c: (-c[0], c[1].id, c[2].id)):
        if a.id in used or b.id in used:
            continue
        used.update((a.id, b.id))
        yield (score, a, b, *rest)


def _provider_splits(y: _Year) -> list[Change]:
    """An item for all providers now asked as a public / private pair."""
    pairs: dict[tuple[int, str], dict[str, Chain]] = {}
    for c in y.starting:
        base, provider = split_qualifier(c.text)
        if provider:
            pairs.setdefault((c.section, loose_key(base)), {})[provider] = c
    cands = []
    for (section, _), pair in pairs.items():
        if set(pair) != {"public", "private"}:
            continue
        base = split_qualifier(pair["public"].text)[0]
        for e in y.ending:
            if e.section == section and not split_qualifier(e.text)[1]:
                rel = compare(e.text, base)
                if rel.kind in CONTINUES and rel.score >= 0.5:
                    cands.append((rel.score, e, pair["public"], pair["private"]))
    out = []
    for score, e, pub, priv in _best_first(cands):
        if priv in y.starting:
            out.append(Change([e], [pub, priv], "split", "", score))
            y.ending.remove(e)
            y.starting.remove(pub)
            y.starting.remove(priv)
    return out


def _recodes(y: _Year) -> list[Change]:
    """A chain that ends and one that starts with a similar label, new code."""
    cands = []
    keys = {c.id: loose_key(c.text) for c in y.ending + y.starting}
    for e in y.ending:
        for s in y.starting:
            if e.code == s.code:
                continue
            # another section only with the same label (رفتگر: 056215 in 5 -> 044418 in 4)
            if e.section != s.section and keys[e.id] != keys[s.id]:
                continue
            # cheap upper bound on the similarity before the full comparison
            if difflib.SequenceMatcher(None, keys[e.id], keys[s.id]).quick_ratio() < 0.5:
                continue
            rel = relate(e.text, s.text)
            if rel.kind in ("same", "minor", "broadened", "narrowed") and rel.score >= 0.5:
                cands.append((rel.score, e, s, rel))
    out = []
    for _, e, s, rel in _best_first(cands):
        out.append(_one_to_one(e, s, "recoded", rel))
        y.ending.remove(e)
        y.starting.remove(s)
    return out


def _absorbs(r: Change, t: Chain):
    """Does change ``r``'s target absorb the ending chain ``t``?  Returns a
    score or None."""
    src, tgt = r.sources[0], r.targets[0]
    # the target may have moved to another section (061214: 6 -> 13 in 1395)
    if t.section not in (src.section, tgt.section) or not _share_words(t.text, tgt.text):
        return None
    rel = contained(t.text, tgt.text)
    if rel is not None:
        return rel.score
    # a collapsed group: "سایر X" -> "X" while related items of the group vanish
    if "سایر" in words(src.text) and "سایر" not in words(tgt.text) and t.code[:-1] == src.code[:-1]:
        rel = relate(t.text, tgt.text)
        if rel.kind != "different" and rel.old_kept >= 0.5:
            return rel.score
    return None


def _merges(y: _Year) -> list[Change]:
    """Ending chains whose label lives on in the target of a 1 -> 1 change,
    or in a chain that goes on with its label unchanged (which then appears
    on both sides: it continues and took in the ending chain)."""
    best: dict[str, tuple[float, Change | Chain]] = {}
    for t in y.just_ended():
        for r in y.one_to_one:
            score = _absorbs(r, t)
            if score is not None and (t.id not in best or score > best[t.id][0]):
                best[t.id] = (score, r)
        for c in y.continuing_like(t):
            rel = contained(t.text, c.text) if c.section == t.section else None
            if rel is not None and (t.id not in best or rel.score > best[t.id][0]):
                best[t.id] = (rel.score, c)
    out: dict[str, Change] = {}
    for t in list(y.ending):
        if t.id not in best:
            continue
        score, into = best[t.id]
        if isinstance(into, Chain):
            into = out.setdefault(into.id, Change([into], [into], "merged", "", score))
        into.sources.append(t)
        into.reshape()
        y.ending.remove(t)
    return list(out.values())


def _splits(y: _Year) -> list[Change]:
    """Starting chains whose label was part of a chain of the year before."""
    sources: list[tuple[Chain, Change | None]] = [(r.sources[0], r) for r in y.one_to_one]
    sources += [(e, None) for e in y.just_ended()]
    going_on = {c.id for c in y.continuing}
    best: dict[str, tuple[float, Chain, Change | None]] = {}
    for s in y.starting:
        for src, r in sources + [(c, None) for c in y.continuing_like(s)]:
            if src.section != s.section or not _share_words(s.text, src.text):
                continue
            rel = contained(s.text, src.text)
            if rel is not None and (s.id not in best or rel.score > best[s.id][0]):
                best[s.id] = (rel.score, src, r)
    out: dict[str, Change] = {}
    for s in list(y.starting):
        if s.id not in best:
            continue
        score, src, r = best[s.id]
        if r is None:  # a split of its own; a source that goes on is also a target
            targets = [src] if src.id in going_on else []
            r = out.setdefault(src.id, Change([src], targets, "split", "", score))
        r.targets.append(s)
        r.reshape()
        y.starting.remove(s)
    return [r for r in out.values() if r.targets]


# --- curated decisions --------------------------------------------------------


@dataclass
class Decision:
    from_chains: frozenset[str]
    to_chains: frozenset[str]
    decision: str
    type: str
    detail: str
    note: str

    def __str__(self) -> str:
        return f"{' '.join(sorted(self.from_chains))} -> {' '.join(sorted(self.to_chains))} {self.decision}"


def load_decisions(path: Path = DECISIONS) -> list[Decision]:
    """Decisions from ``curated/3_items/changes.csv``."""
    if not path.exists():
        return []
    out = [
        Decision(
            frozenset(r["from_chains"].split()),
            frozenset(r["to_chains"].split()),
            r["decision"],
            r["type"],
            r["detail"],
            r["note"],
        )
        for r in csv_io.read(path)
    ]
    for d in out:
        if d.decision not in DECISION_TYPES:
            raise ValueError(f"{path}: unknown decision {d.decision!r} ({d})")
        if d.decision in ("amend", "add") and d.type not in TYPES:
            raise ValueError(f"{path}: {d.decision} needs a type, one of {', '.join(TYPES)} ({d})")
        if not d.from_chains or not d.to_chains:
            raise ValueError(f"{path}: from_chains and to_chains are required ({d})")
        if d.type in CONTINUING and not len(d.from_chains) == len(d.to_chains) == 1:
            raise ValueError(f"{path}: {d.type} joins one chain to one chain ({d})")
    return out


def conflicts(changes: list[Change]) -> list[str]:
    """Breaches of the rule that keeps the changes consistent: a chain
    continues through at most one change each way, and none goes on from (or into) a chain
    that a merge, split or regrouping ends (or starts)."""
    live = [r for r in changes if not r.rejected]
    onward: dict[str, list[Change]] = {}
    into: dict[str, list[Change]] = {}
    for r in live:
        if r.is_continuing:
            onward.setdefault(r.sources[0].id, []).append(r)
            into.setdefault(r.targets[0].id, []).append(r)
    problems = [
        f"{c} has {len(rs)} continuing changes onward: {', '.join(r.id for r in rs)}"
        for c, rs in onward.items()
        if len(rs) > 1
    ]
    problems += [
        f"{c} has {len(rs)} continuing changes into it: {', '.join(r.id for r in rs)}"
        for c, rs in into.items()
        if len(rs) > 1
    ]
    for r in live:
        if r.is_continuing:
            continue
        both = {c.id for c in r.sources} & {c.id for c in r.targets}
        for c in r.sources:
            if c.id not in both and c.id in onward:
                problems.append(
                    f"{c.id} ends in {r.id} ({r.type}) but also continues in {onward[c.id][0].id}"
                )
        for c in r.targets:
            if c.id not in both and c.id in into:
                problems.append(f"{c.id} starts in {r.id} ({r.type}) but also continues {into[c.id][0].id}")
    return problems


def apply_decisions(
    changes: list[Change], decisions: list[Decision], chains: list[Chain]
) -> tuple[list[Change], list[Decision]]:
    """Apply the curated decisions; return the changes and the stale decisions.
    Each change the code found keeps a copy of itself as found in ``found``."""
    for r in changes:
        r.found = replace(r)
    by_key = {r.key: r for r in changes}
    by_id = {c.id: c for c in chains}
    stale = []
    for d in decisions:
        key = (d.from_chains, d.to_chains)
        r = by_key.get(key)
        if d.decision == "add":
            if r is not None or not (d.from_chains | d.to_chains) <= by_id.keys():
                stale.append(d)
                continue
            r = Change(
                [by_id[i] for i in sorted(d.from_chains)], [by_id[i] for i in sorted(d.to_chains)], d.type
            )
            r.detail = d.detail
            # a chain on both sides goes on: the change is when the new chains
            # start, or else the year after the others end
            starting = [c for c in r.targets if c not in r.sources]
            ending = [c for c in r.sources if c not in r.targets] or r.sources
            last = max(c.years[-1] for c in ending)
            after = [y for c in r.targets for y in c.years if y > last]
            if starting:
                r.at = min(c.years[0] for c in starting)
            elif after:
                r.at = min(after)
            changes.append(r)
            by_key[key] = r
        elif r is None:
            stale.append(d)
            continue
        elif d.decision == "amend":
            r.type, r.detail = d.type, d.detail
        r.needs_verification, r.verified, r.note = False, VERIFIED[d.decision], d.note
    return changes, stale


def build_changes(
    chains: list[Chain], decisions: list[Decision], years: list[int] = YEARS, max_gap: int = MAX_GAP
) -> tuple[list[Change], list[Decision]]:
    """Every change the code finds, with the curated decisions applied, in
    order and numbered."""
    changes, stale = apply_decisions(find_changes(chains, years, max_gap), decisions, chains)
    for r in changes:
        r.sources.sort(key=lambda c: (c.code, c.years[0]))
        r.targets.sort(key=lambda c: (c.code, c.years[0]))
    changes.sort(key=lambda r: (r.section, r.sources[0].code, r.sources[0].years[0], r.year))
    for i, r in enumerate(changes, 1):
        r.id = f"L{i:04d}"
    return changes, stale


# --- household evidence -------------------------------------------------------


# the household ratio a scope change allows, relative to the code's group
EXPECTED = {"label_broadened": (0.67, None), "label_narrowed": (None, 1.5)}
STEADY = (0.6, 1.67)
FEW_HOUSEHOLDS = 100


@dataclass
class Evidence:
    year: int  # the year of the change
    before_year: int
    before: int  # households reporting the source codes in before_year
    after: int  # households reporting the target codes in the year of the change
    group: float | None  # the same ratio for the other codes of the group, when there are enough
    ratio: float  # after / before, relative to the group
    verdict: str  # "fits", "does not fit" or "too few"
    expected: tuple[float, float] | None = None  # the ratio a merge or split allows, when it has one

    def __str__(self) -> str:
        g = f" relative to the group (x{self.group})" if self.group is not None else ""
        x = f" (expected x{self.expected[0]}-{self.expected[1]})" if self.expected else ""
        return (
            f"households {self.before_year}: {self.before} -> {self.year}: {self.after}, "
            f"x{self.ratio}{g}{x}; {self.verdict}"
        )


def evidence(
    r: Change,
    occ: Occurrence,
    chains: list[Chain] | None = None,
    min_siblings: int = 2,
    min_households: int = 20,
) -> Evidence | None:
    """Households reporting the source codes in the questionnaire year before
    the change against the target codes in the year of the change.  The ratio
    is taken relative to the other codes of the same groups (code without its
    last two digits), so survey-wide swings cancel out; the verdict says
    whether it fits the change's scope.  None when the table lacks
    either year.

    The table counts households, so one reporting two codes that are merged
    counts once afterwards: after a merge the count lies between the largest
    source and the sum of the sources, and before a split the source lies
    between the largest target and the sum of the targets.

    With ``chains``, a sibling counts only when one chain asks it in both
    years, so a code reused for another item in a redesign (1395 health) does
    not distort the comparison."""
    y = r.year
    before_year = max((v for v in occ if v < y), default=None)
    if y not in occ or before_year is None:
        return None
    src = {int(c.code) for c in r.sources}
    tgt = {int(c.code) for c in r.targets}
    before = sum(occ[before_year].get(c, 0) for c in src)
    after = sum(occ[y].get(c, 0) for c in tgt)
    if not before:
        return None
    groups = {c // 100 for c in src | tgt}
    siblings = [
        c
        for c in occ[y]
        if c // 100 in groups
        and c not in src | tgt
        and occ[y][c] >= min_households
        and occ[before_year].get(c, 0) >= min_households
    ]
    if chains is not None:
        stable = {int(ch.code) for ch in chains if before_year in ch.years and y in ch.years}
        siblings = [c for c in siblings if c in stable]
    g = 1.0
    if len(siblings) >= min_siblings:
        g = sum(occ[y][c] for c in siblings) / sum(occ[before_year][c] for c in siblings)
    group = round(g, 2) if len(siblings) >= min_siblings else None
    ratio = round(after / before / g, 2)
    lo, hi = EXPECTED.get(r.detail, STEADY)
    expected = None
    if len(src) > 1 or len(tgt) > 1:
        largest_src = max(occ[before_year].get(c, 0) for c in src)
        largest_tgt = max(occ[y].get(c, 0) for c in tgt)
        lo = round(STEADY[0] * largest_src / before, 2)
        hi = round(STEADY[1] * after / largest_tgt, 2) if largest_tgt else STEADY[1]
        expected = (lo, hi)
    if max(before, after) < FEW_HOUSEHOLDS:
        verdict = "too few"
    else:
        verdict = "fits" if (lo is None or ratio >= lo) and (hi is None or ratio <= hi) else "does not fit"
    return Evidence(y, before_year, before, after, group, ratio, verdict, expected)


# --- output -------------------------------------------------------------------


def write_changes(changes: list[Change], path: Path) -> None:
    """The final changes among ``changes``: decided and not rejected."""
    _write([r for r in changes if r.final], path)


def write_suggested(changes: list[Change], folder: Path) -> None:
    """What the code found, as it found it, in ``folder/changes.csv``, with who
    decided each and how (``open``: not yet)."""
    _write([r for r in changes if r.found is not None], folder / "changes.csv", suggested=True)


def _write(rows: list[Change], path: Path, suggested: bool = False) -> None:
    """``rows``; with ``suggested``, the type, detail and score as the
    code found them, and no note (the note is a decision's)."""
    head = [
        "change_id",
        "from_chains",
        "to_chains",
        "type",
        "detail",
        "year",
        "score",
        "decided_by",
        "verified",
    ]
    with csv_io.writer(path, [*head, *([] if suggested else ["note"]), "from_text", "to_text"]) as w:
        for r in rows:
            f = r.found if suggested and r.found is not None else r
            w.writerow(
                [
                    r.id,
                    " ".join(c.id for c in r.sources),
                    " ".join(c.id for c in r.targets),
                    f.type,
                    f.detail,
                    r.year,
                    "" if f.score is None else f.score,
                    r.decided_by,
                    r.verified,
                    *([] if suggested else [r.note]),
                    " | ".join(c.text for c in r.sources),
                    " | ".join(c.text for c in r.targets),
                ]
            )


def write_code_reuse(pairs: list[tuple[Chain, Chain, float]], path: Path) -> None:
    header = ["expenditure_code", "from_chain", "to_chain", "score", "from_text", "to_text"]
    with csv_io.writer(path, header) as w:
        for a, b, score in sorted(pairs, key=lambda p: (p[0].code, p[0].years[0])):
            w.writerow([a.code, a.id, b.id, score, a.text, b.text])


def write_evidence(changes: list[Change], chains: list[Chain], occ: Occurrence, path: Path) -> Counter:
    """One row per change with its household evidence; return the verdicts
    of the changes still to verify."""
    todo: Counter = Counter()
    with csv_io.writer(
        path,
        [
            "id",
            "type",
            "detail",
            "year",
            "decided_by",
            "verified",
            "before_year",
            "before",
            "after",
            "group",
            "ratio",
            "verdict",
            "from_text",
            "to_text",
        ],
    ) as w:
        for r in changes:
            e = evidence(r, occ, chains)
            if r.needs_verification:
                todo[e.verdict if e else "no data"] += 1
            w.writerow(
                [r.id, r.type, r.detail, r.year, r.decided_by, r.verified]
                + (
                    [e.before_year, e.before, e.after, "" if e.group is None else e.group, e.ratio, e.verdict]
                    if e
                    else ["", "", "", "", "", "no data"]
                )
                + [" | ".join(c.text for c in r.sources), " | ".join(c.text for c in r.targets)]
            )
    return todo


def main(
    *,
    chains: Path = ITEMS / "chains.csv",
    out: Path = ITEMS / "changes.csv",
    suggested: Path = ITEMS / "suggested",
    decisions: Path = DECISIONS,
    reuse_report: Path = REPORTS / "code_reuse.csv",
    evidence_report: Path = REPORTS / "change_evidence.csv",
    usage: Path = CODE_USAGE,
    max_gap: int = MAX_GAP,
) -> None:
    """Matching stage 2: chains.csv -> output/3_items/changes.csv.

    Parameters
    ----------
    chains
        The chains of stage 1.
    out
        Where the changes go.
    suggested
        Where the code's suggestions go, before the decisions.
    decisions
        The curated decisions on changes.
    reuse_report
        Codes reused for an unrelated item.
    evidence_report
        Household evidence for the changes still to verify.
    usage
        The code usage table (skipped when missing).
    max_gap
        Questionnaires a change may skip.
    """
    chain_list = read_chains(chains)
    changes, stale = build_changes(chain_list, load_decisions(decisions), YEARS, max_gap)
    write_changes(changes, out)
    write_suggested(changes, suggested)
    linked = {(a.id, b.id) for r in changes for a in r.sources for b in r.targets}
    reused = [p for p in code_reuse(chain_list, YEARS, max_gap) if (p[0].id, p[1].id) not in linked]
    write_code_reuse(reused, reuse_report)
    for name, rs in (
        ("changes that continue an item (same, recoded)", [r for r in changes if r.is_continuing]),
        ("merges, splits and regroupings", [r for r in changes if not r.is_continuing]),
    ):
        kinds = Counter(r.type for r in rs)
        verified = Counter(r.verified for r in rs if r.verified)
        print(
            f"{len(rs)} {name} ("
            + ", ".join(f"{k} {v}" for k, v in kinds.most_common())
            + f"): decided by the code {sum(r.decided_by == 'code' for r in rs)}, "
            + f"in {decisions.as_posix()}: "
            + (", ".join(f"{k} {v}" for k, v in verified.items()) or "0")
            + f", open: {sum(r.decided_by == 'open' for r in rs)}"
            + f"; final {sum(r.final for r in rs)}"
        )
    print(f"the code's suggestions, before the decisions -> {suggested.as_posix()}/")
    print(f"code reused for an unrelated item (no change): {len(reused)} -> {reuse_report.as_posix()}")
    if usage.exists():
        # only the years compared: 1382 is no year before 1383 (other codes)
        occ = {y: v for y, v in load_occurrence(usage).items() if y in YEARS}
        todo_ev = write_evidence(changes, chain_list, occ, evidence_report)
        print(
            "household evidence for those still to verify: "
            + (", ".join(f"{k} {v}" for k, v in todo_ev.most_common()) or "none")
            + f" -> {evidence_report.as_posix()}"
        )
    for d in stale:
        print(f"stale decision: {d}")
    for problem in conflicts(changes):
        print(f"changes disagree: {problem}")
