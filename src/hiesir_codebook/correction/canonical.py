"""One wording for labels that differ only in how they are written, and the
word fixes the groups teach.

Many labels are printed in several ways that differ only in spaces, ZWNJs,
the Arabic forms of ی and ک, hamza and how many dots an ellipsis has:
``تختخواب و میزتوالت`` / ``تختخواب و میز توالت``,
``حق‌بیمه‌های‌غیردرمانی‌...`` / ``حق بیمه‌های غیر درمانی ...``.  The labels as
step 1 leaves them are grouped by the :func:`.text.label_key` of what the
label steps make of them (:func:`variant_groups`: so a list joined with ``،``
or with ``و``, with or without "and so on", and the words the steps settle
keep no two labels apart), and every variant of a group gets the best finished
form of the group (:func:`choose_wordings`): what the label steps as they
stand make of each variant (so a hand fix of ``spelling.csv`` counts), judged
by how many words hazm does not know (:func:`unknown_words`), then by how often
the variant is printed, then by the latest year.  The later steps then meet each
group already fixed, and find work only in labels printed one way.  The
choices go to ``output/2_corrected/autocorrect/canonical.csv`` (the
``autocorrect`` command, :mod:`.words`), which the ``canonical`` step applies.
The file holds no word fix of its own: a variant takes the best label as
printed, and the label steps then fix it like any other, so the file comes out
the same however often it is made again, from nothing too.

Columns of ``canonical.csv``: ``find`` (a label as step 1 leaves it),
``replace`` (the best label of its group, as step 1 leaves it), ``uses`` (how
many rows print ``find``), ``years``, and ``evidence`` (the unknown words of
both finished forms, and how often each is printed).

Two finders of the automatic word fixes (:mod:`.words`) come from the groups,
so a label printed only once gains from the others:

- ``learned`` (:func:`learned_fixes`): each loser of a group lined up with its
  winner letter by letter (spaces and ZWNJs aside) and cut where both end a
  word; every stretch the loser writes otherwise is a fix
  (``ترانسفورماتورو`` -> ``ترانسفورماتور و``, ``وسائل`` -> ``وسایل``), kept when
  AGREE of the uses behind it agree, and when two groups teach a style both
  ways, the way more uses stand behind;
- ``folded`` (:func:`folded_fixes`): every word the labels write with other
  forms of ی, ک or hamza gets the house's spelling (ی over ئ, no hamza after a
  final ا), then hazm's, then the majority, never one a row of spelling.csv
  rewrites.
"""

from __future__ import annotations

from collections.abc import Callable

import polars as pl

from ..utils import ZWNJ
from .fixes import FixList
from .lexicon import Lexicon
from .text import PHRASE, WORD, label_char, label_key_expr, letters, years_text

COLUMNS = ["find", "replace", "uses", "years", "evidence"]
AGREE = 2 / 3  # how much of the evidence a learned word fix needs behind it
_SUFFIX_PIECES = ("هایی", "های", "ها", "ای", "ی")


def _unknown(w: str, lex: Lexicon) -> bool:
    """Is ``w`` a word hazm does not know (see :func:`unknown_words`)?"""
    if lex.level(w) >= 2:
        return False
    pieces = [p for p in w.split(ZWNJ) if p]
    return not (len(pieces) > 1 and all(lex.level(p) >= 2 or p in _SUFFIX_PIECES for p in pieces))


def unknown_words(label: str, lex: Lexicon) -> list[str]:
    """The words of ``label`` hazm does not know: not a word, nor a word with a
    suffix, nor a ZWNJ compound of such words (کم‌دوام)."""
    return [w for w in WORD.findall(label) if _unknown(w, lex)]


def _unknown_column(df: pl.DataFrame, column: str, lex: Lexicon) -> pl.Series:
    """The unknown words of each text of ``column``, in order: the words
    exploded and each distinct word asked of the lexicon once."""
    words = (
        df.select(pl.col(column).str.extract_all(WORD.pattern).alias("w")).with_row_index("i").explode("w")
    )
    distinct = words.select("w").drop_nulls().unique()
    known = distinct.with_columns(
        pl.Series("unknown", [_unknown(w, lex) for w in distinct["w"]], dtype=pl.Boolean)
    )
    return (
        words.join(known, on="w", how="left", maintain_order="left")
        .group_by("i", maintain_order=True)
        .agg(pl.col("w").filter(pl.col("unknown").fill_null(False)).alias("bad"))["bad"]
    )


