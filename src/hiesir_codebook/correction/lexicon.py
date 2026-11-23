"""hazm's word list as the correction steps read it: one polars table.

:func:`hazm_table` puts every word the steps may look up in one table,
``word``, ``freq``, ``vouched``:

- hazm's ``words.dat`` (:func:`hiesir_codebook.hazm_data.words`): about 27,000
  words met in its corpus (with their frequency), 8,500 with a part of speech
  but frequency 0, and 158,000 bare headwords with neither, mostly rare or
  archaic words (``سنگی``, ``والک``) but also glued junk (``ویخ``, ``وکم``).
  hazm *vouches* for a word with a frequency or a part of speech;
- the forms of hazm's verbs (``verbs.dat``), which its list leaves out
  (:func:`verb_forms`: کرد, شده, می‌شود, کننده ...), vouched for;
- ``curated/2_corrected/words.csv``: correct words hazm lacks, each with a
  reason (the plant ``والک``, which glued_vav would cut into و + الک), vouched for.

:class:`Lexicon` answers the per-word questions of the rules from that table:
is a word *listed* at all, *known* (vouched for), or a known word with a
suffix hazm does not list it with (``پلاستیکی`` = ``پلاستیک`` + ی).  Every
lookup ignores ZWNJs and the Arabic forms of ی, ک and hamza
(:data:`.text.word_key`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import polars as pl

from .. import CURATED_CORRECTED, csv_io, hazm_data
from ..utils import ZWNJ
from .text import word_key

WORDS = CURATED_CORRECTED / "words.csv"
COMMON = 10_000  # a common word in hazm's corpus; verb forms and curated words count as one

# what a known word may carry and still count as known, longest first: the
# plural, ی (adjective, indefinite, ezafe), ای / یی after a vowel, the plurals
# ان and ات, and the comparative
SUFFIXES = ("هایی", "های", "ها", "ترین", "تر", "ای", "یی", "ان", "ات", "ی")

_SCHEMA = {"word": pl.String, "freq": pl.Int64, "vouched": pl.Boolean}


# --- the table -------------------------------------------------------------------

_PAST_ENDINGS = ("م", "ی", "", "یم", "ید", "ند")
_PRESENT_ENDINGS = ("م", "ی", "د", "یم", "ید", "ند")
# the perfect takes است alone: the personal endings (سوخته‌ای) would read as plurals (سوختهای)
_PERFECT = f"ه{ZWNJ}است"
_TO_BE = ("است", "نیست", "هست", "هستند", "نیستند", "بود", "بودند", "باشد", "نباشد", "باشند", "نباشند")


def _templates() -> pl.DataFrame:
    """How a stem makes a form: ``stem`` (which one), ``prefix``, ``suffix``."""
    rows = []
    for neg in ("", "ن"):
        # past (کرد, نکردند), participle (شده) and perfect (شده‌است)
        rows += [("past", neg, e) for e in (*_PAST_ENDINGS, "ه", _PERFECT)]
        # present (کنم), with می / نمی (می‌شود), and the agent noun (کننده)
        rows += [("present", neg, e) for e in (*_PRESENT_ENDINGS, "نده")]
        rows += [("present", f"{'نمی' if neg else 'می'}{ZWNJ}", e) for e in _PRESENT_ENDINGS]
    rows += [("present", "ب", e) for e in _PRESENT_ENDINGS]  # the subjunctive (بشود)
    return pl.DataFrame(rows, schema=["stem", "prefix", "suffix"], orient="row")


def verb_forms(verbs: pl.DataFrame) -> pl.Series:
    """The forms of the verbs in ``verbs`` (``past``, ``present``): every stem
    joined with every template that takes it, and the verb to be."""
    forms = (
        verbs.unpivot(on=["past", "present"], variable_name="stem", value_name="base")
        .filter(pl.col("base") != "")
        .join(_templates(), on="stem")
        .select(pl.concat_str("prefix", "base", "suffix").alias("word"))
    )
    return pl.concat([forms, pl.DataFrame({"word": _TO_BE})])["word"].unique().sort()


def _glued_vav(column: str, listed: pl.Series) -> pl.Expr:
    """و + a word hazm lists: a glued و far more often than a rare verb or stem
    (وسیم of وشت#وس is و + سیم); ورزید stays."""
    return pl.col(column).str.starts_with("و") & pl.col(column).str.slice(1).is_in(listed.implode())


def load_words(path: Path = WORDS) -> pl.DataFrame:
    """``words.csv``: the correct words hazm lacks (``word``, ``reason``)."""
    if not path.exists():
        return pl.DataFrame(schema={"word": pl.String, "reason": pl.String})
    df = csv_io.read_frame(path).with_columns(pl.col("word", "reason").str.strip_chars())
    missing = df.filter((pl.col("word") == "") | (pl.col("reason") == ""))
    if missing.height:
        raise ValueError(f"{path}: every row needs a word and a reason ({missing['word'][0]})")
    return df


def hazm_table(words: Path = WORDS, folder: Path = hazm_data.HAZM_DIR) -> tuple[pl.DataFrame, pl.Series]:
    """Every word the rules may look up (``word``, ``freq``, ``vouched``), and
    the present stems of hazm's verbs (کش, دار, بند: the heads of compounds)."""
    hazm = hazm_data.words(folder).select(
        "word", "freq", ((pl.col("freq") > 0) | (pl.col("pos") != "0")).alias("vouched")
    )
    verbs = hazm_data.verbs(folder)
    forms = verb_forms(verbs).to_frame().filter(~_glued_vav("word", hazm["word"]))
    # a curated phrase counts, and each of its words (گالینا بلانکا)
    curated = load_words(words).select(
        pl.concat_list(pl.col("word"), pl.col("word").str.split(" ")).alias("word")
    )
    extra = pl.concat([forms, curated.explode("word")]).select(
        "word", pl.lit(COMMON, pl.Int64).alias("freq"), pl.lit(True).alias("vouched")
    )
    listed = pl.concat([hazm["word"], forms["word"]])
    stems = (
        verbs.select(pl.col("present").alias("stem"))
        .filter((pl.col("stem").str.len_chars() >= 2) & ~pl.col("stem").str.contains(" "))
        .filter(~_glued_vav("stem", listed))["stem"]
        .unique()
    )
    return pl.concat([hazm, extra]), stems


# --- the lookups -----------------------------------------------------------------


@dataclass
class Lexicon:
    """The per-word lookups of a word table (``word``, ``freq``, ``vouched``):
    built once from the table, then asked word by word by the rules."""

    table: pl.DataFrame  # one row per word: word, freq (the highest), vouched, key
    stems: frozenset[str] = frozenset()
    freq: dict[str, int] = field(init=False, repr=False)
    words: set[str] = field(init=False, repr=False)  # the vouched words
    _by_key: dict[str, int] = field(init=False, repr=False)
    _word_keys: set[str] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        t = self.table
        self.freq = dict(zip(t["word"], t["freq"], strict=True))
        self.words = set(t.filter("vouched")["word"])
        by_key = t.group_by("key").agg(pl.col("freq").max())
        self._by_key = dict(zip(by_key["key"], by_key["freq"], strict=True))
        self._word_keys = set(t.filter("vouched")["key"])

    @classmethod
    def from_table(cls, df: pl.DataFrame, stems=()) -> Lexicon:
        """A word listed twice keeps its highest frequency, and is vouched for
        when any of its rows is."""
        table = (
            df.group_by("word", maintain_order=True)
            .agg(pl.col("freq").max(), pl.col("vouched").any())
            .with_columns(word_key.expr("word").alias("key"))
        )
        return cls(table, frozenset(stems))

    @classmethod
    def of(cls, freq: dict[str, int], words=(), stems=()) -> Lexicon:
        """A small lexicon (tests): ``freq`` the listed words, ``words`` the vouched ones."""
        listed = {**freq, **{w: freq.get(w, 0) for w in words}}
        df = pl.DataFrame(
            {
                "word": list(listed),
                "freq": list(listed.values()),
                "vouched": [w in set(words) for w in listed],
            },
            schema=_SCHEMA,
        )
        return cls.from_table(df, stems)

    def count(self, w: str) -> int:
        return self.freq.get(w) or self._by_key.get(word_key(w), 0)

    def listed(self, w: str) -> bool:
        """In hazm's list at all, even a bare headword."""
        return w in self.freq or word_key(w) in self._by_key

    def known(self, w: str) -> bool:
        """A word hazm vouches for."""
        return w in self.words or word_key(w) in self._word_keys

    def stem(self, w: str) -> tuple[str, str] | None:
        """``(stem, suffix)`` when ``w`` is a known word with a suffix hazm
        does not list it with: ``پلاستیکی`` -> ``("پلاستیک", "ی")``,
        ``کالاهای`` -> ``("کالا", "های")``, ``پارچه‌ای`` -> ``("پارچه", "ای")``."""
        key = word_key(w)
        for suffix in SUFFIXES:
            stem = key[: -len(suffix)]
            if key.endswith(suffix) and len(stem) >= 2 and (self.known(stem) or self._stem_once(stem)):
                return stem, suffix
        return None

    def _stem_once(self, w: str) -> bool:
        """A known word with one suffix: lets suffixes stack (بیماریهای =
        بیمار + ی + های), two deep at most."""
        return any(w.endswith(x) and len(w) - len(x) >= 2 and self.known(w[: -len(x)]) for x in SUFFIXES)

    def compound_head(self, w: str) -> bool:
        """Is ``w`` a verb's present stem, or one with ی or نده (کش, کشی,
        داری, بندها, کننده), which makes a compound with the word before it
        (اطوکشی, عزاداری, ترکبند, ضدعفونی‌کننده)?"""
        w = word_key(w)
        for suffix in ("هایی", "های", "ها", ""):
            if suffix and not w.endswith(suffix):
                continue
            core = w[: len(w) - len(suffix)]
            for tail in ("", "ی", "نده", "ندگی"):
                if (tail == "" or core.endswith(tail)) and core[: len(core) - len(tail)] in self.stems:
                    return True
        return False

    def level(self, w: str) -> int:
        """How sure hazm is that ``w`` is a word: 3 known, 2 a known word with a
        suffix, 1 only listed, 0 not there."""
        return 3 if self.known(w) else 2 if self.stem(w) else 1 if self.listed(w) else 0


def hazm_lexicon(words: Path = WORDS, folder: Path = hazm_data.HAZM_DIR) -> Lexicon:
    """The lexicon of :func:`hazm_table` (needs hazm's data)."""
    table, stems = hazm_table(words, folder)
    return Lexicon.from_table(table, stems)
