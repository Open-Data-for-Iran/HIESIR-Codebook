"""The questionnaire PDFs: their names, sizes and hashes, and where to get them.

The PDFs are not in git. They are attached to the GitHub release
``questionnaires``; ``data/pdfs.csv`` (in git) lists each one with its size
and SHA-256, so a copy can be checked and a download verified.  In
``data/pdf/`` they keep the release's names: lower case, no spaces
(``questionnaire_1386.pdf``, ``questionnaire_1363_urban.pdf``).

    uv run hiesir-codebook pdfs download            # every PDF the list names, checked
    uv run hiesir-codebook pdfs download --extracted  # only the years that are extracted (small)
    uv run hiesir-codebook pdfs verify              # data/pdf/ against the list
    uv run hiesir-codebook pdfs list                # what data/pdf/ holds
    uv run hiesir-codebook pdfs manifest            # rewrite the list from data/pdf/ (after adding one)
    uv run hiesir-codebook pdfs rename              # old names ("Questionnaire 1386.pdf") -> release names

To add or replace a PDF: put it in ``data/pdf/`` under its release name, run
``pdfs manifest``, attach the file to the release (``gh release upload
questionnaires data/pdf/<name> --clobber``) and commit ``data/pdfs.csv``.
"""

from __future__ import annotations

import hashlib
import re
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from cyclopts import App

from .. import DATA_DIR, SUPPORTED_YEARS, csv_io

REPO = "Open-Data-for-Iran/HIESIR-Codebook"
RELEASE_TAG = "questionnaires"
RELEASE_URL = f"https://github.com/{REPO}/releases/download/{RELEASE_TAG}"
PDF_DIR = DATA_DIR / "pdf"
MANIFEST = DATA_DIR / "pdfs.csv"
MANIFEST_COLUMNS = ["name", "year", "area", "kind", "bytes", "sha256"]
RE_NAME = re.compile(r"^questionnaire[ _](\d{4})(?:[ _](urban|rural))?\.pdf$", re.IGNORECASE)


class PdfError(RuntimeError):
    """A PDF is missing, or differs from data/pdfs.csv."""


def published_name(year: int, area: str = "") -> str:
    return f"questionnaire_{year}{'_' + area if area else ''}.pdf"


# a text layer, left out of the codebook: the older 3+2 digit code scheme,
# which the matching across years does not cover
LEFT_OUT = (1382,)


def kind(year: int) -> str:
    """``extracted`` (in output/), ``text`` (a text layer, left out: 1382)
    or ``scan`` (image only)."""
    if year in SUPPORTED_YEARS:
        return "extracted"
    if year in LEFT_OUT:
        return "text"
    return "scan"


@dataclass(frozen=True)
class Pdf:
    year: int
    area: str  # "urban", "rural" or "" for one form covering both
    path: Path

    @property
    def name(self) -> str:
        """The release name."""
        return published_name(self.year, self.area)

    @property
    def kind(self) -> str:
        return kind(self.year)


@dataclass(frozen=True)
class Entry:
    """One row of data/pdfs.csv."""

    name: str
    year: int
    area: str
    bytes: int
    sha256: str

    @property
    def kind(self) -> str:
        return kind(self.year)


def find(folder: Path) -> list[Pdf]:
    """The questionnaire PDFs in ``folder``, under either naming, by year and area."""
    found = []
    for p in folder.glob("*.pdf") if folder.is_dir() else []:
        m = RE_NAME.match(p.name)
        if m:
            found.append(Pdf(int(m[1]), (m[2] or "").lower(), p))
    return sorted(found, key=lambda f: (f.year, f.area))


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def load_manifest(path: Path = MANIFEST) -> list[Entry]:
    return [
        Entry(r["name"], int(r["year"]), r["area"], int(r["bytes"]), r["sha256"]) for r in csv_io.read(path)
    ]


def write_manifest(folder: Path = PDF_DIR, path: Path = MANIFEST) -> list[Entry]:
    """List the PDFs in ``folder`` (release names only) with their size and hash."""
    entries = []
    for f in find(folder):
        if f.path.name != f.name:
            raise PdfError(f"{f.path.name}: not a release name (run `pdfs rename`)")
        entries.append(Entry(f.name, f.year, f.area, f.path.stat().st_size, sha256(f.path)))
    with csv_io.writer(path, MANIFEST_COLUMNS, bom=False) as w:
        for e in entries:
            w.writerow([e.name, e.year, e.area, e.kind, e.bytes, e.sha256])
    return entries


def check(entry: Entry, path: Path) -> str | None:
    """Why ``path`` is not the file the entry describes (None when it is)."""
    if not path.exists():
        return "missing"
    if path.stat().st_size != entry.bytes:
        return f"{path.stat().st_size} bytes, expected {entry.bytes}"
    if sha256(path) != entry.sha256:
        return "SHA-256 differs"
    return None


