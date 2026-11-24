"""Correction step 1: the structure of each questionnaire.

``output/1_extracted/`` holds each questionnaire exactly as printed, typos
included.  ``curated/2_corrected/corrections.csv`` lists every deviation from
the print in codes, rows and sections, one row each, with the reason;
:func:`apply_corrections` applies them to a questionnaire read as a polars
table.  The descriptions then go through the label steps of :mod:`.correct`.

Columns of ``corrections.csv``:

========== ===================================================================
year       questionnaire year
action     ``recode``: set the expenditure code of an item
           ``retext``: set the description of an item
           ``delete``: remove an item (and group headers left without items)
           ``add_section``: copy a section missing from the PDF from another
           year (``description`` = section number, ``value`` = source year)
           ``recode_header`` / ``retext_header``: set the code / description
           of a group header (its level follows the new code)
expenditure_code  the item's code as printed (for a header: its code as in
                  ``1_extracted``, e.g. ``062 M`` or ``01121, 01122``)
description       the item's description as printed (identifies the row
                  when a code is printed twice)
value      the corrected code or description (empty for ``delete``)
reason     why: evidence from neighbouring years, the raw data, ...
========== ===================================================================

The structure check (:func:`check_structure`) says what must hold in every
questionnaire CSV, from the CSV alone (no PDFs or raw data, so it runs
everywhere, in CI too):

================ ============================================================
kind             what it finds
================ ============================================================
duplicate        an expenditure code printed twice
sub_order        a sub-code not above the one before it in the same code
section_order    a section heading out of order or repeated, or a row whose
                 section is below the row before it
empty            a header or item with no description
bad_code         an item whose ``expenditure_code`` is not its code digits
                 followed by a two-digit ``sub``
outside_header   an item that its header's code does not cover (0631 31
                 under the header 06312), unless
                 ``curated/2_corrected/header_exceptions.csv`` accepts it as
                 printed
================ ============================================================

The corrected questionnaires (``output/2_corrected/``) must have none: a test
checks it.  In ``output/1_extracted/`` the findings are the print errors that
``corrections.csv`` fixes (1386: 041211-041213 and 073611 printed twice, the
header 062 M; 1384: 102216), which a test checks too.

Against the code usage table (``data/code_usage.csv``),
:func:`verify` gives the evidence for each correction and
:func:`check_occurrence` the codes that households report but the
questionnaire lacks, or the reverse (``correct --check``).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import polars as pl

from .. import CORRECTED, CURATED_CORRECTED, SUPPORTED_YEARS, csv_io
from ..extraction.parse import LAST_OLD_SCHEME_YEAR, header_level
from ..usage import correct_codes, load_code_corrections, load_occurrence
from ..utils import collapse_whitespace, parse_years

CORRECTIONS = CURATED_CORRECTED / "corrections.csv"
HEADER_EXCEPTIONS = CURATED_CORRECTED / "header_exceptions.csv"
ACTIONS = ("recode", "retext", "delete", "add_section", "recode_header", "retext_header")
# where a row sits on its page: a section copied from another year has none
_BOX = ("page", "top", "bottom", "left", "right")


def read_questionnaire(folder: Path, year: int) -> pl.DataFrame:
    return csv_io.read_frame(folder / f"questionnaire_{year}.csv")


def _collapsed(column: str) -> pl.Expr:
    """:func:`collapse_whitespace` on a column."""
    return pl.col(column).str.replace_all(r"\s+", " ").str.strip_chars()


def _digits(column: str | pl.Expr) -> pl.Expr:
    col = pl.col(column) if isinstance(column, str) else column
    return col.str.replace_all(r"\D", "")


def _header_codes(column: str = "code") -> pl.Expr:
    """The codes a header covers, as digits: ``"01192, 01193"`` -> ``["01192", "01193"]``."""
    return pl.col(column).str.split(",").list.eval(_digits(pl.element()))


# --- corrections.csv -----------------------------------------------------------


@dataclass(frozen=True)
class Correction:
    year: int
    action: str
    expenditure_code: str
    description: str
    value: str
    reason: str


def load_corrections(path: Path = CORRECTIONS) -> list[Correction]:
    df = csv_io.read_frame(path)
    bad = df.filter(~pl.col("action").is_in(ACTIONS))
    if bad.height:
        raise ValueError(f"unknown action {bad['action'][0]!r} in {path}")
    out = [Correction(**{**r, "year": int(r["year"])}) for r in df.iter_rows(named=True)]
    for c in out:
        if not c.reason.strip():
            raise ValueError(f"correction without a reason: {c}")
    return out


def _target(rows: pl.DataFrame, c: Correction) -> pl.Series:
    """The one row ``c`` is about, as a mask: an item (a header for the
    ``_header`` actions) with its code, and its description when ``c`` gives one."""
    header = c.action.endswith("_header")
    match = (pl.col("kind") == ("header" if header else "item")) & (
        pl.col("code" if header else "expenditure_code") == c.expenditure_code
    )
    if c.description:
        match &= _collapsed("description") == collapse_whitespace(c.description)
    mask = rows.select(match.alias("hit")).to_series()
    if mask.sum() != 1:
        raise ValueError(f"{c.year} {c.action} {c.expenditure_code}: {mask.sum()} matching rows, expected 1")
    return mask


def _set(rows: pl.DataFrame, mask: pl.Series, **values: str) -> pl.DataFrame:
    return rows.with_columns(pl.when(mask).then(pl.lit(v)).otherwise(k).alias(k) for k, v in values.items())


def _delete(rows: pl.DataFrame, mask: pl.Series) -> pl.DataFrame:
    """``rows`` without the masked item, and without the group headers that
    covered it and now cover no item of its section."""
    gone = rows.filter(mask).row(0, named=True)
    rows = rows.filter(~mask)
    section = gone["section"]
    left = rows.filter((pl.col("kind") == "item") & (pl.col("section") == section))["expenditure_code"]
    # a header covers an item when the item's code starts with one of its codes
    prefixes = pl.Series([code[:k] for code in left for k in range(len(code) + 1)], dtype=pl.String)
    orphan = (
        (pl.col("kind") == "header")
        & (pl.col("section") == section)
        & _header_codes().list.eval(pl.lit(gone["expenditure_code"]).str.starts_with(pl.element())).list.any()
        & ~_header_codes().list.eval(pl.element().is_in(prefixes.implode())).list.any()
    )
    return rows.filter(~orphan)


def _add_section(rows: pl.DataFrame, c: Correction, extracted: Path) -> pl.DataFrame:
    """``rows`` with section ``c.description`` copied from the year ``c.value``
    (as printed), before the first section after it; the copy has no page."""
    section = c.description
    if (rows["section"] == section).any():
        raise ValueError(f"{c.year}: section {section} already present")
    added = (
        read_questionnaire(extracted, int(c.value))
        .filter(pl.col("section") == section)
        .with_columns(pl.lit("").alias(k) for k in _BOX)
    )
    after = rows["section"].cast(pl.Int64) > int(section)
    at = after.arg_true()[0] if after.any() else rows.height
    return pl.concat([rows[:at], added, rows[at:]], how="diagonal").fill_null("")


def apply_corrections(
    year: int, rows: pl.DataFrame, corrections: list[Correction], extracted: Path
) -> pl.DataFrame:
    """One questionnaire with that year's corrections applied, in order."""
    for c in corrections:
        if c.year != year:
            continue
        if c.action == "add_section":
            rows = _add_section(rows, c, extracted)
            continue
        mask = _target(rows, c)
        if c.action == "recode":
            rows = _set(rows, mask, expenditure_code=c.value, code=c.value[:-2], sub=c.value[-2:])
        elif c.action in ("retext", "retext_header"):
            rows = _set(rows, mask, description=c.value)
        elif c.action == "recode_header":
            level = header_level(c.value, year <= LAST_OLD_SCHEME_YEAR)
            rows = _set(rows, mask, code=c.value, level=str(level))
        elif c.action == "delete":
            rows = _delete(rows, mask)
    return rows


