import importlib.util
from pathlib import Path

import pytest

from hiesir_codebook import SUPPORTED_YEARS, explorer
from hiesir_codebook.extraction import pdfs

ROOT = Path(__file__).resolve().parents[1]


def test_published_names(tmp_path):
    for name in (
        "Questionnaire 1363 Urban.pdf",
        "Questionnaire 1386.pdf",
        "questionnaire_1401.pdf",
        "notes.pdf",
    ):
        (tmp_path / name).write_bytes(b"%PDF")
    found = pdfs.find(tmp_path)
    assert [(f.year, f.area, f.name, f.kind) for f in found] == [
        (1363, "urban", "questionnaire_1363_urban.pdf", "scan"),
        (1386, "", "questionnaire_1386.pdf", "extracted"),
        (1401, "", "questionnaire_1401.pdf", "extracted"),
    ]
    renamed = pdfs.rename(tmp_path)
    assert sorted(dst.name for _src, dst in renamed) == [
        "questionnaire_1363_urban.pdf",
        "questionnaire_1386.pdf",
    ]
    assert sorted(f.path.name for f in pdfs.find(tmp_path)) == [f.name for f in found]


def _release(tmp_path):
    """A folder standing in for the release, its manifest, and an empty data/pdf/."""
    release = tmp_path / "release"
    release.mkdir()
    (release / "questionnaire_1386.pdf").write_bytes(b"%PDF-1386" * 100)
    (release / "questionnaire_1363_urban.pdf").write_bytes(b"%PDF-1363u")
    manifest = tmp_path / "pdfs.csv"
    entries = pdfs.write_manifest(release, manifest)
    return release, manifest, entries, tmp_path / "pdf"


def test_manifest_lists_size_and_hash(tmp_path):
    release, manifest, entries, _ = _release(tmp_path)
    assert pdfs.load_manifest(manifest) == entries
    (e,) = [e for e in entries if e.year == 1386]
    assert (e.name, e.area, e.kind, e.bytes) == ("questionnaire_1386.pdf", "", "extracted", 900)
    assert e.sha256 == pdfs.sha256(release / e.name) and len(e.sha256) == 64
    assert manifest.read_text(encoding="utf-8").splitlines()[0] == ",".join(pdfs.MANIFEST_COLUMNS)
    (release / "Questionnaire 1390.pdf").write_bytes(b"%PDF")
    with pytest.raises(pdfs.PdfError, match="not a release name"):
        pdfs.write_manifest(release, manifest)


def test_download_checks_and_skips(tmp_path):
    release, _manifest, entries, folder = _release(tmp_path)
    url = release.as_uri()  # urllib reads file:// like https://
    log = []
    got = pdfs.download(entries, folder, base_url=url, log=log.append)
    assert sorted(p.name for p in got) == sorted(e.name for e in entries)
    assert pdfs.verify(folder, entries) == []
    assert pdfs.download(entries, folder, base_url=url) == []  # all there: nothing fetched
    assert not list(folder.glob("*.part"))


def test_download_rejects_a_changed_file(tmp_path):
    release, _manifest, entries, folder = _release(tmp_path)
    (release / "questionnaire_1386.pdf").write_bytes(b"%PDF-other" * 90)  # same size, other bytes
    with pytest.raises(pdfs.PdfError, match="SHA-256 differs"):
        pdfs.download([e for e in entries if e.year == 1386], folder, base_url=release.as_uri())
    assert not (folder / "questionnaire_1386.pdf").exists()
    assert not list(folder.glob("*.part"))


def test_download_reports_a_missing_file(tmp_path):
    release, _manifest, entries, folder = _release(tmp_path)
    (release / "questionnaire_1386.pdf").unlink()
    with pytest.raises(pdfs.PdfError, match="download failed"):
        pdfs.download(entries, folder, base_url=release.as_uri(), retries=1)


def test_verify_finds_problems(tmp_path):
    _release_dir, _manifest, entries, folder = _release(tmp_path)
    folder.mkdir()
    (folder / "questionnaire_1386.pdf").write_bytes(b"short")
    (folder / "questionnaire_1390.pdf").write_bytes(b"%PDF")
    assert pdfs.verify(folder, entries) == [
        "questionnaire_1363_urban.pdf: missing",
        "questionnaire_1386.pdf: 5 bytes, expected 900",
        "questionnaire_1390.pdf: not in the list",
    ]


