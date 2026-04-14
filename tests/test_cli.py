"""Tests for the ai-research Typer CLI skeleton."""

from __future__ import annotations

from typer.testing import CliRunner

from ai_research import __version__
from ai_research.cli import app

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