def corrected_questionnaires(
    years: Iterable[int], extracted: Path, corrections: list[Correction]
) -> pl.DataFrame:
    """Every year's questionnaire with its corrections, in one table with a
    ``year`` column, in year and row order."""
    return pl.concat(
        apply_corrections(y, read_questionnaire(extracted, y), corrections, extracted).with_columns(
            pl.lit(y).alias("year")
        )
        for y in years
    )


# --- the structure check and header_exceptions.csv ----------------------------


@dataclass(frozen=True)
class Finding:
    year: int
    kind: str
    code: str
    detail: str


@dataclass(frozen=True)
class HeaderException:
    header: str  # the header's code as in the CSV ("01192, 01193")
    item_code: str  # the item's code as in the CSV ("0119")
    years: frozenset[int] | None  # None: every year
    reason: str


def load_header_exceptions(path: Path = HEADER_EXCEPTIONS) -> list[HeaderException]:
    if not path.exists():
        return []
    df = csv_io.read_frame(path).with_columns(pl.col("header", "item_code").str.strip_chars())
    return [
        HeaderException(r["header"], r["item_code"], parse_years(r["years"]), r["reason"])
        for r in df.iter_rows(named=True)
    ]


def check_rows(
    year: int,
    rows: pl.DataFrame,
    exceptions: list[HeaderException],
    used: set[HeaderException] | None = None,
) -> list[Finding]:
    """The structure findings of one questionnaire.  The header exceptions
    that accepted something are added to ``used``."""
    rows = rows.with_columns(pl.col("section").cast(pl.Int64).alias("n_section"))
    items = rows.filter(pl.col("kind") == "item")
    out: list[Finding] = []

    def found(kind: str, df: pl.DataFrame, code: pl.Expr, detail: pl.Expr) -> None:
        out.extend(Finding(year, kind, c, d) for c, d in df.select(code, detail).iter_rows())

    dup = items.group_by("expenditure_code", maintain_order=True).len().filter(pl.col("len") > 1)
    found("duplicate", dup, pl.col("expenditure_code"), pl.format("printed {} times", "len"))

    number = r"^\d+$"
    prev = items.with_columns(pl.all().shift(1).name.suffix("_prev"))
    found(
        "sub_order",
        prev.filter(
            (pl.col("section") == pl.col("section_prev"))
            & (pl.col("code") == pl.col("code_prev"))
            & pl.col("sub").str.contains(number)
            & pl.col("sub_prev").str.contains(number)
            & (pl.col("sub").cast(pl.Int64, strict=False) <= pl.col("sub_prev").cast(pl.Int64, strict=False))
        ),
        pl.col("expenditure_code"),
        pl.format("after {}", "expenditure_code_prev"),
    )

    headings = rows.filter(pl.col("kind") == "section")["n_section"].to_list()
    if headings != sorted(set(headings)):
        out.append(Finding(year, "section_order", "", f"section headings {headings}"))
    either = pl.when(pl.col("expenditure_code") != "").then("expenditure_code").otherwise("code")
    found(
        "section_order",
        rows.filter(pl.col("n_section") < pl.col("n_section").shift(1)),
        either,
        pl.lit("below the row before"),
    )

    found(
        "empty",
        rows.filter((pl.col("kind") != "section") & (pl.col("description").str.strip_chars() == "")),
        either,
        pl.format("{} with no text", "kind"),
    )

    found(
        "bad_code",
        items.filter(
            ~pl.col("sub").str.contains(r"^\d{2}$")
            | (pl.col("expenditure_code") != pl.concat_str(_digits("code"), "sub"))
        ),
        pl.col("expenditure_code"),
        pl.format("code '{}' sub '{}'", "code", "sub"),
    )

    # each item with the header above it in its section: covered when its
    # code starts with one of the header's codes
    uncovered = (
        rows.with_row_index("i")
        .with_columns(
            pl.when(pl.col("kind") == "header")
            .then("code")
            .when(pl.col("kind") == "section")
            .then(pl.lit(""))
            .forward_fill()
            .alias("header")
        )
        .filter((pl.col("kind") == "item") & (pl.col("header").fill_null("") != ""))
        .with_columns(_header_codes("header").alias("covers"))
        .explode("covers")
        .group_by("i", maintain_order=True)
        .agg(
            pl.col("expenditure_code", "code", "header").first(),
            pl.col("expenditure_code").str.starts_with(pl.col("covers")).any().alias("covered"),
        )
        .filter(~pl.col("covered"))
    )
    for r in uncovered.iter_rows(named=True):
        accepted = next(
            (
                e
                for e in exceptions
                if e.header == r["header"]
                and e.item_code == r["code"]
                and (e.years is None or year in e.years)
            ),
            None,
        )
        if accepted is None:
            out.append(Finding(year, "outside_header", r["expenditure_code"], f"under header {r['header']}"))
        elif used is not None:
            used.add(accepted)
    return out