def test_tracked_manifest_matches_the_pdfs():
    """data/pdfs.csv lists every PDF once, under its release name; with the
    PDFs in data/pdf/ (downloaded in CI) they match it byte for byte."""
    entries = pdfs.load_manifest(ROOT / "data" / "pdfs.csv")
    assert len({e.name for e in entries}) == len(entries)
    assert all(e.name == pdfs.published_name(e.year, e.area) for e in entries)
    assert {e.year for e in entries if e.kind == "extracted"} == set(SUPPORTED_YEARS)
    folder = ROOT / "data" / "pdf"
    if not pdfs.find(folder):
        pytest.skip("no PDFs in data/pdf/")
    assert pdfs.verify(folder, entries) == []


def _hooks():
    pytest.importorskip("mkdocs")  # the docs dependency group
    spec = importlib.util.spec_from_file_location("mkdocs_hooks", ROOT / "scripts" / "mkdocs_hooks.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_questionnaire_table(tmp_path):
    (tmp_path / "Questionnaire 1386.pdf").write_bytes(b"%PDF" * 1000)
    hooks = _hooks()
    book = tmp_path / "questionnaire_1386.xlsx"
    book.write_bytes(b"x" * 150 * 1024)
    books = {1386: book}
    found = pdfs.find(tmp_path)
    en = hooks.pdf_table(found, "en", books)
    # each file a link with the icon of its application and its size
    assert "| 1386 | urban and rural | extracted" in en
    assert "[:material-file-pdf-box: 4 KB](pdf/questionnaire_1386.pdf)" in en
    assert "[:material-microsoft-excel: 150 KB](excel/questionnaire_1386.xlsx)" in en
    assert 'aria-label="Download questionnaire_1386.xlsx, 150 KB"' in en
    fa = hooks.pdf_table(found, "fa", books)
    assert "| ۱۳۸۶ | شهری و روستایی |" in fa and "۱۵۰ کیلوبایت" in fa
    # without the PDFs, a note and the workbooks still
    alone = hooks.pdf_table([], "en", books)
    assert "!!! note" in alone and "excel/questionnaire_1386.xlsx" in alone


def test_hreflang_links_are_dropped():
    # Material fetches <href>/sitemap.xml for each of them (404 for every page)
    hooks = _hooks()
    page = (
        '<head>\n  <link rel="alternate" href="./" hreflang="en">\n'
        '  <link rel="alternate" href="../fa/explorer/" hreflang="fa">\n'
        '  <link rel="alternate" type="application/rss+xml" href="feed.xml">\n</head>'
    )
    out = hooks.on_post_page(page, None, None)
    assert "hreflang" not in out and "feed.xml" in out


def test_explorer_knows_the_printed_page():
    data = explorer.collect(
        corrected=ROOT / "output" / "2_corrected",
        items=ROOT / "output" / "3_items",
        source=ROOT / "curated" / "2_corrected" / "corrections.csv",
    )
    for c in data["chains"]:
        asked = [y for y in data["years"] if c["first"] <= y <= c["last"] and y not in c["miss"]]
        assert len(c["pg"]) == len(asked), c["id"]  # one page per year asked, in order
        assert len(c["bx"]) == len(asked), c["id"]  # and one box per year asked
    rice = next(c for c in data["chains"] if c["id"] == "C-011111-1383")
    assert all(isinstance(p, int) and p > 0 for p in rice["pg"])
    assert all(
        0 < b[0] < b[1] < 900 and 0 <= b[2] < b[3] < 650 for b in rice["bx"]
    )  # inside an A4 page, in points


def test_every_printed_item_has_its_position():
    """Items carry their box on the page (top, bottom, left, right; 1382 is A3,
    the rest A4); only items that
    curated/2_corrected/corrections.csv copies into a year (no page) lack one."""
    from hiesir_codebook import csv_io

    for f in sorted((ROOT / "output" / "2_corrected").glob("questionnaire_*.csv")):
        for r in csv_io.read(f):
            if r["kind"] != "item":
                continue
            assert bool(r["page"]) == bool(r["top"]) == bool(r["bottom"]), (f.name, r["expenditure_code"])
            if r["left"]:
                assert 0 <= float(r["left"]) < float(r["right"]) < 850, (f.name, r["expenditure_code"])
            if r["top"]:
                assert 0 < float(r["top"]) < float(r["bottom"]) < 1200, (f.name, r["expenditure_code"])
                assert float(r["bottom"]) - float(r["top"]) < 120, (f.name, r["expenditure_code"])


def test_pdf_path_is_the_release_name(tmp_path):
    from hiesir_codebook.extraction.parse import pdf_path

    assert pdf_path(1390, tmp_path) == tmp_path / "pdf" / "questionnaire_1390.pdf"