# --- one wording per group ---------------------------------------------------------


def variant_groups(
    labels: pl.DataFrame, finish: Callable[[pl.Series], pl.Series] = lambda s: s
) -> pl.DataFrame:
    """Each distinct label of ``labels`` (``year``, ``description``) whose group
    writes it more than one way: ``label``, ``n`` (rows that print it),
    ``years``, ``finished`` (what the label steps make of it: ``finish``) and
    ``key``, the :func:`.text.label_key` of the finished form, so the words the
    steps settle (a glued و: ``آب ونصب``) do not keep two labels apart."""
    distinct = (
        labels.filter(pl.col("description") != "")
        .group_by(pl.col("description").alias("label"))
        .agg(pl.len().alias("n"), pl.col("year").unique().sort().alias("years"))
    )
    return (
        distinct.with_columns(finish(distinct["label"]).alias("finished"))
        .with_columns(label_key_expr("finished").alias("key"))
        .filter(pl.col("key").is_duplicated())
    )


def choose_wordings(variants: pl.DataFrame, lex: Lexicon) -> pl.DataFrame:
    """``canonical.csv`` from :func:`variant_groups`: the best of each group has
    the fewest unknown words in its finished form, then is printed most, then of
    the latest year, then first in order; every other variant is replaced by the
    best one as printed, which the label steps then fix like any label (so the
    file holds no word fix of its own, and comes out the same however often it
    is made again)."""
    variants = variants.with_columns(
        _unknown_column(variants, "finished", lex).alias("bad"),
        pl.col("years").list.max().alias("last_year"),
    )
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

    def listed(column: str) -> pl.Expr:
        """``"N"`` or ``"N (w1 w2)"``: how many unknown words, and which."""
        bad = pl.col(column)
        return (
            pl.when(bad.list.len() > 0)
            .then(pl.format("{} ({})", bad.list.len(), bad.list.join(" ")))
            .otherwise(bad.list.len().cast(pl.String))
        )

    return (
        variants.join(best, on="key")
        .filter(pl.col("label") != pl.col("best"))
        .sort("key", "label")
        .select(
            pl.col("label").alias("find"),
            pl.col("best").alias("replace"),
            pl.col("n").cast(pl.String).alias("uses"),
            pl.col("years").map_elements(years_text, return_dtype=pl.String).alias("years"),
            pl.format(
                "unknown words: {} against {}; printed {} times against {}",
                listed("bad"),
                listed("target_bad"),
                "n",
                "best_n",
            ).alias("evidence"),
        )
    )


# --- words: learned from the groups, and folded ------------------------------


def _skeleton(text: str) -> tuple[str, list[tuple[int, int]], list[bool]]:
    """``text`` as its letters (folded as :func:`.text.label_key` folds them,
    one key letter per letter), where each sits in ``text``, and after which a
    word ends (a space or a mark follows, or it is itself a mark; a ZWNJ does
    not end a word)."""
    keys, spans, ends = [], [], []
    for i, ch in enumerate(text):
        if ch in (" ", " "):
            if ends:
                ends[-1] = True
            continue
        folded = label_char(ch)
        if not folded:  # ZWNJ, tatweel, hamza alone
            continue
        mark = not PHRASE.fullmatch(ch)
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
            if a != b and PHRASE.fullmatch(a) and PHRASE.fullmatch(b):
                out.append((a, b))
            start = j + 1
    return out


def _squeezed(column: str) -> pl.Expr:
    return pl.col(column).str.replace_many([" ", ZWNJ], ["", ""])


