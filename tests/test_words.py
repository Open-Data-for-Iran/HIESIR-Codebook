"""The automatic fixes: the chain of finders behind words.csv (learned,
folded, hazm's rules), the lexicon they ask, and the canonical wordings."""

from pathlib import Path

import polars as pl
import pytest

from hiesir_codebook import csv_io, hazm_data
from hiesir_codebook.correction import canonical, words
from hiesir_codebook.correction import hazm_rules as autocorrect
from hiesir_codebook.correction.fixes import Fix, Fixes, FixList, read_words
from hiesir_codebook.correction.hazm_rules import find_fixes, glued_vav, joined_plural, spaced_suffix
from hiesir_codebook.correction.lexicon import Lexicon, load_words, verb_forms

ROOT = Path(__file__).resolve().parents[1]

# known: met in the corpus or given a part of speech; listed only: bare headwords
LEX = Lexicon.of(
    freq={
        "یخ": 714221,
        "نخ": 437077,
        "الک": 109007,
        "ویخ": 0,
        "سنگی": 0,
        "ورنی": 0,
        "رنی": 0,
        "وام": 900,
        "پلاستیک": 627087,
        "کالا": 2212284,
        "پارچه": 1000,
        "ورود": 15401712,
        "رود": 223000773,
        "لایی": 32101,
        "ولا": 2250020,
        "نمایش": 12602746,
        "پودر": 24000151,
        "تن": 5000000,
        "تنها": 90000000,
        "سالن": 1810894,
        "سیب‌زمینی": 300000,
        "وب": 0,
        "بها": 2000000,
    },
    words={
        "یخ",
        "نخ",
        "الک",
        "وام",
        "پلاستیک",
        "کالا",
        "پارچه",
        "ورود",
        "رود",
        "لایی",
        "ولا",
        "نمایش",
        "پودر",
        "تن",
        "تنها",
        "سالن",
        "سیب‌زمینی",
        "وب",
        "بها",
    },
)


def _labels(*pairs: tuple[int, str]) -> pl.DataFrame:
    return pl.DataFrame(pairs, schema={"year": pl.Int64, "label": pl.String}, orient="row")


def _found(*pairs: tuple[int, str], lex: Lexicon = LEX) -> dict[str, str]:
    df = find_fixes(_labels(*pairs), lex)
    return dict(zip(df["find"], df["replace"], strict=True))


@pytest.mark.parametrize(
    ("word", "fixed"),
    [
        ("ویخ", "و یخ"),  # listed only, its rest a word
        ("ونخ", "و نخ"),  # not listed, its rest a word
        ("وسنگی", "و سنگی"),  # not listed, its rest listed
        ("ورنی", None),  # listed, its rest only listed: no higher
        ("وام", None),  # a word of its own
        ("وپلاستیکی", "و پلاستیکی"),  # its rest a known word + ی
        ("وکالاهای", "و کالاهای"),  # + های
        ("وپارچه‌ای", "و پارچه‌ای"),  # + ای, after a ZWNJ
        ("ورودی", None),  # ورود + ی and رود + ی: a tie keeps it
        ("ولایی", "و لایی"),  # ولا + یی, but لایی is a word itself
        ("یخ", None),  # no و
        ("و", None),
    ],
)
def test_glued_vav(word, fixed):
    fix = glued_vav(word, LEX)
    assert (fix.replace if fix else None) == fixed


@pytest.mark.parametrize(
    ("word", "suffix", "fixed"),
    [
        ("نمایش", "های", "نمایش‌های"),
        ("پارچه", "ای", "پارچه‌ای"),  # ای after ه
        ("پودر", "های", "پودرهای"),  # no ZWNJ after ر
        ("کالا", "ها", "کالاها"),  # nor after ا
        ("نمایش", "ای", None),  # ای only after ه
        ("تن", "ها", None),  # تنها is a word of its own
        ("رنی", "ها", None),  # not a known word
    ],
)
def test_spaced_suffix(word, suffix, fixed):
    fix = spaced_suffix(word, suffix, LEX)
    assert (fix.replace if fix else None) == fixed


