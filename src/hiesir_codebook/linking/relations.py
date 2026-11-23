"""Matching, stage 2: links and relations between chains.

Reads ``output/3_items/chains.csv`` (stage 1).  A relation links a *set*
of earlier chains to a *set* of later chains; its shape gives its kind:

========== ======== =========================================================
relation   shape    meaning
========== ======== =========================================================
same       1 -> 1   the same code with a changed label
recoded    1 -> 1   the same item under a new code
merged     n -> 1   several items combined into one
split      1 -> n   one item divided into several
regrouped  n -> m   items reorganised (only from curated decisions so far)
========== ======== =========================================================

For 1 -> 1 relations ``detail`` says how the label changed: ``minor``
(wording only), ``label_broadened``, ``label_narrowed``, ``label_reworded``,
or empty when the label is the same.

The two families do different jobs and are kept apart:

* a *link* (``same`` or ``recoded``, always 1 -> 1) continues an item: the
  chains it joins form one series (stage 3).  Written to
  ``output/3_items/links.csv``, decided in ``curated/3_items/links.csv``.
* a *relation* (``merged``, ``split``, ``regrouped``) ends series and starts
  others.  Written to ``output/3_items/relations.csv``, decided in
  ``curated/3_items/relations.csv``.

Suggestions and results are kept apart.  ``output/3_items/suggested/``
(``links.csv``, ``relations.csv``) holds every link and relation the code
found, as it found it, with who decided it and how (``open``: not yet);
``output/3_items/links.csv`` and ``relations.csv`` hold only the final
ones: decided by the code or in ``curated/``, and not rejected.  The two
share ids (``L0001``, ``R0001``).

They are found together, since a merge is found by extending a link.  A
chain continues through at most one link each way, and a chain that goes
into a merge, split or regrouping (without also continuing on its other
side) has no link onward from it; ``conflicts`` reports any breach.

How relations are found, year by year
-------------------------------------
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
item: that is *no* relation.  These pairs are listed in
``reports/code_reuse.csv`` for review.  Chains more than ``MAX_GAP``
questionnaires apart are not related.

Verification
------------
A 1 -> 1 relation is *definite* (``decided_by`` ``code``) when both
labels carry the same content words: only punctuation, the conjunction
(، / و), word order, spacing, generic words (انواع، اقسام) or "etc." markers
(و نظایر آن، و ...، غیره) differ.  Every other relation, and every merge,
split or regrouping, needs a human decision.

Decisions are kept in ``curated/3_items/links.csv`` (columns ``from_chain``,
``to_chain``: one chain id each) and ``curated/3_items/relations.csv`` (columns
``from_chains``, ``to_chains``: chain ids separated by spaces), one row per
link or relation:

============ ================================================================
from_chains  the earlier chains (``from_chain`` in links.csv)
to_chains    the later chains (``to_chain`` in links.csv)
decision     ``confirm``: the relation is right as found
             ``reject``: the chains are not related this way
             ``change``: right chains, but use ``relation``/``detail``
             ``add``: a relation the code did not find (e.g. a regrouping)
relation     for ``change`` and ``add``
detail       for ``change`` and ``add`` (may be empty)
note         why
agent        who decided (the person or the AI model and its effort)
============ ================================================================

To change the chains of a relation, reject it and add the right one.  The
output records each decision in ``verified`` (``confirmed``, ``rejected``,
``changed``, ``added``); a decided relation no longer needs verification.
Rejected and open relations are only in ``suggested/``, where the decision
on each suggestion stays visible.  A decision whose relation was not found (or, for ``add``,
already exists or names unknown chains) is reported as stale.
"""

from __future__ import annotations

import difflib
import itertools
from collections import Counter
from dataclasses import dataclass, field, replace
from functools import cache
from pathlib import Path

from .. import CURATED_ITEMS, ITEMS, REPORTS, csv_io
from ..occurrence import OCCURRENCE, Occurrence, load_occurrence
from ..utils import loose_key, words
from .chains import Chain, read_chains
from .compare import MAX_GAP, YEARS, compare, contained, is_etc, relate, split_qualifier