def learned_fixes(pairs: pl.DataFrame) -> pl.DataFrame:
    """Word fixes from ``pairs`` (``loser``, ``winner``, ``n`` uses): every
    stretch a loser writes otherwise than its winner, kept when at least AGREE
    of the uses behind it agree on how to write it."""
    pieces = pl.DataFrame(
        [(a, b, n) for loser, winner, n in pairs.iter_rows() for a, b in aligned_pieces(loser, winner)],
        schema={"find": pl.String, "replace": pl.String, "n": pl.Int64},
        orient="row",
    )
    # the votes for each way of writing a stretch, in the order first met
    votes = pieces.group_by("find", "replace", maintain_order=True).agg(pl.col("n").sum())
    back = votes.select(
        pl.col("replace").alias("find"), pl.col("find").alias("replace"), pl.col("n").alias("back")
    )
    best = votes.group_by("find", maintain_order=True).agg(
        pl.col("replace", "n").sort_by("n", descending=True, maintain_order=True).first(),
        pl.col("n").sum().alias("total"),
    )
    # the other ways the votes write it, for the evidence
    also = (
        votes.join(best.select("find", pl.col("replace").alias("chosen")), on="find", maintain_order="left")
        .filter(pl.col("replace") != pl.col("chosen"))
        .group_by("find", maintain_order=True)
        .agg(pl.format("{} {}", "replace", "n").str.join(", ").alias("also"))
    )
    out = (
        best.join(back, on=["find", "replace"], how="left", maintain_order="left")
        .join(also, on="find", how="left", maintain_order="left")
        .with_columns(pl.col("back").fill_null(0))
        .filter(
            # letter forms (ئ / ی, ؤ / و, hamza) are the folded fixes' business
            ~(
                (_squeezed("find") != _squeezed("replace"))
                & (letters.expr(_squeezed("find")) == letters.expr(_squeezed("replace")))
            ),
            # two groups may teach a style both ways (بی دوام / بی‌دوام): the way
            # more uses stand behind wins
            ~(
                (pl.col("back") > pl.col("n"))
                | ((pl.col("back") == pl.col("n")) & (pl.col("replace") < pl.col("find")))
            ),
            pl.col("n") >= AGREE * pl.col("total"),
        )
    )
    return out.select(
        "find",
        "replace",
        pl.lit("learned").alias("kind"),
        pl.when(pl.col("total") > pl.col("n"))
        .then(pl.format("a group's winner writes it so; also {}", "also"))
        .otherwise(pl.lit("a group's winner writes it so"))
        .alias("evidence"),
    )


def folded_fixes(texts: pl.Series, lex: Lexicon, spelling: FixList | None = None) -> pl.DataFrame:
    """Word fixes for every word the finished labels (``texts``) write in more
    than one way that differ only in the forms of ی, ک and hamza (وسائل /
    وسایل, موسسات / مؤسسات): each gets the house's form, then hazm's, then the
    one the labels write most (تزئینی / تزیینی -> تزیینی: the house style
    writes یی for ئی only after a vowel, so the texts it leaves may still
    differ so).  ZWNJs are the plural's and the compound rules' business, so
    they do not count.  A form that a row of spelling.csv rewrites (دائره ->
    دایره) is never chosen: the hand decision wins."""
    uses = (
        texts.str.extract_all(WORD.pattern)
        .explode()
        .drop_nulls()
        .to_frame("word")
        .filter(~pl.col("word").str.starts_with("ء"))
        .group_by("word", maintain_order=True)
        .len("uses")
        .with_columns(letters.expr("word").alias("key"))
        .filter(pl.len().over("key") >= 2)
    )
    spelling = spelling or FixList()
    settled = [spelling.apply(w) == w for w in uses["word"]]
    vouched = lex.table.filter("vouched")["word"]
    ranked = uses.with_columns(
        pl.Series("stable", settled, dtype=pl.Boolean),
        # the house's spelling first: ی over ئ (دایره, ویدیو) and no hamza after
        # a final ا (اعضا, اولیا), then hazm's, then the labels' majority
        (
            pl.col("word").str.count_matches("ئ", literal=True)
            + pl.col("word").str.count_matches("ء", literal=True)
        ).alias("hamzas"),
        pl.col("word").is_in(vouched.implode()).alias("hazm"),
    )
    best = (
        ranked.filter("stable")
        .sort(["hamzas", "hazm", "uses", "word"], descending=[False, True, True, False])
        .group_by("key", maintain_order=True)
        .first()
        .select(
            "key",
            pl.col("word").alias("best"),
            pl.col("uses").alias("best_uses"),
            pl.col("hazm").alias("best_hazm"),
        )
    )
    return (
        ranked.join(best, on="key", maintain_order="left")
        .filter(pl.col("word") != pl.col("best"))
        .select(
            pl.col("word").alias("find"),
            pl.col("best").alias("replace"),
            pl.lit("folded").alias("kind"),
            (
                pl.format("the labels write {} {} times", "best", "best_uses")
                + pl.when("best_hazm").then(pl.lit("; hazm lists it")).otherwise(pl.lit(""))
            ).alias("evidence"),
        )
    )