@pytest.mark.parametrize(
    ("word", "fixed"),
    [
        ("سالنهای", "سالن‌های"),
        ("سالنها", "سالن‌ها"),
        ("سیب‌زمینیها", "سیب‌زمینی‌ها"),  # the last piece of a ZWNJ compound
        ("وامهای", "وام‌های"),
        ("کالاها", None),  # no ZWNJ after ا
        ("تنها", None),  # hazm vouches for it as written
        ("وبهای", None),  # وب + های, or و + بهای
        ("سالن‌های", None),  # already right
    ],
)
def test_joined_plural(word, fixed):
    fix = joined_plural(word, LEX)
    assert (fix.replace if fix else None) == fixed


def test_word_passes_chain():
    """وسالنهای: glued_vav gives و سالنهای, then joined_plural سالن‌های."""
    assert _found((1383, "اجاره وسالنهای ورزشی")) == {"وسالنهای": "و سالنهای", "سالنهای": "سالن‌های"}


def test_spaced_suffix_after_a_glued_vav():
    """The pair rule reads the label as the word rules leave it: ونمایش های
    gives و نمایش (glued_vav) and نمایش‌های (spaced_suffix)."""
    assert _found((1383, "فیلم ونمایش های سینما")) == {"ونمایش": "و نمایش", "نمایش های": "نمایش‌های"}


def test_find_fixes_proposes_each_fix_once():
    df = find_fixes(
        _labels(
            (1383, "ماهی تازه ویخ زده"), (1384, "ماهی تازه ویخ زده"), (1384, "خلال ونخ دندان"), (1390, "وام")
        ),
        LEX,
    )
    assert df.columns == ["find", "replace", "kind", "evidence"]
    assert df.select("find", "replace", "kind").rows() == [
        ("ویخ", "و یخ", "glued_vav"),
        ("ونخ", "و نخ", "glued_vav"),
    ]


def test_protected_stretch_is_left_to_its_row():
    """Where a word row of spelling.csv matches, the rules leave it alone."""
    df = find_fixes(_labels((1383, "ماهی ویخ زده")), LEX, FixList([Fix("ویخ زده", "یخ‌زده")]))
    assert df.height == 0


# --- words.csv: the chain and the bookkeeping -------------------------------------


def _proposals(*rows):
    return pl.DataFrame(rows, schema=["find", "replace", "kind", "evidence"], orient="row")


def test_bookkeeping_counts_changed_descriptions():
    labels = _labels(
        (1383, "ماهی تازه ویخ زده"),
        (1384, "ماهی تازه ویخ زده"),
        (1384, "ویخ و ویخ"),  # twice in one label: one description
        (1390, "و یخ"),  # already right
    )
    found = _proposals(("ویخ", "و یخ", "glued_vav", "e"), ("ونخ", "و نخ", "glued_vav", "e"))
    df = words.bookkeeping(labels, found, FixList())
    assert df.columns == words.COLUMNS
    # ونخ matches nothing: dropped
    assert df.select("find", "uses", "years", "example").rows() == [
        ("ویخ", 3, "1383-1384", "ماهی تازه ویخ زده")
    ]


def test_bookkeeping_drops_a_fix_that_changes_nothing():
    """A fix blind to ZWNJs matches a text already right, but changes nothing."""
    found = _proposals(("آنها", "آن‌ها", "joined_plural", "e"))
    assert words.bookkeeping(_labels((1390, "آن‌ها")), found, FixList()).height == 0


def test_ordered_by_kind_then_longest_find():
    df = words.ordered(
        _proposals(("ab", "x", "compound", ""), ("abc", "x", "compound", ""), ("z", "x", "learned", ""))
    )
    assert df["find"].to_list() == ["z", "abc", "ab"]


