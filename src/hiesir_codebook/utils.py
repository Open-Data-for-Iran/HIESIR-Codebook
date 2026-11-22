"""Persian text normalisation helpers.

Small, composable functions; the higher-level ones are built from the lower
ones so callers can pick exactly the steps they need:

- character level: :func:`unify_letters`, :func:`to_ascii_digits`,
  :func:`to_persian_digits`, :func:`strip_tatweel`, :func:`canonical`
- spacing: :func:`tidy_zwnj`, :func:`collapse_whitespace`
- full clean-up: :func:`normalize_persian`
- right-to-left visual text: :func:`mirror_brackets`, :func:`fix_ltr_runs`,
  :func:`visual_to_logical`, :func:`normalize_visual`
- comparison: :func:`loose_key`
- classification: :func:`has_persian`, :func:`has_letters`, :func:`joins_next`
"""

from __future__ import annotations

import re
import unicodedata

ZWNJ = "‌"  # zero-width non-joiner (نیم‌فاصله)
TATWEEL = "ـ"

PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
ARABIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"
ASCII_DIGITS = "0123456789"

#: regex fragment: an optional space or ZWNJ (e.g. "قسمت سوم" / "قسمت‌سوم")
OPT_SPACE = f"[ {ZWNJ}]?"
#: regex character class for Arabic-script characters
ARABIC_SCRIPT = "؀-ۿ"

_LETTERS = str.maketrans({"ي": "ی", "ى": "ی", "ك": "ک", "ە": "ه"})
_TO_ASCII = str.maketrans(PERSIAN_DIGITS + ARABIC_DIGITS, ASCII_DIGITS * 2)
_TO_PERSIAN = str.maketrans(ASCII_DIGITS + ARABIC_DIGITS, PERSIAN_DIGITS * 2)
_MIRROR = str.maketrans({"(": ")", ")": "(", "[": "]", "]": "[", "«": "»", "»": "«"})
_HAS_PERSIAN = re.compile(f"[{ARABIC_SCRIPT}]")
_HAS_LETTERS = re.compile(f"[{ARABIC_SCRIPT}A-Za-z]")
_LTR_RUN = re.compile(r"[A-Za-z0-9][A-Za-z0-9 .,:;/&+%\-]*[A-Za-z0-9]|[A-Za-z]")
_NUMBER = re.compile(r"\d+(?:[./]\d+)*")
_PUNCT = re.compile(rf"[\s{ZWNJ}()\[\]،,.\-:؛;«»\"'/]+")

# letters that connect to the following letter (dual-joining)
_DUAL_JOINING = frozenset("بپتثجچحخسشصضطظعغفقکگلمنهیئكي")


# --- character level ----------------------------------------------------------


def unify_letters(s: str) -> str:
    """Arabic letter variants -> Persian (ي ى -> ی, ك -> ک, ە -> ه)."""
    return s.translate(_LETTERS)


def to_ascii_digits(s: str) -> str:
    """Persian and Arabic-Indic digits -> 0-9."""
    return s.translate(_TO_ASCII)


def to_persian_digits(s: str) -> str:
    """0-9 and Arabic-Indic digits -> Persian digits (۰-۹)."""
    return s.translate(_TO_PERSIAN)


def strip_tatweel(s: str) -> str:
    return s.replace(TATWEEL, "")


def canonical(s: str) -> str:
    """Presentation forms -> base letters (NFKC) and unified Persian letters.

    Use it to compare characters regardless of how a font encoded them
    (e.g. 'ﺑ' == 'ب', 'ي' == 'ی').
    """
    return unify_letters(unicodedata.normalize("NFKC", s))


# --- spacing ------------------------------------------------------------------


def tidy_zwnj(s: str) -> str:
    """Collapse repeated ZWNJs; a ZWNJ next to a space becomes a plain space."""
    return re.sub(f" *{ZWNJ}+ *", lambda m: " " if " " in m.group(0) else ZWNJ, s)


