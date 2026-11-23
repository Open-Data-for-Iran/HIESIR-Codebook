"""The house style every description gets, with no word list: the
``house_style`` step of :mod:`.correct`, after the canonical wording and
before the letter, automatic and spelling fixes.  :func:`house_style` runs
the rules in order:

- :func:`tidy_punctuation`: the same punctuation spacing everywhere
- :func:`standard_spelling`: the Academy's spelling rules that need no word list

A rule replaces a list of words: add one here when a pattern, not a word,
is what is wrong.
"""

from __future__ import annotations

import re

from ..utils import ZWNJ, collapse_whitespace


def house_style(text: str) -> str:
    """Punctuation spacing, then the spelling rules that need no word list."""
    return standard_spelling(tidy_punctuation(text))


_OPENING = re.escape("([«")
_CLOSING = re.escape(")]»")
_MARKS = "،؛:؟!"  # marks that attach to the word before them
_PERSIAN_LETTER = "ء-يپچژکگی"  # ء-ي and پ چ ژ ک گ ی


def tidy_punctuation(s: str) -> str:
    """Persian punctuation spacing.

    - a Latin comma between words becomes "،" (not inside numbers: 1,000)
    - a mark repeated is written once: "دیس،، کتری" -> "دیس، کتری"
    - the conjunction و is a separate word: "وسایل‌و لوازم" -> "وسایل و لوازم"
    - "،", "؛", ":", "؟", "!" attach to the word before them and are followed
      by one space: "آرد ، رشته ،غلات" -> "آرد، رشته، غلات"
    - an opening bracket has one space before it and none after; a closing
      bracket has none before it and one space after (unless punctuation
      follows): "نان ماشینی( لواش )سنگک" -> "نان ماشینی (لواش) سنگک"
    - two or more dots, spaced or not, become "..." with a space before it
      (not after an opening bracket) and before a following word:
      "و.." / "و. . ." -> "و ...", "و...وسایر" -> "و ... وسایر"
    - a lone dot is never a full stop in the labels: after و it is an
      ellipsis cut short ("ختنه اطفال و.)" -> "ختنه اطفال و ...)"), between
      two words it joins a separator ("نوارقلب.نوارمغز" -> "نوارقلب، نوارمغز"),
      anywhere else it goes ("کاکائو. و" -> "کاکائو و", "نشده است." ->
      "نشده است"); a dot next to a digit or a Latin letter stays
    - a Persian word and a number are separated by a space:
      "در12ماه" -> "در 12 ماه", "پژو405" -> "پژو 405" (Latin "MP3" stays)
    - a slash between words has a space on each side:
      "دبیرستان/ متوسطه" -> "دبیرستان / متوسطه" (not between digits: 1/2)
    - a hyphen between words spaced on one side only loses the space:
      "سمعی- بصری" -> "سمعی-بصری" (spaced on both sides it stays: a dash)
    - runs of spaces collapse to one

    A colon or comma between digits ("10:30", "1,000") is left alone.
    """
    s = re.sub(r"(?<!\d),|,(?!\d)", "،", s)
    s = re.sub(rf"([{_MARKS}])(?:\s*\1)+", r"\1", s)  # "دیس،،" -> "دیس،"
    s = re.sub(rf"{ZWNJ}و(?=\s|$)", " و", s)  # "وسایل‌و لوازم" -> "وسایل و لوازم"
    s = re.sub(r"\.(?:\s*\.)+", "...", s)
    # a lone dot is never a full stop in the labels: after و it is an ellipsis
    # cut short, between two words joined by it a separator, else a stray mark
    s = re.sub(r"(?:^|(?<=[\s(،]))و\s*\.(?!\.)", "و ...", s)
    s = re.sub(rf"(?<=[{_PERSIAN_LETTER}])\.(?=[{_PERSIAN_LETTER}])", "، ", s)
    s = re.sub(r"(?<![.\dA-Za-z])\.(?![.\dA-Za-z])", "", s)
    s = re.sub(rf"\.\.\.(?=[{_PERSIAN_LETTER}])", "... ", s)
    s = re.sub(rf"(?<=[^\s{_OPENING}])\.\.\.", " ...", s)
    s = re.sub(rf"(?<=[{_PERSIAN_LETTER}])(?=\d)|(?<=\d)(?=[{_PERSIAN_LETTER}])", " ", s)
    s = re.sub(r"\s*(?<!\d)/(?!\d)\s*", " / ", s)
    # a hyphen spaced on one side only joins the words: "سمعی- بصری" -> "سمعی-بصری"
    s = re.sub(rf"(?<=[{_PERSIAN_LETTER}])-\s+(?=[{_PERSIAN_LETTER}])", "-", s)
    s = re.sub(rf"(?<=[{_PERSIAN_LETTER}])\s+-(?=[{_PERSIAN_LETTER}])", "-", s)
    s = re.sub(rf"\s*((?<!\d)[{_MARKS}]|[{_MARKS}](?!\d))\s*", r"\1 ", s)
    s = re.sub(rf"([{_OPENING}])\s+", r"\1", s)
    s = re.sub(rf"\s+([{_CLOSING}])", r"\1", s)
    s = re.sub(rf"(?<=[^\s{_OPENING}])([{_OPENING}])", r" \1", s)
    s = re.sub(rf"([{_CLOSING}])(?=[^\s{_CLOSING}{_MARKS}.])", r"\1 ", s)
    s = re.sub(rf"\s+([{_CLOSING}{_MARKS}])", r"\1", s)  # "آشپز، )" -> "آشپز،)"
    return collapse_whitespace(s)