def test_find_words_chains_the_finders(monkeypatch):
    """Each finder reads the labels as the fixes before it leave them; a find
    an earlier finder writes otherwise is left to it, one it writes alike stays."""
    seen = []

    def first(ctx):
        seen.append(ctx.labels["label"].to_list())
        return _proposals(
            ("انرژی درمانی", "انرژی‌درمانی", "learned", "a"),  # nothing to match yet
            ("یخ", "یخچال", "learned", "a"),
        )

    def second(ctx):
        seen.append(ctx.labels["label"].to_list())
        return _proposals(
            ("وانرژی", "و انرژی", "glued_vav", "b"),
            ("یخ", "برف", "glued_vav", "b"),  # the first writes it otherwise
        )

    def third(ctx):
        seen.append(ctx.labels["label"].to_list())
        return _proposals(("انرژی درمانی", "انرژی‌درمانی", "compound", "c"))  # made by the second

    monkeypatch.setattr(words, "FINDERS", (("first", first), ("second", second), ("third", third)))
    labels = _labels((1383, "طب وانرژی درمانی"), (1384, "یخ"))
    df = words.find_words(labels, pl.DataFrame(), LEX, FixList(), FixList())
    # the labels are fixed as the build fixes them, until they stop changing: the
    # first finder's انرژی درمانی meets the text the second's وانرژی makes
    assert seen[:3] == [
        ["طب وانرژی درمانی", "یخ"],
        ["طب وانرژی درمانی", "یخچال"],
        ["طب و انرژی‌درمانی", "یخچال"],
    ]
    assert df.select("find", "kind", "uses").rows() == [
        ("یخ", "learned", 1),
        ("وانرژی", "glued_vav", 1),
        ("انرژی درمانی", "compound", 1),
    ]  # the third finder's row, after وانرژی, changes it first: the learned one, and every repeat, go


def test_a_spaced_suffix_crosses_a_hand_decision():
    guard = FixList([Fix("سی دی", "سی دی")])
    fixes = FixList([Fix("دی", "D", kind="compound"), Fix("سی دی های", "سی دی‌های", kind="spaced_suffix")])
    assert fixes.apply("انواع سی دی های نو", 0, None, guard) == "انواع سی دی‌های نو"


def test_write_and_read(tmp_path):
    path = tmp_path / "words.csv"
    labels = _labels((1383, "ماهی ویخ زده"))
    df = words.bookkeeping(labels, find_fixes(labels, LEX), FixList())
    csv_io.write_frame(df.with_columns(pl.col("uses").cast(pl.String)), path)
    assert csv_io.read(path)[0] | {"evidence": ""} == {
        "find": "ویخ",
        "replace": "و یخ",
        "kind": "glued_vav",
        "uses": "1",
        "years": "1383",
        "evidence": "",
        "example": "ماهی ویخ زده",
    }
    (fx,) = read_words(path)
    assert (fx.find, fx.replace, fx.match, fx.kind) == ("ویخ", "و یخ", "word", "glued_vav")


def test_automatic_fixes_are_up_to_date():
    """canonical.csv and words.csv are what the finders make now (and so what
    a second run makes); if this fails, run `uv run hiesir-codebook autocorrect`."""
    if not (hazm_data.HAZM_DIR / "words.dat").exists():
        pytest.skip("hazm data not downloaded (uv run hiesir-codebook hazm download)")
    groups, found = words.find_all()
    folder = ROOT / "output" / "2_corrected" / "autocorrect"
    assert groups.rows() == csv_io.read_frame(folder / "canonical.csv").rows()
    found = found.with_columns(pl.col("uses").cast(pl.String))
    assert found.rows() == csv_io.read_frame(folder / "words.csv").rows()


# --- the lexicon -------------------------------------------------------------------


def test_curated_words_need_a_reason(tmp_path):
    path = tmp_path / "words.csv"
    csv_io.write(path, ["word", "reason"], [{"word": "والک", "reason": ""}])
    with pytest.raises(ValueError, match="reason"):
        load_words(path)


def test_verb_forms():
    forms = set(verb_forms(pl.DataFrame({"past": ["کرد", ""], "present": ["کن", "هست"]})))
    assert {"کرد", "نکردند", "کرده", "کرده‌است", "می‌کند", "نمی‌کنم", "بکنند", "کننده"} <= forms
    assert {"هستم", "می‌هستد"} <= forms  # a verb with no past stem still gives its present forms
    assert "است" in forms  # the verb to be
    assert not any(f.startswith("ب") and f.endswith("کرد") for f in forms)  # no subjunctive of the past


def test_lexicon_keeps_the_highest_count():
    lex = Lexicon.from_table(
        pl.DataFrame({"word": ["آب", "آب", "اب"], "freq": [5, 9, 0], "vouched": [False, True, False]})
    )
    assert (lex.count("آب"), lex.known("آب"), lex.known("اب"), lex.listed("اب")) == (9, True, False, True)


