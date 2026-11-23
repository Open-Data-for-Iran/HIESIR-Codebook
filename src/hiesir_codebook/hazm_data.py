"""hazm's data files: its Persian word list with frequencies, verbs, stopwords.

`hazm <https://github.com/roshan-research/hazm>`_ (MIT licence) ships plain
text resources inside its package, but the package needs Python 3.12 or
3.13.  The files themselves need nothing, so this module downloads them from
hazm's repository at a fixed release, checks each against the size and
SHA-256 listed here, and reads them without hazm installed.  They live in
``data/hazm/``, outside git.

    uv run hiesir-codebook hazm download   # the files listed below, checked
    uv run hiesir-codebook hazm verify     # data/hazm/ against the list
    uv run hiesir-codebook hazm list       # what each file holds

=================== ===========================================================
file                what it holds
=================== ===========================================================
words.dat           about 194,000 words, each with its frequency in hazm's corpus and
                    its parts of speech: ``آب<TAB>549005877<TAB>N,AJ``
verbs.dat           verb stems, past#present: ``آموخت#آموز``
stopwords.dat       function words, one per line
abbreviations.dat   abbreviations with their dots: ``ه.ش``
iwords.dat          informal word -> formal word: ``یه یک``
iverbs.dat          informal verb stems
=================== ===========================================================

To move to another hazm release: change ``HAZM_VERSION``, download the files,
and put their sizes and hashes in ``FILES`` (``hazm list`` prints them).
"""

from __future__ import annotations

import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import polars as pl
from cyclopts import App

from . import DATA_DIR
from .extraction.pdfs import sha256

HAZM_VERSION = "v0.12.1"
HAZM_URL = f"https://raw.githubusercontent.com/roshan-research/hazm/{HAZM_VERSION}/hazm/data"
HAZM_DIR = DATA_DIR / "hazm"


class HazmDataError(RuntimeError):
    """A hazm data file is missing, or differs from the list."""


@dataclass(frozen=True)
class DataFile:
    name: str
    bytes: int
    sha256: str
    what: str


FILES = (
    DataFile(
        "words.dat",
        3396078,
        "e9e212a774beb05c1bfe2fe7646d068e11e093f78696fc23fbbc2baa2b795fe1",
        "words with frequency and parts of speech",
    ),
    DataFile(
        "verbs.dat",
        13498,
        "37e07804cb52d2afe03ccb5484c6d5e4cd0595f3e4684f3d10df23d90c6ae4d6",
        "verb stems (past#present)",
    ),
    DataFile(
        "stopwords.dat",
        3664,
        "d68c35e2ebde04a2e229013bd04a0afa976939bff3cfdfe9e880a16dbfb14af6",
        "function words",
    ),
    DataFile(
        "abbreviations.dat",
        2210,
        "35560d5f2481936ccd66c092a6f61ec2532492b04eb433326e28c19a4bdd9f6a",
        "abbreviations",
    ),
    DataFile(
        "iwords.dat",
        7705,
        "748e1aaeda091481cdea05bd0daddb736c5ba6ce7c0f8f31501df3098b227f5f",
        "informal -> formal words",
    ),
    DataFile(
        "iverbs.dat",
        2131,
        "492d807e561d7c916160b4e91c826371e19aa4c9e87a64391434ce75a59f0429",
        "informal verb stems",
    ),
)


# --- getting the files -----------------------------------------------------------


def check(f: DataFile, path: Path) -> str | None:
    """Why ``path`` is not the listed file, or None when it is."""
    if not path.is_file():
        return "missing"
    size = path.stat().st_size
    if size != f.bytes:
        return f"{size} bytes, expected {f.bytes}"
    if sha256(path) != f.sha256:
        return "SHA-256 differs"
    return None


def verify(folder: Path = HAZM_DIR, files: tuple[DataFile, ...] = FILES) -> list[str]:
    """The problems of ``folder`` against the list (empty when all is well)."""
    return [f"{f.name}: {why}" for f in files if (why := check(f, folder / f.name))]