def verify(folder: Path = PDF_DIR, entries: list[Entry] | None = None) -> list[str]:
    """Problems with ``folder`` against the manifest: missing or different
    files, and questionnaire PDFs it does not list."""
    entries = load_manifest() if entries is None else entries
    problems = [f"{e.name}: {why}" for e in entries if (why := check(e, folder / e.name))]
    listed = {e.name for e in entries}
    problems += [f"{f.path.name}: not in the list" for f in find(folder) if f.path.name not in listed]
    return problems


def download(
    entries: list[Entry],
    folder: Path = PDF_DIR,
    base_url: str = RELEASE_URL,
    retries: int = 3,
    log=print,
) -> list[Path]:
    """Download the PDFs ``entries`` name from the release into ``folder``,
    skipping those already there and checking each one's size and hash.
    Raises PdfError when a download does not match the manifest."""
    folder.mkdir(parents=True, exist_ok=True)
    fetched = []
    for e in entries:
        dst = folder / e.name
        if check(e, dst) is None:
            continue
        part = dst.with_name(dst.name + ".part")
        for attempt in range(1, retries + 1):
            try:
                with urllib.request.urlopen(f"{base_url}/{e.name}", timeout=60) as r, open(part, "wb") as f:
                    while block := r.read(1 << 20):
                        f.write(block)
                break
            except OSError as err:
                if attempt == retries:
                    part.unlink(missing_ok=True)
                    raise PdfError(f"{e.name}: download failed ({err})") from err
                time.sleep(2 * attempt)
        why = check(e, part)
        if why:
            part.unlink()
            raise PdfError(f"{e.name}: the download does not match data/pdfs.csv ({why})")
        part.replace(dst)
        fetched.append(dst)
        log(f"{e.name}  {e.bytes / 2**20:5.1f} MB")
    return fetched


def rename(folder: Path = PDF_DIR) -> list[tuple[Path, Path]]:
    """Give the PDFs in ``folder`` their release names (``Questionnaire 1386.pdf``
    -> ``questionnaire_1386.pdf``)."""
    done = []
    for f in find(folder):
        dst = folder / f.name
        if f.path.name == f.name:
            continue
        if dst.exists():
            raise PdfError(f"{f.path.name}: {f.name} is there already")
        f.path.rename(dst)
        done.append((f.path, dst))
    return done


cli = App(name="pdfs", help="Download, verify or list the questionnaire PDFs.")


@cli.command(name="download")
def download_command(
    years: list[int] | None = None, *, extracted: bool = False, dir: Path = PDF_DIR, manifest: Path = MANIFEST
) -> None:
    """Download the PDFs the list names, each checked against its size and SHA-256.

    Parameters
    ----------
    years
        Only these years.
    extracted
        Only the years that are extracted (small).
    dir
        Where the PDFs go.
    manifest
        The list of the PDFs.
    """
    entries = load_manifest(manifest)
    if years:
        entries = [e for e in entries if e.year in years]
    if extracted:
        entries = [e for e in entries if e.kind == "extracted"]
    fetched = download(entries, dir)
    print(f"{len(fetched)} downloaded, {len(entries) - len(fetched)} already there -> {dir.as_posix()}/")


@cli.command(name="verify")
def verify_command(*, dir: Path = PDF_DIR, manifest: Path = MANIFEST) -> int:
    """Check data/pdf/ against the list.

    Parameters
    ----------
    dir
        The folder of PDFs.
    manifest
        The list of the PDFs.
    """
    entries = load_manifest(manifest)
    problems = verify(dir, entries)
    for p in problems:
        print(f"    {p}")
    print(f"{len(entries)} PDFs listed, {len(problems)} problems in {dir.as_posix()}/")
    return 1 if problems else 0


@cli.command(name="list")
def list_command(*, dir: Path = PDF_DIR) -> None:
    """What data/pdf/ holds.

    Parameters
    ----------
    dir
        The folder of PDFs.
    """
    for f in find(dir):
        print(
            f"{f.year} {f.area or '-':5} {f.kind:10} {f.path.stat().st_size / 2**20:5.1f} MB  {f.path.name}"
        )


@cli.command(name="manifest")
def manifest_command(*, dir: Path = PDF_DIR, manifest: Path = MANIFEST) -> None:
    """Rewrite the list from data/pdf/ (after adding a PDF).

    Parameters
    ----------
    dir
        The folder of PDFs.
    manifest
        The list of the PDFs.
    """
    entries = write_manifest(dir, manifest)
    print(f"{len(entries)} PDFs ({sum(e.bytes for e in entries) / 2**20:.0f} MB) -> {manifest.as_posix()}")


@cli.command(name="rename")
def rename_command(*, dir: Path = PDF_DIR) -> None:
    """Old names ("Questionnaire 1386.pdf") -> release names.

    Parameters
    ----------
    dir
        The folder of PDFs.
    """
    for src, dst in rename(dir):
        print(f"{src.name} -> {dst.name}")