# --- glued_words: the cutter ---------------------------------------------------

CUT_LEX = Lexicon.of(
    freq={
        "پودر": 24000151,
        "پیاز": 5000000,
        "لباس": 4270916,
        "زیر": 90000000,
        "اطو": 200000,
        "کش": 2740051,
        "کشی": 0,
        "ترک": 3471389,
        "بند": 39900928,
        "مؤسسات": 900000,
    },
    words={"پودر", "پیاز", "لباس", "زیر", "اطو", "کش", "ترک", "بند", "مؤسسات"},
    stems={"کش", "بند"},
)


def _cutter(*labels):
    return autocorrect.Cutter(CUT_LEX, autocorrect.Labels.of(labels))


def test_glued_words_cuts_two_common_words():
    fix = autocorrect.glued_words("پودرپیاز", CUT_LEX, _cutter("ادویه، پودرپیاز"))
    assert fix.replace == "پودر پیاز"


def test_glued_words_keeps_a_compound_with_a_verb_stem():
    """اطو + کشی and ترک + بند are compounds (کش, بند are present stems)."""
    cutter = _cutter("اطوکشی", "ترکبند")
    assert autocorrect.glued_words("اطوکشی", CUT_LEX, cutter) is None
    assert autocorrect.glued_words("ترکبند", CUT_LEX, cutter) is None


def test_lookups_ignore_hamza():
    assert CUT_LEX.known("موسسات")  # hazm writes مؤسسات


def test_labels_count_and_see_whatever_the_letter_forms():
    labels = autocorrect.Labels.of(["سایر مؤسسات", "مؤسسات دولتی", "پودرپیاز"])
    assert labels.count("موسسات") == 2
    assert labels.seen("سایر موسسات")
    assert not labels.seen("پودر")  # whole words only


def test_parts_leave_a_matched_stretch_to_its_row():
    rows = FixList([Fix("سی دی", "سی دی")])
    assert rows.parts("انواع سی دی و نوار") == [("انواع ", True), ("سی دی", False), (" و نوار", True)]


# --- compound ---------------------------------------------------------------------

COMP_LEX = Lexicon.of(
    freq={
        "تخم": 1,
        "مرغ": 1,
        "تخم‌مرغ": 1,
        "نمک": 1,
        "سود": 1,
        "نمک‌سود": 1,
        "پرداخت": 1,
        "شده": 1,
        "پرداخت‌شده": 1,
        "قابل": 1,
        "حمل": 1,
        "قابل‌حمل": 1,
    },
    words={"تخم‌مرغ", "نمک‌سود", "پرداخت‌شده", "قابل‌حمل"},
)


@pytest.mark.parametrize(
    ("a", "b", "fixed"),
    [
        ("تخم", "مرغ", "تخم‌مرغ"),  # hazm lists it, the labels write it joined
        ("نمک", "سود", "نمک‌سود"),  # hazm lists it, though the labels always write it apart
        ("پرداخت", "شده", None),  # a verb phrase
        ("قابل", "حمل", None),  # a head the house style writes apart
    ],
)
def test_compound(a, b, fixed):
    labels = autocorrect.Labels.of(["تخم مرغ", "تخم‌مرغ محلی", "نمک سود", "پرداخت شده", "قابل حمل"])
    fix = autocorrect.compound(a, b, COMP_LEX, labels)
    assert (fix.replace if fix else None) == fixed


def test_compound_written_joined_only_where_the_labels_join_it():
    lex = Lexicon.of(
        freq={"زرد": 1, "آلو": 1, "زردآلو": 9, "صورت": 1, "حساب": 1, "صورتحساب": 9},
        words={"زردآلو", "صورتحساب"},
    )
    labels = autocorrect.Labels.of(["زرد آلو", "برگه زردآلو", "صورت حساب"])
    assert autocorrect.compound("زرد", "آلو", lex, labels).replace == "زردآلو"
    assert autocorrect.compound("صورت", "حساب", lex, labels) is None  # never printed joined


# --- canonical: one wording per group ---------------------------------------------


