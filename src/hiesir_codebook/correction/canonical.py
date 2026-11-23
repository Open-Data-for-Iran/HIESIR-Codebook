"""Correction step 2: one wording for labels that differ only in how they are written.

Many labels are printed in several ways that differ only in spaces, ZWNJs,
the Arabic forms of ی and ک, hamza and how many dots an ellipsis has:
``تختخواب و میزتوالت`` / ``تختخواب و میز توالت``,
``حق‌بیمه‌های‌غیردرمانی‌...`` / ``حق بیمه‌های غیر درمانی ...``.  This step reads
every label once, as the structural corrections (:mod:`.corrections`, step 1)
leave it, groups the labels by their canonical form (:func:`canonical_key`),
and gives every variant of a group the best finished form of the group: what
the steps as they stand make of each variant (so a hand fix of
``spelling.csv`` counts) is judged by how many words hazm does not know
(:func:`unknown_words`), then by how often the variant is printed, then by the
latest year.  The later steps then meet each group already fixed, and find
work only in labels printed one way; a second run finds what the first did.  The choices go to
``output/2_corrected/autocorrect/canonical.csv``, which the build applies to
whole labels before the house style (:mod:`.rules`, step 3), the automatic
fixes (:mod:`.autocorrect`, step 4) and ``spelling.csv`` (:mod:`.spelling`,
step 5), so it runs without hazm's data.  Regenerate it, then the automatic
fixes, with hazm's data downloaded:

    uv run hiesir-codebook canonical
    uv run hiesir-codebook autocorrect

The file is a record as well: it holds the finished forms the rows of
``spelling.csv`` and the automatic fixes once made, after those rows go.

Then the words, in ``output/2_corrected/autocorrect/canonical_words.csv``,
applied to every label after the label mapping, so a label printed only once
gains from the others:

- ``learned``: each loser of a group lined up with its winner letter by letter
  (spaces and ZWNJs aside) and cut where both end a word; every stretch the
  loser writes otherwise is a fix (``ترانسفورماتورو`` -> ``ترانسفورماتور و``,
  ``وسائل`` -> ``وسایل``), kept when AGREE of the uses behind it agree, and when
  two groups teach a style both ways, the way more uses stand behind;
- ``folded``: every word the labels write with other forms of ی, ک or hamza
  gets the house's spelling (ی over ئ, no hamza after a final ا), then
  hazm's, then the majority, never one a row of spelling.csv rewrites; judged
  on the labels finished without these fixes, so they do not count their own
  work.

Columns of ``canonical.csv``: ``find`` (a label as step 1 leaves it),
``replace`` (the finished form of its group), ``uses`` (how many rows
print ``find``), ``years``, and ``evidence`` (the unknown words and uses of
both).
"""

from __future__ import annotations

import functools
import re
from collections import Counter
from collections.abc import Callable, Iterable
from pathlib import Path

import polars as pl

from .. import csv_io
from ..utils import ZWNJ
from .autocorrect import _WORD, AUTOCORRECT_DIR, PLURALS, Lexicon, hazm_lexicon, years_text
from .spelling import LabelFix, fix_label

CANONICAL = AUTOCORRECT_DIR / "canonical.csv"
CANONICAL_WORDS = AUTOCORRECT_DIR / "canonical_words.csv"
COLUMNS = ["find", "replace", "uses", "years", "evidence"]
WORD_COLUMNS = ["find", "replace", "kind", "uses", "evidence"]
AGREE = 2 / 3  # how much of the evidence a learned word fix needs behind it

# what a canonical form ignores: spaces and ZWNJs, the Arabic forms of ی and
# ک, hamza, ة, tatweel, and the Latin comma
_FOLD_MAP = {
    " ": "",
    " ": "",
    ZWNJ: "",
    "ـ": "",
    "ي": "ی",
    "ك": "ک",
    "ئ": "ی",
    "أ": "ا",
    "إ": "ا",
    "ؤ": "و",
    "ء": "",
    "ة": "ه",
    ",": "،",
}
_FOLD = str.maketrans({k: v or None for k, v in _FOLD_MAP.items()})


def canonical_key(label: str) -> str:
    """``label`` as its group knows it: no spaces or ZWNJs, one form of each
    letter, an ellipsis of any length as one dot."""
    return re.sub(r"\.+", ".", label.translate(_FOLD))


