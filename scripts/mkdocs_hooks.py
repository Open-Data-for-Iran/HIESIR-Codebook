"""MkDocs hooks: publish the explorer's data and component, and the CSVs.

They are added to the site at build time instead of being copied into docs/,
so git holds one copy and the site always shows what output/ holds:

    explorer.collect() over output/          -> explorer/data.json
    src/.../data/explorer/explorer.{js,css}  -> assets/explorer/
    output/2_corrected/*.csv                 -> 2_corrected/*.csv
    output/3_matched/*.csv                   -> 3_matched/*.csv

The explorer page itself is docs/explorer.md (and its translations), drawn by
overrides/explorer.html.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from mkdocs.structure.files import File, Files

from hiesir_codebook import explorer

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output"
PUBLISH = ["2_corrected/*.csv", "3_matched/*.csv"]


def on_files(files: Files, config) -> Files:
    # added in every language build; mkdocs-static-i18n writes them once, at the
    # site root, and points the translated pages there
    cwd = os.getcwd()
    os.chdir(ROOT)  # explorer.collect() reads output/ and curated/ relative to the repository
    try:
        data = explorer.to_json(explorer.collect())
    finally:
        os.chdir(cwd)
    # a real file: mkdocs-static-i18n cannot handle files generated from content
    cache = Path(tempfile.mkdtemp(prefix="hiesir-explorer-")) / "data.json"
    cache.write_text(data, encoding="utf-8")
    files.append(File.generated(config, "explorer/data.json", abs_src_path=str(cache)))
    for src in (explorer.JS, explorer.CSS):
        files.append(File.generated(config, f"assets/explorer/{src.name}", abs_src_path=str(src)))
    for pattern in PUBLISH:
        paths = sorted(OUTPUT.glob(pattern))
        if not paths:
            raise FileNotFoundError(f"nothing matches output/{pattern}; run `hiesir-codebook build`")
        for p in paths:
            files.append(File.generated(config, p.relative_to(OUTPUT).as_posix(), abs_src_path=str(p)))
    return files
