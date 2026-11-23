"""hazm's data files: download and check against the list, and read them.

The tests serve the files from a local folder (``file://``), so they need no
network; ``test_real_files`` checks data/hazm/ when it has been downloaded."""

import hashlib
from pathlib import Path

import pytest

from hiesir_codebook import hazm_data
from hiesir_codebook.hazm_data import DataFile, HazmDataError, check, download, verify

WORDS = "آب\t549005877\tN,AJ\nآبادان\t2911082\tN\nآب\t12\tN\nبد سطر\n"


def _spec(path: Path) -> DataFile:
    data = path.read_bytes()
    return DataFile(path.name, len(data), hashlib.sha256(data).hexdigest(), "test")


@pytest.fixture
def source(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "words.dat").write_text(WORDS, encoding="utf-8", newline="\n")
    (src / "stopwords.dat").write_text("و\nدر\nو\n\n", encoding="utf-8", newline="\n")
    return src


def test_download_checks_and_skips(source, tmp_path):
    files = tuple(_spec(p) for p in sorted(source.iterdir()))
    dst = tmp_path / "hazm"
    got = download(dst, files, source.as_uri(), log=lambda _: None)
    assert sorted(p.name for p in got) == ["stopwords.dat", "words.dat"]
    assert verify(dst, files) == []
    assert download(dst, files, source.as_uri(), log=lambda _: None) == []  # already there


def test_download_rejects_a_changed_file(source, tmp_path):
    spec = _spec(source / "words.dat")
    wrong = DataFile(spec.name, spec.bytes, "0" * 64, "test")
    with pytest.raises(HazmDataError, match="does not match"):
        download(tmp_path / "hazm", (wrong,), source.as_uri(), log=lambda _: None)
    assert not (tmp_path / "hazm" / "words.dat").exists()
    assert not (tmp_path / "hazm" / "words.dat.part").exists()


def test_check_reports_why(source, tmp_path):
    spec = _spec(source / "words.dat")
    assert check(spec, tmp_path / "none.dat") == "missing"
    (tmp_path / "words.dat").write_text("x", encoding="utf-8")
    assert "bytes" in check(spec, tmp_path / "words.dat")


def test_readers(source):
    assert hazm_data.words(source).rows() == [
        ("آب", 549005877, "N,AJ"),
        ("آبادان", 2911082, "N"),
        ("آب", 12, "N"),
    ]  # a line without parts of speech is left out
    assert hazm_data.stopwords(source).to_list() == ["در", "و"]
    (source / "verbs.dat").write_text("آموخت#آموز\n#هست\nزیست# زیو\n", encoding="utf-8", newline="\n")
    assert hazm_data.verbs(source).rows() == [("آموخت", "آموز"), ("", "هست"), ("زیست", "زیو")]


def test_missing_file_says_how_to_get_it(tmp_path):
    with pytest.raises(HazmDataError, match="hazm download"):
        hazm_data.words(tmp_path)


def test_real_files():
    """data/hazm/, when downloaded, is hazm's release as listed."""
    if not (hazm_data.HAZM_DIR / "words.dat").exists():
        pytest.skip("hazm data not downloaded (uv run hiesir-codebook hazm download)")
    assert verify() == []
    words = hazm_data.words()
    assert words.height > 190_000
    assert ("آب", 549005877, "N,AJ") in words.rows()