def canonical_key_expr(column: str) -> pl.Expr:
    """:func:`canonical_key` as a polars expression."""
    return (
        pl.col(column)
        .str.replace_many(list(_FOLD_MAP), list(_FOLD_MAP.values()))
        .str.replace_all(r"\.+", ".")
    )


def _unknown(w: str, lex: Lexicon) -> bool:
    """Is ``w`` a word hazm does not know (see :func:`unknown_words`)?"""
    if lex.level(w) >= 2:
        return False
    pieces = [p for p in w.split(ZWNJ) if p]
    return not (len(pieces) > 1 and all(lex.level(p) >= 2 or p in (*PLURALS, "ای", "ی") for p in pieces))


def unknown_words(label: str, lex: Lexicon) -> list[str]:
    """The words of ``label`` hazm does not know: not a word, nor a word with a
    suffix, nor a ZWNJ compound of such words (کم‌دوام)."""
    return [w for w in _WORD.findall(label) if _unknown(w, lex)]


def choose(
    variants: Counter, years: dict[str, set[int]], lex: Lexicon, finish: Callable[[str], str] = str
) -> str:
    """The variant for the whole group: the one whose result (``finish``: what
    the later steps make of it, so a hand fix of spelling.csv counts) has the
    fewest unknown words, then the one printed most, then of the latest year,
    then the first in order."""
    return max(
        sorted(variants),
        key=lambda t: (-len(unknown_words(finish(t), lex)), variants[t], max(years[t])),
    )


def find_variants(
    labels: Iterable[tuple[int, str]], lex: Lexicon, finish: Callable[[str], str] = str
) -> list[dict[str, str]]:
    """A row for every label that its group writes otherwise (``finish``: see
    :func:`choose`), in polars: the labels grouped by their canonical key, the
    words of each finished form exploded and asked of the lexicon once per
    distinct word, and the best variant of each group taken by sorting."""
    labels = [(y, t) for y, t in labels if t]
    if not labels:
        return []
    variants = (
        pl.DataFrame({"year": [y for y, _ in labels], "label": [t for _, t in labels]}, orient="col")
        .group_by("label")
        .agg(pl.len().alias("n"), pl.col("year").unique().sort().alias("years"))
        .with_columns(canonical_key_expr("label").alias("key"))
        .filter(pl.col("key").is_duplicated())
        .with_columns(
            pl.col("label").map_elements(finish, return_dtype=pl.String).alias("finished"),
            pl.col("years").list.max().alias("last_year"),
        )
    )
    # the unknown words of each finished form, in order, each word asked once
    words = (
        variants.select("finished")
        .unique()
        .with_columns(pl.col("finished").str.extract_all(_WORD.pattern).alias("word"))
        .explode("word")
    )
    known = (
        words.select("word")
        .drop_nulls()
        .unique()
        .with_columns(
            pl.col("word").map_elements(lambda w: _unknown(w, lex), return_dtype=pl.Boolean).alias("unknown")
        )
    )
    bad = (
        words.join(known, on="word", how="left", maintain_order="left")
        .filter(pl.col("unknown"))
        .group_by("finished", maintain_order=True)
        .agg(pl.col("word").alias("bad"))
    )
    variants = variants.join(bad, on="finished", how="left").with_columns(
        pl.col("bad").fill_null(pl.lit([], dtype=pl.List(pl.String)))
    )
    # the best of each group: fewest unknown words, printed most, latest year, first label
    best = (
        variants.sort(
            ["key", pl.col("bad").list.len(), "n", "last_year", "label"],
            descending=[False, False, True, True, False],
        )
        .group_by("key", maintain_order=True)
        .first()
        .select(
            "key",
            pl.col("label").alias("best"),
            pl.col("finished").alias("target"),
            pl.col("n").alias("best_n"),
            pl.col("bad").alias("target_bad"),
        )
    )
    rows = variants.join(best, on="key").filter(pl.col("label") != pl.col("target")).sort("key", "label")
    out = []
    for r in rows.iter_rows(named=True):
        mine, bad_words = r["bad"], r["target_bad"]
        out.append(
            {
                "find": r["label"],
                "replace": r["target"],
                "uses": str(r["n"]),
                "years": years_text(r["years"]),
                "evidence": (
                    f"unknown words: {len(mine)}"
                    + (f" ({' '.join(mine)})" if mine else "")
                    + f" against {len(bad_words)}"
                    + (f" ({' '.join(bad_words)})" if bad_words else "")
                    + f"; printed {r['n']} times against {r['best_n']} ({r['best']})"
                ),
            }
        )
    return out


