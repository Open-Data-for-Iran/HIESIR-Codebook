"""Correction step 2: the house style every description gets, with no
word list.  :func:`house_style` runs the rules in order, after the
structure (:mod:`.corrections`, step 1) and before the automatic and
spelling fixes (:mod:`.autocorrect`, :mod:`.spelling`, steps 3 and 4):

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
    s = re.sub(rf"\s*((?<!\d)[{_MARKS}]|[{_MARKS}](?!\d))\s*", r"\1 ", s)
    s = re.sub(rf"([{_OPENING}])\s+", r"\1", s)
    s = re.sub(rf"\s+([{_CLOSING}])", r"\1", s)
    s = re.sub(rf"(?<=[^\s{_OPENING}])([{_OPENING}])", r" \1", s)
    s = re.sub(rf"([{_CLOSING}])(?=[^\s{_CLOSING}{_MARKS}.])", r"\1 ", s)
    s = re.sub(rf"\s+([{_CLOSING}{_MARKS}])", r"\1", s)  # "آشپز، )" -> "آشپز،)"
    return collapse_whitespace(s)


# the suffix ی after ا / و, at the end of a word or before ان / ها (but not in
# a loanword such as گازوئیل, موزائیک, where more letters follow)
_SUFFIX_YE = re.compile(
    rf"(?<=[{_PERSIAN_LETTER}][اآو])ئی(?=(?:ان|ها|های|هایی)?(?![{_PERSIAN_LETTER}]))"
)  # a lone "ائی" is ه + ای misprinted (پارچه ائی), left to the spelling fixes


def standard_spelling(s: str) -> str:
    """Spelling rules of the Academy of Persian Language and Literature that
    need no word list.

    - the suffix ی after a vowel is written یی, not ئی: "دمپائی" -> "دمپایی",
      "روستائیان" -> "روستاییان", "هوائی" -> "هوایی" (گازوئیل, ارائه stay)
    """
    return _SUFFIX_YE.sub("یی", s)