# the suffix ی after ا / و, at the end of a word or before ان / ها (but not in
# a loanword such as گازوئیل, موزائیک, where more letters follow)
_SUFFIX_YE = re.compile(rf"(?<=[{_PERSIAN_LETTER}][اآو])ئی(?=(?:ان|ها|های|هایی)?(?![{_PERSIAN_LETTER}]))")
# ای after ه, misprinted ائی or ایی and set apart (پارچه ائی, مسابقه ایی)
_SUFFIX_HE_YE = re.compile(rf"(?<=[{_PERSIAN_LETTER}]ه)[ {ZWNJ}](?:ائی|ایی)(?![{_PERSIAN_LETTER}])")
# the prefix می / نمی set apart from its verb
_PREFIX_MI = re.compile(rf"(?<![{_PERSIAN_LETTER}{ZWNJ}])(ن?می) (?=[{_PERSIAN_LETTER}])")


# harakat: fatha, damma, kasra, shadda, sukun (tanwin, ً, stays: قبلاً)
_HARAKAT = re.compile("[\u064e-\u0652]")


def standard_spelling(s: str) -> str:
    """Spelling rules of the Academy of Persian Language and Literature that
    need no word list.

    - the suffix ی after a vowel is written یی, not ئی: "دمپائی" -> "دمپایی",
      "روستائیان" -> "روستاییان", "هوائی" -> "هوایی" (گازوئیل, ارائه stay)
    - ای after ه is joined with a ZWNJ, however it is misprinted: "پارچه ائی",
      "مسابقه ایی", "پارچه‌ایی" -> "پارچه‌ای", "مسابقه‌ای" (کالاهایی stays)
    - the prefix می / نمی takes a ZWNJ: "می شود" -> "می‌شود"
    - no harakat (fatha, damma, kasra, shadda, sukun), which the labels never
      need: "آّبرنگ" -> "آبرنگ"; tanwin stays ("قبلاً")
    """
    s = _HARAKAT.sub("", s)
    s = _SUFFIX_HE_YE.sub(f"{ZWNJ}ای", s)
    s = _PREFIX_MI.sub(rf"\1{ZWNJ}", s)
    return _SUFFIX_YE.sub("یی", s)