def download(
    folder: Path = HAZM_DIR,
    files: tuple[DataFile, ...] = FILES,
    base_url: str = HAZM_URL,
    retries: int = 3,
    log=print,
) -> list[Path]:
    """Download the listed files into ``folder``, skipping those already
    there and checking each one's size and hash.  Raises HazmDataError when
    a download fails or does not match the list."""
    folder.mkdir(parents=True, exist_ok=True)
    fetched = []
    for f in files:
        dst = folder / f.name
        if check(f, dst) is None:
            continue
        part = dst.with_name(dst.name + ".part")
        for attempt in range(1, retries + 1):
            try:
                with urllib.request.urlopen(f"{base_url}/{f.name}", timeout=60) as r, open(part, "wb") as out:
                    while block := r.read(1 << 20):
                        out.write(block)
                break
            except OSError as err:
                if attempt == retries:
                    part.unlink(missing_ok=True)
                    raise HazmDataError(f"{f.name}: download failed ({err})") from err
                time.sleep(2 * attempt)
        why = check(f, part)
        if why:
            part.unlink()
            raise HazmDataError(f"{f.name}: the download does not match the list ({why})")
        part.replace(dst)
        fetched.append(dst)
        log(f"{f.name}  {f.bytes / 2**10:7.0f} KB")
    return fetched


# --- reading them --------------------------------------------------------------


def _path(name: str, folder: Path) -> Path:
    path = folder / name
    if not path.is_file():
        raise HazmDataError(f"{path.as_posix()} is missing: run `uv run hiesir-codebook hazm download`")
    return path


def _lines(name: str, folder: Path) -> list[str]:
    with open(_path(name, folder), encoding="utf-8") as f:
        return [s for line in f if (s := line.strip())]


def words_frame(folder: Path = HAZM_DIR) -> pl.DataFrame:
    """``words.dat`` as a polars table: ``word``, ``freq`` (its frequency in
    hazm's corpus) and ``pos`` (its parts of speech, comma-separated, ``0``
    for none), every line that has all three."""
    return (
        pl.read_csv(
            _path("words.dat", folder),
            separator="\t",
            has_header=False,
            new_columns=["word", "freq", "pos"],
            quote_char=None,  # a word may hold a quote
            truncate_ragged_lines=True,
            schema_overrides={"word": pl.String, "freq": pl.String, "pos": pl.String},
        )
        .with_columns(pl.col(c).str.strip_chars() for c in ("word", "freq", "pos"))
        .filter(pl.col("word").is_not_null() & (pl.col("word") != "") & pl.col("pos").is_not_null())
        .with_columns(pl.col("freq").cast(pl.Int64))
    )


def words_list(folder: Path = HAZM_DIR) -> list[tuple[str, int, tuple[str, ...]]]:
    """``(word, frequency, parts of speech)`` for every word, as
    ``hazm.words_list()`` gives them: ``("آب", 549005877, ("N", "AJ"))``."""
    df = words_frame(folder)
    return [(w, n, tuple(p.split(","))) for w, n, p in df.iter_rows()]


def word_frequencies(folder: Path = HAZM_DIR) -> dict[str, int]:
    """Word -> frequency; a word listed twice keeps its higher count."""
    df = words_frame(folder).group_by("word").agg(pl.col("freq").max())
    return dict(zip(df["word"], df["freq"], strict=True))


def stopwords_list(folder: Path = HAZM_DIR) -> list[str]:
    """The function words, sorted (as ``hazm.stopwords_list()``)."""
    return sorted(set(_lines("stopwords.dat", folder)))


def verbs_list(folder: Path = HAZM_DIR) -> list[str]:
    """The verb stems, ``past#present`` (``آموخت#آموز``)."""
    return _lines("verbs.dat", folder)


cli = App(name="hazm", help="Download, verify or list hazm's word list and data.")


@cli.command(name="download")
def download_command(*, dir: Path = HAZM_DIR) -> int:
    """Download hazm's data files, each checked against its size and SHA-256.

    Parameters
    ----------
    dir
        Where the files go.
    """
    try:
        fetched = download(dir)
    except HazmDataError as e:
        print(e)
        return 1
    print(
        f"hazm {HAZM_VERSION}: {len(fetched)} downloaded, {len(FILES) - len(fetched)} already there"
        f" -> {dir.as_posix()}/"
    )
    return 0


@cli.command(name="verify")
def verify_command(*, dir: Path = HAZM_DIR) -> int:
    """Check data/hazm/ against the list.

    Parameters
    ----------
    dir
        The folder of hazm's files.
    """
    problems = verify(dir)
    for p in problems:
        print(f"    {p}")
    print(f"{len(FILES)} hazm files listed, {len(problems)} problems in {dir.as_posix()}/")
    return 1 if problems else 0


@cli.command(name="list")
def list_command(*, dir: Path = HAZM_DIR) -> None:
    """What each file holds, with its size, hash and state.

    Parameters
    ----------
    dir
        The folder of hazm's files.
    """
    for f in FILES:
        state = check(f, dir / f.name) or "ok"
        print(f"{f.name:18} {f.bytes:>9} bytes  {f.sha256}  {state:8} {f.what}")
    print(f"hazm {HAZM_VERSION}: {HAZM_URL}")