def test_label_key_ignores_spacing_and_letter_forms():
    from hiesir_codebook.correction.text import label_key

    assert label_key("تختخواب و میز توالت") == label_key("تختخواب و میزتوالت")
    assert label_key("حق‌بیمه") == label_key("حق بیمه")
    assert label_key("موسسات و . .") == label_key("مؤسسات و ...")
    assert label_key("تخم مرغ") != label_key("تخم مرغ محلی")


def test_label_key_ignores_list_separators_and_etc():
    from hiesir_codebook.correction.text import label_key

    one = label_key("هزینه لوله‌کشی آب و نصب کنتور و سایر هزینه‌های مربوط به آن")
    assert one == label_key("هزینه لوله‌کشی آب، نصب کنتور و سایر هزینه‌های مربوط به آن")
    assert label_key("ماشین اصلاح سروصورت") == label_key("ماشین اصلاح سر و صورت")  # a glued و too
    assert label_key("لباس، کفش و غیره") == label_key("لباس، کفش ...") == label_key("لباس، کفش")
    assert label_key("انواع گوشت") != label_key("گوشت")  # a word, not a separator


def test_label_key_on_a_column_agrees():
    from hiesir_codebook.correction.text import label_key, label_key_expr

    texts = ["موسسات و . .", "حق‌بیمه  ة", "يك،ك,ـ"]
    assert pl.DataFrame({"t": texts}).select(label_key_expr("t"))["t"].to_list() == [
        label_key(t) for t in texts
    ]


LABELS = pl.DataFrame(
    {
        "year": [1403] * 17 + [1385] * 9 + [1390],
        "description": ["میزتوالت"] * 17 + ["میز توالت"] * 9 + ["مبل"],
    }
)


def _variants(finish=lambda t: t):
    variants = canonical.variant_groups(LABELS)
    return variants.with_columns(
        pl.col("label").map_elements(finish, return_dtype=pl.String).alias("finished")
    )


def test_variant_groups_hold_labels_written_several_ways():
    groups = canonical.variant_groups(LABELS).sort("label")
    assert groups.select("label", "n", "years").rows() == [("میز توالت", 9, [1385]), ("میزتوالت", 17, [1403])]


def test_canonical_gives_a_group_its_best_finished_form():
    lex = Lexicon.of(freq={"میز": 1, "توالت": 1}, words={"میز", "توالت"})
    # fewer unknown words beats more prints
    rows = canonical.choose_wordings(_variants(), lex)
    assert rows.select("find", "replace", "uses", "years").rows() == [("میزتوالت", "میز توالت", "17", "1403")]
    assert rows["evidence"][0] == "unknown words: 1 (میزتوالت) against 0; printed 17 times against 9"
    # judged by what the later steps make of it: both finish alike, so the commoner
    # wins, and every other variant takes it as printed (the steps then fix it)
    rows = canonical.choose_wordings(_variants(lambda t: "میز توالت"), lex)
    assert rows.select("find", "replace").rows() == [("میز توالت", "میزتوالت")]
    assert rows["evidence"][0].endswith("printed 9 times against 17")


def test_trace_runs_each_distinct_label_once(monkeypatch):
    from hiesir_codebook.correction import correct

    calls = []

    def upper(text):
        calls.append(text)
        return text.upper()

    monkeypatch.setattr(correct, "house_style", upper)
    labels = pl.DataFrame({"year": [1383, 1384, 1385, 1386], "description": ["a", "a", "b", "a"]})
    df = correct.trace(labels, Fixes(), upto="house_style")
    assert df["house_style"].to_list() == ["A", "A", "B", "A"]
    assert sorted(calls) == ["a", "b"]


def test_trace_gives_a_column_per_step():
    from hiesir_codebook.correction.correct import STEPS, trace

    fixes = Fixes(
        variants={"تختخواب و میزتوالت": "تختخواب و میز توالت"},
        letters=FixList([Fix("تزئین", "تزیین", "text")]),
        spelling=FixList([Fix("بجز", "به جز", years=frozenset({1390}))]),
    )
    labels = pl.DataFrame(
        {"year": [1390, 1383, 1390], "description": ["تختخواب و میزتوالت", "تزئین ،بجز", "تزئین ،بجز"]}
    )
    df = trace(labels, fixes)
    assert df.columns == ["year", "description", *[c for s in STEPS for c in (s, f"{s}_hits")]]
    assert df["canonical"][0] == "تختخواب و میز توالت"
    assert df["house_style"][1] == "تزئین، بجز"
    assert df["spelling"].to_list() == ["تختخواب و میز توالت", "تزیین، بجز", "تزیین، به جز"]  # بجز: 1390 only
    assert df["spelling_hits"].to_list() == [[], [], ["بجز"]]