# --- words: learned from the groups, and folded ------------------------------

_LETTERS_FOLD = str.maketrans({"ي": "ی", "ك": "ک", "ئ": "ی", "أ": "ا", "إ": "ا", "ؤ": "و", "ء": None})


_WORDS_ONLY = re.compile(f"[ء-يٹ-ۓ{ZWNJ} ]+")


def _skeleton(text: str) -> tuple[str, list[tuple[int, int]], list[bool]]:
    """``text`` as its letters (folded, as :func:`canonical_key` folds them, but
    one key letter per letter), where each sits in ``text``, and after which a
    word ends (a space or a mark follows, or it is itself a mark; a ZWNJ does
    not end a word)."""
    keys, spans, ends = [], [], []
    for i, ch in enumerate(text):
        folded = _FOLD_MAP.get(ch, ch)
        if ch == " " or ch == "\u00a0":
            if ends:
                ends[-1] = True
            continue
        if not folded:  # ZWNJ, tatweel, hamza alone
            continue
        mark = not _WORDS_ONLY.fullmatch(ch)
        if mark and ends:
            ends[-1] = True
        keys.append(folded)
        spans.append((i, i + 1))
        ends.append(mark)
    if ends:
        ends[-1] = True
    return "".join(keys), spans, ends


def aligned_pieces(loser: str, winner: str) -> list[tuple[str, str]]:
    """The stretches of ``loser`` that ``winner`` writes otherwise, cut at the
    word ends both share, when the two have the same letters: ``انواع
    ژنراتور،ترانسفورماتورو انواع وسائل`` against ``انواع ژنراتور، ترانسفورماتور
    و انواع وسایل`` gives ``ترانسفورماتورو`` -> ``ترانسفورماتور و`` and ``وسائل`` ->
    ``وسایل``; only stretches of words (no marks)."""
    ka, sa, ea = _skeleton(loser)
    kb, sb, eb = _skeleton(winner)
    if ka != kb or not ka:
        return []
    out, start = [], 0
    for j in range(len(ka)):
        if ea[j] and eb[j]:
            a = loser[sa[start][0] : sa[j][1]].strip()
            b = winner[sb[start][0] : sb[j][1]].strip()
            if a != b and _WORDS_ONLY.fullmatch(a) and _WORDS_ONLY.fullmatch(b):
                out.append((a, b))
            start = j + 1
    return out


def learned_fixes(pairs: Iterable[tuple[str, str, int]]) -> list[dict[str, str]]:
    """Word fixes from ``(loser, winner, uses)``: every stretch a loser writes
    otherwise than its winner, kept when at least AGREE of the uses behind it
    agree on how to write it."""
    seen: dict[str, Counter] = {}
    for loser, winner, n in pairs:
        for a, b in aligned_pieces(loser, winner):
            seen.setdefault(a, Counter())[b] += n
    out = []
    for a, targets in seen.items():
        b, n = targets.most_common(1)[0]
        total = sum(targets.values())
        # letter forms (ئ / ی, ؤ / و, hamza) are the folded fixes' business
        if a.replace(" ", "").replace(ZWNJ, "") != b.replace(" ", "").replace(ZWNJ, "") and (
            a.translate(_LETTERS_FOLD).replace(" ", "").replace(ZWNJ, "")
            == b.translate(_LETTERS_FOLD).replace(" ", "").replace(ZWNJ, "")
        ):
            continue
        # two groups may teach a style both ways (بی دوام / بی‌دوام): the way more
        # uses stand behind wins
        back = seen.get(b, Counter()).get(a, 0)
        if back > n or (back == n and b < a):
            continue
        if n >= AGREE * total:
            out.append(
                {
                    "find": a,
                    "replace": b,
                    "kind": "learned",
                    "uses": str(n),
                    "evidence": "a group's winner writes it so"
                    + (
                        f"; also {', '.join(f'{t} {c}' for t, c in targets.items() if t != b)}"
                        if total > n
                        else ""
                    ),
                }
            )
    return out


