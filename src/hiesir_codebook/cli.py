"""The ``hiesir-codebook`` command: every stage of the build, and the data it needs.

Each command is the ``main`` of its module, loaded only when it runs, so
``hiesir-codebook --help`` stays quick and a command imports only what it uses.
Their options come from the function's signature and its docstring.
"""

from __future__ import annotations

import sys
from pathlib import Path

from cyclopts import App, Group, Parameter

from . import DATA_DIR, EXTRACTED, SUPPORTED_YEARS


def _default(value: object) -> str | None:
    """A default as --help shows it: paths with /, as the documentation writes them."""
    if value is None or value is False:
        return None  # nothing to show: no value, or a flag left off
    return value.as_posix() if isinstance(value, Path) else str(value)


app = App(
    name="hiesir-codebook",
    help="The HIES questionnaires as a codebook: extracted, corrected, matched across years.",
    help_format="restructuredtext",
    version_flags=[],
    # a flag is just --flag (no --no-flag), a list just its values (no --empty-list)
    default_parameter=Parameter(negative=(), show_default=_default),
)

BUILD = Group("Build", sort_key=0)
STAGES = Group("Stages, in the order build runs them", sort_key=1)
WORDS = Group("Automatic fixes (need hazm's data; build reads what they write)", sort_key=2)
DATA = Group("Data", sort_key=3)


@app.command(group=BUILD)
def build(*, no_extract: bool = False, data: Path = DATA_DIR) -> None:
    """Regenerate every stage of output/, in order.

    extract (PDFs -> 1_extracted, skipped when the PDFs are not there) -> correct
    (-> 2_corrected) -> chains and relations (-> 3_items) -> groups (-> 4_groups)
    -> metrics (-> metrics.json).

    Parameters
    ----------
    no_extract
        Keep output/1_extracted/ as it is, do not read the PDFs.
    data
        The folder with pdf/.
    """
    from . import build_all

    build_all(data, extract_pdfs=not no_extract)


@app.command(group=STAGES, sort_key=0)
def extract(years: list[int] | None = None, *, data: Path = DATA_DIR, csv_dir: Path = EXTRACTED) -> None:
    """Extract the PDFs -> output/1_extracted/ (what each left out: reports/).

    Parameters
    ----------
    years
        Survey years (default: all supported).
    data
        The folder with pdf/.
    csv_dir
        Where the CSVs go.
    """
    from .extraction import build as build_year

    for y in years or SUPPORTED_YEARS:
        print(build_year(y, data, csv_dir), flush=True)


# (name, import path, group, the line --help shows: a lazy command is not
# imported to list it, so its docstring cannot give that line)
LAZY = [
    ("correct", "correction.correct:main", STAGES, "Apply curated/2_corrected/ -> output/2_corrected/."),
    ("check-structure", "correction.corrections:main", STAGES, "What must hold in every questionnaire CSV."),
    ("chains", "linking.chains:main", STAGES, "Matching stage 1: chains -> output/3_items/chains.csv."),
    ("relations", "linking.relations:main", STAGES, "Matching stage 2: links and relations between chains."),
    ("groups", "linking.groups:main", STAGES, "Group headers across years -> output/4_groups/."),
    ("metrics", "metrics:main", STAGES, "The figures of the build -> output/metrics.json."),
    ("autocorrect", "correction.words:main", WORDS, "Write canonical.csv and words.csv with hazm's words."),
    ("pdfs", "extraction.pdfs:cli", DATA, "Download, verify or list the questionnaire PDFs."),
    ("hazm", "hazm_data:cli", DATA, "Download, verify or list hazm's word list and data."),
    ("glyph-db", "extraction.build_glyph_db:main", DATA, "Rebuild the glyph database from good PDFs."),
]
for i, (name, path, group, short) in enumerate(LAZY, start=1):
    app.command(f"hiesir_codebook.{path}", name=name, group=group, help=short, sort_key=i)


def main(argv: list[str] | None = None) -> int:
    """Run the command line; returns the exit code of the command."""
    # the reports name Persian words: a Windows console's code page cannot show them
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    result = app(argv, result_action="return_int_as_exit_code_else_zero")
    return result if isinstance(result, int) else 0
