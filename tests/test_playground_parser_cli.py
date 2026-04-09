"""CLI integration test for the offline Ralph playground parser path."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import fitz


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _make_text_pdf(path: Path) -> None:
    doc = fitz.open()
    page = doc.new_page()
    sample = "This is a sample PDF for Ralph parser integration testing. " * 4
    page.insert_textbox(fitz.Rect(72, 72, 520, 760), sample, fontsize=12)
    doc.save(path)
    doc.close()


def test_playground_parser_cli_returns_pymupdf_result_for_text_pdf_without_vlm(tmp_path: Path) -> None:
    pdf_path = tmp_path / "sample.pdf"
    _make_text_pdf(pdf_path)

    env = os.environ.copy()
    env["RALPH_USE_VLM"] = "false"
    env["PYTHONPATH"] = str(PROJECT_ROOT)

    proc = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "ralph" / "playground_parser.py"), str(pdf_path)],
        cwd=str(PROJECT_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["ok"] is True
    assert payload["pages"] == 1
    assert payload["method"] == "pymupdf"
    assert payload["text_structure"] == "document"
    assert payload["visual_description"] is None
    assert "integration testing" in payload["text"]


def test_assess_text_quality_treats_indonesian_text_as_real_text() -> None:
    from ralph.playground_parser import assess_text_quality

    text = (
        "Ini adalah dokumen investasi dalam bahasa Indonesia dengan uraian pasar, "
        "proyeksi pendapatan, strategi distribusi, dan analisis risiko. "
        "Dokumen ini memiliki cukup banyak teks sehingga tidak boleh dianggap "
        "sebagai hasil OCR yang buruk atau PDF gambar."
    )

    quality, is_poor, is_fragmented = assess_text_quality(
        text,
        blocks=[text[:80], text[80:160], text[160:]],
        page_count=1,
    )

    assert quality > 0.3
    assert is_poor is False
    assert is_fragmented is False