def check_structure(
    years: list[int],
    folder: Path,
    exceptions: list[HeaderException] | None = None,
    used: set[HeaderException] | None = None,
) -> list[Finding]:
    """The findings of every year's ``questionnaire_<year>.csv`` in ``folder``."""
    exc = load_header_exceptions() if exceptions is None else exceptions
    return [f for y in years for f in check_rows(y, read_questionnaire(folder, y), exc, used)]


# --- against the raw data --------------------------------------------------------


def check_occurrence(years: Iterable[int], corrected: Path, occurrence: Path, min_households: int = 5) -> int:
    """Print codes that disagree with the raw data; return the number of
    years with a code reported by households but missing from the
    questionnaire (the strong signal of a typo or an extraction miss)."""
    occ = correct_codes(load_occurrence(occurrence), load_code_corrections())
    bad = 0
    for year in years:
        if year not in occ:
            continue
        items = read_questionnaire(corrected, year).filter(pl.col("kind") == "item")
        codes = items["expenditure_code"].cast(pl.Int64)
        printed = set(codes)
        dup = sorted(codes.filter(codes.is_duplicated()).unique())
        # codes shorter than the 5-6 digit item codes are noise in the raw data
        invalid = sorted((c, n) for c, n in occ[year].items() if c < 10000)
        missing = sorted(
            (c, n) for c, n in occ[year].items() if c >= 10000 and c not in printed and n >= min_households
        )
        unused = sorted(c for c in printed if c not in occ[year])
        print(
            f"{year}: {items.height} items, {len(missing)} codes in the data but not printed, "
            f"{len(unused)} printed but not reported, {len(dup)} duplicated"
        )
        for c, n in missing:
            print(f"    in data, not printed: {c:06d} ({n} households)")
        for c in dup:
            print(f"    printed twice: {c:06d}")
        for c, n in invalid:
            print(f"    not an item code, ignored: {c} ({n} households)")
        bad += bool(missing or dup)
    return bad