DECISIONS = CURATED_ITEMS / "relations.csv"
LINK_DECISIONS = CURATED_ITEMS / "links.csv"
LINK_KINDS = ("same", "recoded")
GROUP_KINDS = ("merged", "split", "regrouped")
DECISION_KINDS = ("confirm", "reject", "change", "add")
VERIFIED = {"confirm": "confirmed", "reject": "rejected", "change": "changed", "add": "added"}
DETAILS = {
    "same": "",
    "minor": "minor",
    "broadened": "label_broadened",
    "narrowed": "label_narrowed",
    "reworded": "label_reworded",
}
CONTINUES = ("same", "minor", "broadened", "narrowed", "reworded")
DECIDED_BY = ("code", "curated", "open")


def decided_by(needs_verification: bool, verified: str) -> str:
    """Who decided a link or relation: ``curated`` (a row in ``curated/``;
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


# --- relations ----------------------------------------------------------------


@dataclass
class Relation:
    sources: list[Chain]
    targets: list[Chain]
    relation: str
    detail: str = ""
    score: float | None = None
    needs_verification: bool = True
    verified: str = ""
    note: str = ""
    id: str = ""
    at: int | None = None  # the year of the change, when not the targets' first year
    found: Relation | None = None  # as the code found it, before any decision (None: added)

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
    def is_link(self) -> bool:
        """A 1 -> 1 continuation (same item), as opposed to a merge, split or regrouping."""
        return self.relation in LINK_KINDS

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
        """Name the relation after its shape once chains were added to it."""
        n, m = len(self.sources), len(self.targets)
        if n > 1 or m > 1:
            self.relation = "regrouped" if n > 1 and m > 1 else ("merged" if n > 1 else "split")
            self.detail, self.needs_verification = "", True


def _one_to_one(a: Chain, b: Chain, relation: str, rel) -> Relation:
    """A 1 -> 1 relation; definite when the labels carry the same content."""
    if rel.kind != "same" and definite(a.text, b.text):
        return Relation([a], [b], relation, "minor", rel.score, needs_verification=False)
    return Relation([a], [b], relation, DETAILS[rel.kind], rel.score, needs_verification=rel.kind != "same")


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
    one_to_one: list[Relation] = field(default_factory=list)

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


def find_relations(chains: list[Chain], years: list[int] = YEARS, max_gap: int = MAX_GAP) -> list[Relation]:
    chains = sorted(chains, key=lambda c: c.id)  # the result must not depend on the input order
    relations = [
        _one_to_one(a, b, "same", rel)
        for a, b, rel in _consecutive(chains, years, max_gap)
        if rel.kind != "different"
    ]
    has_out = {c.id for r in relations for c in r.sources}
    has_in = {c.id for r in relations for c in r.targets}
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
        y.one_to_one = [r for r in relations if r.year == year and len(r.sources) == len(r.targets) == 1]
        y.one_to_one += [r for r in new if len(r.targets) == 1]
        new += _merges(y)
        new += _splits(y)
        for r in new:
            r.at = year
        relations += new
        for r in new + y.one_to_one:
            has_out.update(c.id for c in r.sources)
            has_in.update(c.id for c in r.targets)
    return relations


def _best_first(cands):
    """Greedy assignment: highest score first, each chain used once."""
    used: set[str] = set()
    for score, a, b, *rest in sorted(cands, key=lambda c: (-c[0], c[1].id, c[2].id)):
        if a.id in used or b.id in used:
            continue
        used.update((a.id, b.id))
        yield (score, a, b, *rest)


def _provider_splits(y: _Year) -> list[Relation]:
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
            out.append(Relation([e], [pub, priv], "split", "", score))
            y.ending.remove(e)
            y.starting.remove(pub)
            y.starting.remove(priv)
    return out


def _recodes(y: _Year) -> list[Relation]:
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


def _absorbs(r: Relation, t: Chain):
    """Does relation ``r``'s target absorb the ending chain ``t``?  Returns a
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