def collapse_whitespace(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


# --- full clean-up ------------------------------------------------------------


def normalize_persian(s: str) -> str:
    """Canonical letters, ASCII digits, no tatweel, tidy spaces and ZWNJs."""
    s = strip_tatweel(to_ascii_digits(canonical(s)))
    return collapse_whitespace(tidy_zwnj(s))


# --- right-to-left visual text ------------------------------------------------


def mirror_brackets(s: str) -> str:
    """Swap ( ) [ ] « » — needed after reversing visual RTL text."""
    return s.translate(_MIRROR)


def fix_ltr_runs(s: str) -> str:
    """Re-reverse left-to-right runs inside text that was read right-to-left.

    Latin runs ("reyalP 4PM" -> "MP4 Player") are reversed as a whole; in
    pure number runs each number is reversed but their order stays RTL, so a
    code pair like "11 0111" keeps its reading order.
    """

    def fix(m: re.Match) -> str:
        run = m.group(0)
        if re.search(r"[A-Za-z]", run):
            return run[::-1]
        return _NUMBER.sub(lambda d: d.group(0)[::-1], run)

    return _LTR_RUN.sub(fix, s)


def visual_to_logical(s: str) -> str:
    """Bidi fix-up for a string whose characters were sorted right-to-left."""
    return fix_ltr_runs(mirror_brackets(s))


def normalize_visual(s: str) -> str:
    """Right-to-left-sorted glyph text -> clean logical Persian text."""
    s = strip_tatweel(to_ascii_digits(canonical(s)))
    s = visual_to_logical(s)
    return collapse_whitespace(tidy_zwnj(s))


# --- comparison ---------------------------------------------------------------


def loose_key(s: str) -> str:
    """Key for fuzzy equality: ignores spacing, ZWNJ, punctuation, hamza/madda,
    tatweel, presentation forms and digit style.

    'هزینه‌های (ریال)' and 'هزينه هاي ريال' get the same key.
    """
    s = strip_tatweel(to_ascii_digits(canonical(s)))
    s = s.translate(str.maketrans({"ؤ": "و", "أ": "ا", "إ": "ا", "آ": "ا", "ة": "ه"}))
    return _PUNCT.sub("", s)


_STOPWORDS = frozenset(
    ["و", "یا", "از", "به", "در", "با", "که", "را", "برای", "آن", "این", "آنها", "ها", "های", "انواع", "نوع"]
)


def words(s: str) -> list[str]:
    """Content words of a description, each reduced to its :func:`loose_key`.

    Splits on spaces, ZWNJ and punctuation and drops function words and
    generic qualifiers (و، از، انواع ...), which carry no item identity.
    """
    s = strip_tatweel(to_ascii_digits(canonical(s)))
    out = []
    for w in re.split(rf"[\s{ZWNJ}()\[\]،,.\-:؛;«»\"'/…]+", s):
        k = loose_key(w)
        if k and k not in _STOPWORDS:
            out.append(k)
    return out


# --- classification -----------------------------------------------------------


def has_persian(s: str) -> bool:
    return bool(_HAS_PERSIAN.search(s))


def has_letters(s: str) -> bool:
    """Contains a Persian/Arabic or Latin letter (not only digits/punctuation)."""
    return bool(_HAS_LETTERS.search(s))


def is_arabic_letter(ch: str) -> bool:
    return "ء" <= ch <= "ۿ"


def joins_next(ch: str) -> bool:
    """Does this letter connect to the following one (e.g. ب, س; not ا, د, ر)?"""
    return ch in _DUAL_JOINING


def parse_years(spec: str) -> frozenset[int] | None:
    """Years as written in the curated files: '' -> None (every year);
    '1383-1385 1390' (or with commas) -> {1383, 1384, 1385, 1390}."""
    if not spec.strip():
        return None
    out: set[int] = set()
    for part in re.split(r"[\s,]+", spec.strip()):
        lo, _, hi = part.partition("-")
        out.update(range(int(lo), int(hi or lo) + 1))
    return frozenset(out)