def verify(corrections: list[Correction], extracted: Path, occurrence: Path) -> int:
    """Print the household evidence for each code-level correction; return
    the number that the raw data contradicts (a recode to a code nobody
    reports, a deleted or copied item that households do / do not report)."""
    occ = correct_codes(load_occurrence(occurrence), load_code_corrections())

    def n(year: int, code: str) -> int:
        return occ.get(year, {}).get(int(code), 0)

    bad = 0
    for c in corrections:
        if c.year not in occ:
            continue
        if c.action == "recode":
            ok = n(c.year, c.value) > 0
            print(
                f"{c.year} recode {c.expenditure_code} -> {c.value}: households "
                f"{n(c.year, c.expenditure_code)} -> {n(c.year, c.value)}"
                + ("" if ok else "  <-- not reported")
            )
        elif c.action == "delete":
            ok = n(c.year, c.expenditure_code) == 0
            print(
                f"{c.year} delete {c.expenditure_code}: {n(c.year, c.expenditure_code)} households"
                + ("" if ok else "  <-- reported")
            )
        elif c.action == "add_section":
            codes = (
                read_questionnaire(extracted, int(c.value))
                .filter((pl.col("section") == c.description) & (pl.col("kind") == "item"))["expenditure_code"]
                .to_list()
            )
            deleted = {d.expenditure_code for d in corrections if d.year == c.year and d.action == "delete"}
            unreported = [x for x in codes if n(c.year, x) == 0 and x not in deleted]
            ok = not unreported
            print(
                f"{c.year} add section {c.description} from {c.value}: "
                + ", ".join(f"{x} ({n(c.year, x)})" for x in codes)
                + ("" if ok else f"  <-- not reported: {' '.join(unreported)}")
            )
        else:
            continue
        bad += not ok
    return bad


def main(folder: Path = CORRECTED, *, exceptions: Path = HEADER_EXCEPTIONS) -> int:
    """Structure check: what must hold in every questionnaire CSV, from the CSV alone.

    Parameters
    ----------
    folder
        A folder of questionnaire CSVs.
    exceptions
        The accepted header exceptions.
    """
    accepted = load_header_exceptions(exceptions)
    used: set[HeaderException] = set()
    findings = check_structure(SUPPORTED_YEARS, folder, accepted, used)
    for f in findings:
        print(f"    {f.year} {f.kind:14} {f.code:8} {f.detail}")
    stale = [e for e in accepted if e not in used]
    for e in stale:
        print(f"    header exception that accepts nothing: {e.header} / {e.item_code}")
    print(
        f"structure check of {folder.as_posix()}: {len(findings)} findings"
        f" ({len(accepted)} accepted header exceptions, {len(stale)} stale)"
    )
    return 1 if findings or stale else 0
