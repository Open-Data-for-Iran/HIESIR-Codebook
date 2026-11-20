"""The questionnaire PDFs: their published names, and a list for the site.

The PDFs are not in git. They are attached to the GitHub release
``questionnaires``, and the documentation build publishes them under ``pdf/``.
Published names are lower case without spaces (GitHub turns spaces in release
file names into dots): ``Questionnaire 1363 Urban.pdf`` -> ``questionnaire_1363_urban.pdf``.

    uv run python -m hiesir_codebook.extraction.pdfs stage    # data/pdf -> data/release, renamed for upload
    uv run python -m hiesir_codebook.extraction.pdfs list     # what a folder holds
"""

from __future__ import annotations

import argparse
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from .. import DATA_DIR, SUPPORTED_YEARS

RELEASE_TAG = "questionnaires"
RE_NAME = re.compile(r"^questionnaire[ _](\d{4})(?:[ _](urban|rural))?\.pdf$", re.IGNORECASE)


@dataclass(frozen=True)
class Pdf:
    year: int
    area: str  # "urban", "rural" or "" for one form covering both
    path: Path

    @property
    def name(self) -> str:
        """The published file name."""
        return published_name(self.year, self.area)

    @property
    def kind(self) -> str:
        """``extracted`` (in output/), ``dictionary`` (1401) or ``scan`` (image only)."""
        if self.year in SUPPORTED_YEARS:
            return "extracted"
        return "dictionary" if self.year == 1401 else "scan"


def published_name(year: int, area: str = "") -> str:
    return f"questionnaire_{year}{'_' + area if area else ''}.pdf"


def find(folder: Path) -> list[Pdf]:
    """The questionnaire PDFs in ``folder``, under either naming, by year and area."""
    found = []
    for p in folder.glob("*.pdf") if folder.is_dir() else []:
        m = RE_NAME.match(p.name)
        if m:
            found.append(Pdf(int(m[1]), (m[2] or "").lower(), p))
    return sorted(found, key=lambda f: (f.year, f.area))


def stage(src: Path, dst: Path) -> list[Path]:
    """Copy the PDFs in ``src`` to ``dst`` under their published names."""
    dst.mkdir(parents=True, exist_ok=True)
    return [Path(shutil.copy2(f.path, dst / f.name)) for f in find(src)]


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(
        prog="python -m hiesir_codebook.extraction.pdfs",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("action", choices=["stage", "list"])
    ap.add_argument("--src", type=Path, default=DATA_DIR / "pdf")
    ap.add_argument("--dst", type=Path, default=DATA_DIR / "release")
    args = ap.parse_args(argv)
    if args.action == "list":
        for f in find(args.src):
            print(f"{f.year} {f.area or '-':5} {f.kind:10} {f.path.stat().st_size / 2**20:5.1f} MB  {f.name}")
        return
    copied = stage(args.src, args.dst)
    size = sum(p.stat().st_size for p in copied) / 2**20
    print(
        f"{len(copied)} PDFs ({size:.0f} MB) -> {args.dst.as_posix()}; attach them to the "
        f"GitHub release '{RELEASE_TAG}'"
    )


if __name__ == "__main__":
    main()
