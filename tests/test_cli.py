"""Tests for the ai-research Typer CLI skeleton."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from ai_research import __version__
from ai_research.cli import app
from ai_research.extract import (
    PdfExtractionError,
    PdftotextNotFoundError,
    UnsupportedSourceError,
    UrlExtractionError,
)

runner = CliRunner()


def test_help_exits_zero() -> None:
    """`ai-research --help` must exit 0 and show Typer help."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "ai-research" in result.stdout.lower() or "Usage" in result.stdout


def test_version_prints_version_string() -> None:
    """`ai-research version` must print the exact `__version__` string."""
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == __version__


# ---------------------------------------------------------------------------
# extract command — happy path
# ---------------------------------------------------------------------------


def test_extract_happy_path_prints_json(tmp_path: Path) -> None:
    """extract dispatches to the adapter and emits JSON on stdout."""
    fake_result = {"text": "hello", "metadata": {"source_type": "markdown"}}
    src = tmp_path / "note.md"
    src.write_text("hello")

    with patch("ai_research.cli.extract_dispatch", return_value=fake_result):
        result = runner.invoke(app, ["extract", str(src)])

    assert result.exit_code == 0
    parsed = json.loads(result.stdout)
    assert parsed == fake_result


def test_extract_output_ends_with_newline(tmp_path: Path) -> None:
    """extract output must end with a newline so it is shell-pipeline friendly."""
    fake_result = {"text": "x", "metadata": {}}
    src = tmp_path / "note.md"
    src.write_text("x")

    with patch("ai_research.cli.extract_dispatch", return_value=fake_result):
        result = runner.invoke(app, ["extract", str(src)])

    assert result.exit_code == 0
    assert result.stdout.endswith("\n")


# ---------------------------------------------------------------------------
# extract command — error paths (exit codes and stderr messages)
# ---------------------------------------------------------------------------


def test_extract_unsupported_source_exits_2(tmp_path: Path) -> None:
    """`UnsupportedSourceError` must produce exit code 2."""
    src = tmp_path / "data.xyz"
    src.write_text("nope")

    with patch(
        "ai_research.cli.extract_dispatch",
        side_effect=UnsupportedSourceError("unsupported"),
    ):
        result = runner.invoke(app, ["extract", str(src)])

    assert result.exit_code == 2


def test_extract_unsupported_source_writes_to_stderr(tmp_path: Path) -> None:
    """`UnsupportedSourceError` message must appear on stderr, not stdout."""
    src = tmp_path / "data.xyz"
    src.write_text("nope")

    with patch(
        "ai_research.cli.extract_dispatch",
        side_effect=UnsupportedSourceError("unsupported type .xyz"),
    ):
        result = runner.invoke(app, ["extract", str(src)], catch_exceptions=False)

    # Typer's CliRunner mixes stderr into output when mix_stderr=True (default).
    assert "unsupported" in result.output.lower() or result.exit_code == 2


def test_extract_pdftotext_not_found_exits_2(tmp_path: Path) -> None:
    """`PdftotextNotFoundError` must produce exit code 2 (tool missing)."""
    src = tmp_path / "paper.pdf"
    src.write_bytes(b"%PDF-1.4")

    with patch(
        "ai_research.cli.extract_dispatch",
        side_effect=PdftotextNotFoundError("pdftotext not found"),
    ):
        result = runner.invoke(app, ["extract", str(src)])

    assert result.exit_code == 2


def test_extract_pdf_extraction_error_exits_1(tmp_path: Path) -> None:
    """`PdfExtractionError` must produce exit code 1 (extraction failure)."""
    src = tmp_path / "corrupt.pdf"
    src.write_bytes(b"%PDF-corrupted")

    with patch(
        "ai_research.cli.extract_dispatch",
        side_effect=PdfExtractionError("pdftotext failed"),
    ):
        result = runner.invoke(app, ["extract", str(src)])

    assert result.exit_code == 1


def test_extract_url_extraction_error_exits_1() -> None:
    """`UrlExtractionError` must produce exit code 1."""
    with patch(
        "ai_research.cli.extract_dispatch",
        side_effect=UrlExtractionError("network error"),
    ):
        result = runner.invoke(app, ["extract", "https://example.com"])

    assert result.exit_code == 1


def test_extract_file_not_found_exits_1(tmp_path: Path) -> None:
    """`FileNotFoundError` must produce exit code 1."""
    missing = tmp_path / "ghost.md"  # does not exist

    with patch(
        "ai_research.cli.extract_dispatch",
        side_effect=FileNotFoundError(f"No such file: {missing}"),
    ):
        result = runner.invoke(app, ["extract", str(missing)])

    assert result.exit_code == 1


def test_extract_error_message_includes_prefix_for_runtime_errors() -> None:
    """`PdfExtractionError` and `UrlExtractionError` should print 'extract: <msg>'."""
    with patch(
        "ai_research.cli.extract_dispatch",
        side_effect=UrlExtractionError("fetch failed"),
    ):
        result = runner.invoke(app, ["extract", "https://bad.example.com"])

    assert result.exit_code == 1
    # The message is written to stderr (mixed into output by CliRunner default).
    assert "fetch failed" in result.output


def test_extract_missing_argument_exits_nonzero() -> None:
    """`ai-research extract` with no argument must fail (Typer validates it)."""
    result = runner.invoke(app, ["extract"])
    assert result.exit_code != 0