def _merges(y: _Year) -> list[Relation]:
    """Ending chains whose label lives on in the target of a 1 -> 1 relation,
    or in a chain that goes on with its label unchanged (which then appears
    on both sides: it continues and took in the ending chain)."""
    best: dict[str, tuple[float, Relation | Chain]] = {}
    for t in y.just_ended():
        for r in y.one_to_one:
            score = _absorbs(r, t)
            if score is not None and (t.id not in best or score > best[t.id][0]):
                best[t.id] = (score, r)
        for c in y.continuing_like(t):
            rel = contained(t.text, c.text) if c.section == t.section else None
            if rel is not None and (t.id not in best or rel.score > best[t.id][0]):
                best[t.id] = (rel.score, c)
    out: dict[str, Relation] = {}
    for t in list(y.ending):
        if t.id not in best:
            continue
        score, into = best[t.id]
        if isinstance(into, Chain):
            into = out.setdefault(into.id, Relation([into], [into], "merged", "", score))
        into.sources.append(t)
        into.reshape()
        y.ending.remove(t)
    return list(out.values())


def _splits(y: _Year) -> list[Relation]:
    """Starting chains whose label was part of a chain of the year before."""
    sources: list[tuple[Chain, Relation | None]] = [(r.sources[0], r) for r in y.one_to_one]
    sources += [(e, None) for e in y.just_ended()]
    going_on = {c.id for c in y.continuing}
    best: dict[str, tuple[float, Chain, Relation | None]] = {}
    for s in y.starting:
        for src, r in sources + [(c, None) for c in y.continuing_like(s)]:
            if src.section != s.section or not _share_words(s.text, src.text):
                continue
            rel = contained(s.text, src.text)
            if rel is not None and (s.id not in best or rel.score > best[s.id][0]):
                best[s.id] = (rel.score, src, r)
    out: dict[str, Relation] = {}
    for s in list(y.starting):
        if s.id not in best:
            continue
        score, src, r = best[s.id]
        if r is None:  # a split of its own; a source that goes on is also a target
            targets = [src] if src.id in going_on else []
            r = out.setdefault(src.id, Relation([src], targets, "split", "", score))
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
    relation: str
    detail: str
    note: str

    def __str__(self) -> str:
        return f"{' '.join(sorted(self.from_chains))} -> {' '.join(sorted(self.to_chains))} {self.decision}"


def load_decisions(path: Path = DECISIONS, links: bool | None = None) -> list[Decision]:
    """Decisions from ``curated/3_items/relations.csv`` or, with ``links``, from
    ``curated/3_items/links.csv`` (guessed from the header when None)."""
    if not path.exists():
        return []
    if links is None:
        links = "from_chain" in csv_io.columns(path)
    cols = ("from_chain", "to_chain") if links else ("from_chains", "to_chains")
    out = [
        Decision(
            frozenset(r[cols[0]].split()),
            frozenset(r[cols[1]].split()),
            r["decision"],
            r["relation"],
            r["detail"],
            r["note"],
        )
        for r in csv_io.read(path)
    ]
    kinds = LINK_KINDS if links else GROUP_KINDS
    other = "relations.csv" if links else "links.csv"
    for d in out:
        if d.decision not in DECISION_KINDS:
            raise ValueError(f"{path}: unknown decision {d.decision!r} ({d})")
        if d.decision in ("change", "add") and not d.relation:
            raise ValueError(f"{path}: {d.decision} needs a relation ({d})")
        if not d.from_chains or not d.to_chains:
            raise ValueError(f"{path}: {cols[0]} and {cols[1]} are required ({d})")
        if links and not len(d.from_chains) == len(d.to_chains) == 1:
            raise ValueError(f"{path}: a link joins one chain to one chain ({d})")
        if d.decision in ("change", "add") and d.relation not in kinds:
            raise ValueError(f"{path}: {d.relation!r} belongs in {other} ({d})")
    return out


def conflicts(relations: list[Relation]) -> list[str]:
    """Breaches of the rule that keeps links and relations consistent: a chain
    has at most one link each way, and no link onward from (or into) a chain
    that a merge, split or regrouping ends (or starts)."""
    live = [r for r in relations if not r.rejected]
    out_links: dict[str, list[Relation]] = {}
    in_links: dict[str, list[Relation]] = {}
    for r in live:
        if r.is_link:
            out_links.setdefault(r.sources[0].id, []).append(r)
            in_links.setdefault(r.targets[0].id, []).append(r)
    problems = [
        f"{c} has {len(rs)} links onward: {', '.join(r.id for r in rs)}"
        for c, rs in out_links.items()
        if len(rs) > 1
    ]
    problems += [
        f"{c} has {len(rs)} links into it: {', '.join(r.id for r in rs)}"
        for c, rs in in_links.items()
        if len(rs) > 1
    ]
    for r in live:
        if r.is_link:
            continue
        both = {c.id for c in r.sources} & {c.id for c in r.targets}
        for c in r.sources:
            if c.id not in both and c.id in out_links:
                problems.append(
                    f"{c.id} ends in {r.id} ({r.relation}) but also continues in {out_links[c.id][0].id}"
                )
        for c in r.targets:
            if c.id not in both and c.id in in_links:
                problems.append(
                    f"{c.id} starts in {r.id} ({r.relation}) but also continues {in_links[c.id][0].id}"
                )
    return problems