def test_aligned_pieces_teach_word_fixes():
    assert canonical.aligned_pieces(
        "انواع ژنراتور، ترانسفورماتورو انواع وسائل مشابه", "انواع ژنراتور، ترانسفورماتور و انواع وسایل مشابه"
    ) == [("ترانسفورماتورو", "ترانسفورماتور و"), ("وسائل", "وسایل")]
    assert canonical.aligned_pieces("تختخواب و میزتوالت", "تختخواب و میز توالت") == [
        ("میزتوالت", "میز توالت")
    ]
    assert canonical.aligned_pieces("نان", "نام") == []  # other letters: nothing to learn


def test_learned_fixes_keep_one_way_and_leave_letters_to_folding():
    pairs = pl.DataFrame(
        [
            ("بی دوام و کم دوام", "بی‌دوام و کم دوام", 5),  # بی دوام -> بی‌دوام, 5 uses
            ("بی‌دوام", "بی دوام", 1),  # the other way, 1 use: dropped
            ("وسائل", "ویدیؤ", 1),  # other letters: nothing
            ("ویدیؤ", "ویدیو", 3),  # letter forms only: the folded fixes decide
        ],
        schema=["loser", "winner", "n"],
        orient="row",
    )
    rows = canonical.learned_fixes(pairs)
    assert rows.select("find", "replace", "kind").rows() == [("بی دوام", "بی‌دوام", "learned")]


def test_learned_fixes_need_agreement():
    pairs = pl.DataFrame(
        [
            ("میزتوالت", "میز توالت", 2),
            ("میزتوالت", "میز‌توالت", 1),
            ("کیفپول", "کیف پول", 1),
            ("کیفپول", "کیف‌پول", 1),
        ],
        schema=["loser", "winner", "n"],
        orient="row",
    )
    rows = canonical.learned_fixes(pairs)
    assert rows.select("find", "replace", "evidence").rows() == [
        ("میزتوالت", "میز توالت", "a group's winner writes it so; also میز‌توالت 1")
    ]  # 2 of 3 agree; کیفپول splits 1 to 1


def test_folded_fixes_follow_the_house_spelling():
    lex = Lexicon.of(freq={"دائره": 1, "اعضاء": 1}, words={"دائره", "اعضاء"})
    texts = pl.Series(["دائره دایره دایره", "اعضاء اعضا", "دکمه تزئینی", "سنگ‌های تزیینی", "آینه"])
    rows = canonical.folded_fixes(texts, lex)
    assert sorted(rows.select("find", "replace").rows()) == [
        ("اعضاء", "اعضا"),
        ("تزئینی", "تزیینی"),  # ئی / یی after a consonant: the house style leaves it
        ("دائره", "دایره"),
    ]
    # a form a hand row rewrites is never chosen
    hand = FixList([Fix("دایره", "دائره")])
    rows = canonical.folded_fixes(pl.Series(["دائره دایره"]), lex, hand)
    assert rows.select("find", "replace").rows() == [("دایره", "دائره")]


# --- variants: one word an item prints two ways ------------------------------------


