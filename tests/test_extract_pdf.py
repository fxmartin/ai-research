"""Tests for the PDF extractor (Story 01.2-001)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from ai_research.cli import app
from ai_research.extract.pdf import (
    PdfExtractionError,
    PdftotextNotFoundError,
    extract_pdf,
)

FIXTURE_PDF = Path(__file__).parent / "fixtures" / "sample.pdf"
runner = CliRunner()


def test_fixture_pdf_exists() -> None:
    assert FIXTURE_PDF.is_file(), "sample.pdf fixture missing"


def test_extract_pdf_returns_text_and_metadata() -> None:
    result = extract_pdf(FIXTURE_PDF)

    assert "text" in result
    assert "metadata" in result
    assert "HELLO_AI_RESEARCH_MARKER" in result["text"]

    meta = result["metadata"]
    assert meta["source_type"] == "pdf"
    assert isinstance(meta["pages"], int) and meta["pages"] >= 1
    expected_hash = hashlib.sha256(FIXTURE_PDF.read_bytes()).hexdigest()
    assert meta["sha256"] == expected_hash


def test_extract_pdf_missing_file_raises() -> None:
    with pytest.raises(PdfExtractionError):
        extract_pdf(Path("/nonexistent/does-not-exist.pdf"))


def test_extract_pdf_malformed_raises(tmp_path: Path) -> None:
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"this is not a pdf")
    with pytest.raises(PdfExtractionError):
        extract_pdf(bad)


def test_extract_pdf_missing_binary_raises(tmp_path: Path) -> None:
    dummy = tmp_path / "x.pdf"
    dummy.write_bytes(b"%PDF-1.4\n")
    with patch("ai_research.extract.pdf.shutil.which", return_value=None):
        with pytest.raises(PdftotextNotFoundError) as exc_info:
            extract_pdf(dummy)
    assert "brew install poppler" in str(exc_info.value)


def test_cli_extract_pdf_emits_json() -> None:
    result = runner.invoke(app, ["extract", str(FIXTURE_PDF)])
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert "HELLO_AI_RESEARCH_MARKER" in payload["text"]
    assert payload["metadata"]["source_type"] == "pdf"
    assert payload["metadata"]["pages"] >= 1
    assert len(payload["metadata"]["sha256"]) == 64


def test_cli_extract_pdf_malformed_nonzero(tmp_path: Path) -> None:
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"not a pdf")
    result = runner.invoke(app, ["extract", str(bad)])
    assert result.exit_code != 0
    # Typer writes errors to stderr; CliRunner merges into output by default off.
    combined = (result.stdout or "") + (result.stderr or "")
    assert "pdf" in combined.lower() or "extract" in combined.lower()


def test_cli_extract_pdf_missing_binary_message(tmp_path: Path) -> None:
    dummy = tmp_path / "x.pdf"
    dummy.write_bytes(b"%PDF-1.4\n")
    with patch("ai_research.extract.pdf.shutil.which", return_value=None):
        result = runner.invoke(app, ["extract", str(dummy)])
    assert result.exit_code != 0
    combined = (result.stdout or "") + (result.stderr or "")
    assert "brew install poppler" in combined