def apply_decisions(
    relations: list[Relation], decisions: list[Decision], chains: list[Chain]
) -> tuple[list[Relation], list[Decision]]:
    """Apply the curated decisions; return the relations and the stale decisions.
    Each relation the code found keeps a copy of itself as found in ``found``."""
    for r in relations:
        r.found = replace(r)
    by_key = {r.key: r for r in relations}
    by_id = {c.id: c for c in chains}
    stale = []
    for d in decisions:
        key = (d.from_chains, d.to_chains)
        r = by_key.get(key)
        if d.decision == "add":
            if r is not None or not (d.from_chains | d.to_chains) <= by_id.keys():
                stale.append(d)
                continue
            r = Relation(
                [by_id[i] for i in sorted(d.from_chains)], [by_id[i] for i in sorted(d.to_chains)], d.relation
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
            relations.append(r)
            by_key[key] = r
        elif r is None:
            stale.append(d)
            continue
        elif d.decision == "change":
            r.relation, r.detail = d.relation, d.detail
        r.needs_verification, r.verified, r.note = False, VERIFIED[d.decision], d.note
    return relations, stale


def build_relations(
    chains: list[Chain], decisions: list[Decision], years: list[int] = YEARS, max_gap: int = MAX_GAP
) -> tuple[list[Relation], list[Decision]]:
    """Every relation the code finds, with the curated decisions applied, in
    order and numbered."""
    relations, stale = apply_decisions(find_relations(chains, years, max_gap), decisions, chains)
    for r in relations:
        r.sources.sort(key=lambda c: (c.code, c.years[0]))
        r.targets.sort(key=lambda c: (c.code, c.years[0]))
    relations.sort(key=lambda r: (r.section, r.sources[0].code, r.sources[0].years[0], r.year))
    numbers: Counter = Counter()
    for r in relations:
        prefix = "L" if r.is_link else "R"
        numbers[prefix] += 1
        r.id = f"{prefix}{numbers[prefix]:04d}"
    return relations, stale


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
    r: Relation,
    occ: Occurrence,
    chains: list[Chain] | None = None,
    min_siblings: int = 2,
    min_households: int = 20,
) -> Evidence | None:
    """Households reporting the source codes in the questionnaire year before
    the change against the target codes in the year of the change.  The ratio
    is taken relative to the other codes of the same groups (code without its
    last two digits), so survey-wide swings cancel out; the verdict says
    whether it fits the relation's scope change.  None when the table lacks
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


LINK_HEAD = ("link_id", "from_chain", "to_chain")
RELATION_HEAD = ("relation_id", "from_chains", "to_chains")


def write_links(relations: list[Relation], path: Path) -> None:
    """The final links (1 -> 1 continuations) among ``relations``."""
    _write([r for r in relations if r.is_link and r.final], path, LINK_HEAD)


def write_relations(relations: list[Relation], path: Path) -> None:
    """The final merges, splits and regroupings among ``relations``."""
    _write([r for r in relations if not r.is_link and r.final], path, RELATION_HEAD)


def write_suggested(relations: list[Relation], folder: Path) -> None:
    """What the code found, as it found it, in ``folder``: ``links.csv`` and
    ``relations.csv``, with who decided each and how (``open``: not yet)."""
    found = [r for r in relations if r.found is not None]
    _write([r for r in found if r.found.is_link], folder / "links.csv", LINK_HEAD, suggested=True)
    _write([r for r in found if not r.found.is_link], folder / "relations.csv", RELATION_HEAD, suggested=True)


def _write(rows: list[Relation], path: Path, head: tuple[str, str, str], suggested: bool = False) -> None:
    """``rows``; with ``suggested``, the relation, detail and score as the
    code found them, and no note (the note is a decision's)."""
    middle = ["relation", "detail", "year", "score", "decided_by", "verified"]
    with csv_io.writer(path, [*head, *middle, *([] if suggested else ["note"]), "from_text", "to_text"]) as w:
        for r in rows:
            f = r.found if suggested and r.found is not None else r
            w.writerow(
                [
                    r.id,
                    " ".join(c.id for c in r.sources),
                    " ".join(c.id for c in r.targets),
                    f.relation,
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


def write_evidence(relations: list[Relation], chains: list[Chain], occ: Occurrence, path: Path) -> Counter:
    """One row per relation with its household evidence; return the verdicts
    of the relations still to verify."""
    todo: Counter = Counter()
    with csv_io.writer(
        path,
        [
            "id",
            "relation",
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
        for r in relations:
            e = evidence(r, occ, chains)
            if r.needs_verification:
                todo[e.verdict if e else "no data"] += 1
            w.writerow(
                [r.id, r.relation, r.detail, r.year, r.decided_by, r.verified]
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
    out: Path = ITEMS / "relations.csv",
    links_out: Path = ITEMS / "links.csv",
    suggested: Path = ITEMS / "suggested",
    decisions: Path = DECISIONS,
    link_decisions: Path = LINK_DECISIONS,
    reuse_report: Path = REPORTS / "code_reuse.csv",
    evidence_report: Path = REPORTS / "relation_evidence.csv",
    occurrence: Path = OCCURRENCE,
    max_gap: int = MAX_GAP,
) -> None:
    """Matching stage 2: chains.csv -> output/3_items/links.csv and relations.csv.

    Parameters
    ----------
    chains
        The chains of stage 1.
    out
        Where the relations go.
    links_out
        Where the links go.
    suggested
        Where the code's suggestions go, before the decisions.
    decisions
        The curated relation decisions.
    link_decisions
        The curated link decisions.
    reuse_report
        Codes reused for an unrelated item.
    evidence_report
        Household evidence for the relations still to verify.
    occurrence
        The household occurrence table (skipped when missing).
    max_gap
        Questionnaires a relation may skip.
    """
    chain_list = read_chains(chains)
    curated = load_decisions(link_decisions, links=True) + load_decisions(decisions, links=False)
    relations, stale = build_relations(chain_list, curated, YEARS, max_gap)
    write_links(relations, links_out)
    write_relations(relations, out)
    write_suggested(relations, suggested)
    linked = {(a.id, b.id) for r in relations for a in r.sources for b in r.targets}
    reused = [p for p in code_reuse(chain_list, YEARS, max_gap) if (p[0].id, p[1].id) not in linked]
    write_code_reuse(reused, reuse_report)
    for name, rs, path in (
        ("links", [r for r in relations if r.is_link], link_decisions),
        ("relations", [r for r in relations if not r.is_link], decisions),
    ):
        kinds = Counter(r.relation for r in rs)
        verified = Counter(r.verified for r in rs if r.verified)
        print(
            f"{len(rs)} {name} ("
            + ", ".join(f"{k} {v}" for k, v in kinds.most_common())
            + f"): decided by the code {sum(r.decided_by == 'code' for r in rs)}, "
            + f"in {path.as_posix()}: "
            + (", ".join(f"{k} {v}" for k, v in verified.items()) or "0")
            + f", open: {sum(r.decided_by == 'open' for r in rs)}"
            + f"; final {sum(r.final for r in rs)}"
        )
    print(f"the code's suggestions, before the decisions -> {suggested.as_posix()}/")
    print(f"code reused for an unrelated item (no relation): {len(reused)} -> {reuse_report.as_posix()}")
    if occurrence.exists():
        todo_ev = write_evidence(relations, chain_list, load_occurrence(occurrence), evidence_report)
        print(
            "household evidence for those still to verify: "
            + (", ".join(f"{k} {v}" for k, v in todo_ev.most_common()) or "none")
            + f" -> {evidence_report.as_posix()}"
        )
    for d in stale:
        print(f"stale decision: {d}")
    for problem in conflicts(relations):
        print(f"links and relations disagree: {problem}")