def folded_fixes(
    texts: Iterable[str], lex: Lexicon, settle: Callable[[str], str] = str
) -> list[dict[str, str]]:
    """Word fixes for every word the finished labels (``texts``) write in more
    than one way that differ only in the forms of ی, ک and hamza (وسائل /
    وسایل, موسسات / مؤسسات): each gets the form hazm lists exactly, then the one
    the labels write most.  ZWNJs are the plural's and the compound rules'
    business, and ئی / یی the house style's (روئی -> رویی), so neither counts.
    A form that a row of spelling.csv rewrites (``settle``: دائره -> دایره) is
    never chosen: the hand decision wins."""
    uses = Counter(w for t in texts for w in _WORD.findall(t) if not w.startswith("ء"))
    groups: dict[str, list[str]] = {}
    for w in uses:
        groups.setdefault(w.translate(_LETTERS_FOLD), []).append(w)
    for key in list(groups):
        if len({w.replace("ئی", "یی") for w in groups[key]}) < 2:
            del groups[key]
    out = []
    for forms in groups.values():
        if len(forms) < 2:
            continue
        stable = [w for w in forms if settle(w) == w]
        if not stable:
            continue
        # the house's spelling first: ی over ئ (دایره, ویدیو) and no hamza after
        # a final ا (اعضا, اولیا), then hazm's, then the labels' majority
        best = max(sorted(stable), key=lambda w: (-(w.count("ئ") + w.count("ء")), w in lex.words, uses[w]))
        for w in forms:
            if w != best:
                out.append(
                    {
                        "find": w,
                        "replace": best,
                        "kind": "folded",
                        "uses": str(uses[w]),
                        "evidence": f"the labels write {best} {uses[best]} times"
                        + ("; hazm lists it" if best in lex.words else ""),
                    }
                )
    return out


def load_word_fixes(path: Path = CANONICAL_WORDS) -> list[LabelFix]:
    """The fixes of ``canonical_words.csv`` as whole-word label fixes, the
    learned ones first (none when the file is not there)."""
    if not path.exists():
        return []
    rows = csv_io.read(path)
    rows.sort(key=lambda r: (r["kind"] != "learned", -len(r["find"])))
    return [LabelFix(r["find"], r["replace"], "word", None, r["kind"]) for r in rows]


def load_variants(path: Path = CANONICAL) -> dict[str, str]:
    """``find`` -> ``replace`` of ``canonical.csv`` (empty when it is not there)."""
    if not path.exists():
        return {}
    return {r["find"]: r["replace"] for r in csv_io.read(path)}


def main(*, out: Path = CANONICAL, words_out: Path = CANONICAL_WORDS) -> None:
    """Correction step 2: one wording for labels that differ only in how they are written.

    Needs hazm's data (``hiesir-codebook hazm download``).

    Parameters
    ----------
    out
        The label variants and the wording each takes.
    words_out
        The word fixes learned from them, and the folded forms of each word.
    """
    from .autocorrect import load_fixes
    from .correct import Steps, labels_after_corrections
    from .rules import house_style
    from .spelling import load_label_fixes

    lex = hazm_lexicon()
    labels = labels_after_corrections()
    # each variant judged by what the steps make of it today, this one included,
    # so a second run finds what the first one did (the steps are stable)
    steps = Steps(load_label_fixes(), load_fixes(), load_variants(out), words=load_word_fixes(words_out))
    finish = functools.cache(lambda t: steps(t, 0))
    rows = find_variants(labels, lex, finish)
    csv_io.write(out, COLUMNS, rows)
    print(
        f"{len(rows)} labels written otherwise in their group -> {out.as_posix()} "
        f"({sum(int(r['uses']) for r in rows)} rows)"
    )
    # the words: what the losers of the groups teach, then the forms of each word
    styled = functools.cache(house_style)
    learned = learned_fixes((styled(r["find"]), r["replace"], int(r["uses"])) for r in rows)
    spelling = load_label_fixes()
    settle = functools.cache(lambda w: fix_label(w, 0, spelling))
    # the folded fixes judged on the labels as the label mapping, the learned
    # fixes and the house style leave them, without the folded fixes, so they do
    # not count their own work (a second run finds what the first did)
    unfolded = Steps(
        spelling,
        load_fixes(),
        load_variants(out),
        upto=3,  # before the automatic fixes and the word rows of spelling.csv, which settle these words
        words=[fx for fx in load_word_fixes(words_out) if fx.reason == "learned"],
    )
    words = learned + folded_fixes((unfolded(t, 0) for _, t in set(labels)), lex, settle)
    words.sort(key=lambda r: (r["kind"], r["find"]))
    csv_io.write(words_out, WORD_COLUMNS, words)
    print(
        f"{len(words)} word fixes -> {words_out.as_posix()} "
        f"({sum(r['kind'] == 'learned' for r in words)} learned from the groups, "
        f"{sum(r['kind'] == 'folded' for r in words)} folded)"
    )