@pytest.mark.parametrize(
    ("a", "b", "same"),
    [
        ("ذغال", "زغال", True),  # a letter changed, at the start
        ("برآورد", "براورد", True),
        ("بجز", "به جز", True),  # a ه added inside
        ("جابجایی", "جابه‌جایی", True),
        ("پینگ‌پونگ", "پینگ‌پنگ", True),  # a و dropped inside
        ("آینه", "آئینه", True),  # a hamza seat
        ("جا به جایی", "جابه‌جایی", True),  # spacing only
        ("شور", "شوی", False),  # changed at the end: another word
        ("تأتر", "تئاتر", True),  # hamza written otherwise
        ("کروات", "کراوات", True),  # an ا in a rare word
        ("کتاب", "کتب", False),  # an ا between two common words: a broken plural
        ("مجلس", "مجالس", False),
        ("لباس", "لباسی", False),  # added at the end
        ("اثاثه و", "اثاث و", False),  # a و alone hides where the word ends
        ("ته‌گرد و", "ته گردو", False),
        ("دولتی", "خصوصی", False),
    ],
)
def test_variant(a, b, same):
    from hiesir_codebook.correction.variants import variant

    lex = Lexicon.of(freq={"کتاب": 13_000_000, "کتب": 1_200_000, "مجلس": 7_000_000, "مجالس": 2_600_000})
    assert variant(a, b, lex) is same


def _variant_labels(*rows):
    return pl.DataFrame(rows, schema={"year": pl.Int64, "key": pl.String, "label": pl.String}, orient="row")


def test_variant_fixes_take_hazm_when_it_leads_else_the_majority():
    from hiesir_codebook.correction.variants import variant_fixes

    lex = Lexicon.of(
        freq={"درآمد": 3_000_000, "درامد": 19, "جابجایی": 198, "جابه‌جایی": 103, "مالیات": 1},
        words={"درآمد", "درامد", "جابجایی", "جابه‌جایی", "مالیات"},
    )
    labels = _variant_labels(
        (1385, "a", "مالیات بر درامد"),
        (1386, "a", "مالیات بر درآمد"),
        (1387, "a", "مالیات بر درامد"),
        (1385, "b", "خدمات جابجایی"),
        (1386, "b", "خدمات جابه‌جایی"),
        (1387, "b", "خدمات جابه‌جایی"),
    )
    found = variant_fixes(labels, FixList(), lex)
    assert sorted(found.select("find", "replace").rows()) == [
        ("جابجایی", "جابه‌جایی"),  # 198 to 103: no lead, so the labels' majority
        ("درامد", "درآمد"),  # hazm writes درآمد far more, though the labels print درامد more
    ]


def test_variant_fixes_never_choose_a_form_a_hand_row_rewrites():
    from hiesir_codebook.correction.variants import variant_fixes

    labels = _variant_labels((1385, "a", "ذغال سنگ"), (1386, "a", "زغال سنگ"), (1387, "a", "زغال سنگ"))
    found = variant_fixes(labels, FixList([Fix("زغال", "ذغال")]), Lexicon.of({}))
    assert found.select("find", "replace").rows() == [("زغال", "ذغال")]


def test_spacing_variants_take_the_form_hazm_lists_as_one_word():
    from hiesir_codebook.correction.variants import choose

    lex = Lexicon.of(freq={"جابه‌جایی": 103, "جا": 9, "به": 9, "جایی": 9}, words={"جابه‌جایی"})
    forms = ["جا به جایی", "جابه‌جایی"]
    assert choose(forms, {"جا به جایی": 9, "جابه‌جایی": 1}, dict.fromkeys(forms, 1386), lex) == "جابه‌جایی"


def test_settle_applies_a_list_until_the_text_stops_changing():
    fixes = FixList([Fix("بجز", "به جز", kind="variant"), Fix("بجزروانی", "بجز روانی", kind="glued_words")])
    assert fixes.apply("کلینیک (بجزروانی)") == "کلینیک (بجز روانی)"
    assert fixes.settle("کلینیک (بجزروانی)") == "کلینیک (به جز روانی)"


def test_labels_either_counts_words_respelled_but_not_words_cut_apart():
    printed = pl.Series(["بجز کره", "بجز غوره", "بجز روغن", "بجز شیر", "شیره ونظایر", "خرما ونظایر"] * 1)
    now = pl.Series(["به جز کره", "به جز غوره", "به جز روغن", "به جز شیر", "شیره و نظایر", "خرما و نظایر"])
    words_ = autocorrect.Labels.either(printed, now, glued=["ونظایر"])
    assert words_.count("بجز") == 4  # respelled elsewhere: still a word
    assert words_.count("ونظایر") == 0  # only و + نظایر, cut apart
    assert words_.seen("و نظایر") and not words_.seen("خرما ونظایر")  # phrases as they read now
