"""Tests for the `search` ripgrep wrapper verb."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from ai_research.cli import app
from ai_research.search import SearchHit, run_search

runner = CliRunner()


@pytest.fixture
def fixture_wiki(tmp_path: Path) -> Path:
    """Create a small fixture wiki/ with two markdown pages."""
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    (wiki / "alpha.md").write_text(
        "# Alpha\n\nThe quick brown foo jumps.\nAnother line about foo.\n",
        encoding="utf-8",
    )
    (wiki / "beta.md").write_text(
        "# Beta\n\nNo hits here.\nJust filler.\n",
        encoding="utf-8",
    )
    sub = wiki / "concepts"
    sub.mkdir()
    (sub / "gamma.md").write_text("# Gamma\n\nfoo appears once here.\n", encoding="utf-8")
    return wiki


def test_run_search_returns_structured_hits(fixture_wiki: Path) -> None:
    hits = run_search("foo", wiki_dir=fixture_wiki)
    assert len(hits) == 3
    for hit in hits:
        assert isinstance(hit, SearchHit)
        assert hit.page.endswith(".md")
        assert hit.line >= 1
        assert "foo" in hit.snippet.lower()


def test_run_search_limit_truncates(fixture_wiki: Path) -> None:
    hits = run_search("foo", wiki_dir=fixture_wiki, limit=2)
    assert len(hits) == 2


def test_run_search_no_matches(fixture_wiki: Path) -> None:
    hits = run_search("zzznothinghere", wiki_dir=fixture_wiki)
    assert hits == []


def test_run_search_missing_wiki_dir(tmp_path: Path) -> None:
    missing = tmp_path / "nope"
    with pytest.raises(FileNotFoundError):
        run_search("foo", wiki_dir=missing)


def test_run_search_missing_rg_binary(fixture_wiki: Path) -> None:
    with patch("ai_research.search.shutil.which", return_value=None):
        with pytest.raises(RuntimeError, match="ripgrep"):
            run_search("foo", wiki_dir=fixture_wiki)


def test_run_search_rg_failure(fixture_wiki: Path) -> None:
    """Non-zero, non-1 rg exit codes should raise."""

    def fake_run(*args, **kwargs):  # type: ignore[no-untyped-def]
        return subprocess.CompletedProcess(args[0], returncode=2, stdout="", stderr="boom")

    with patch("ai_research.search.subprocess.run", side_effect=fake_run):
        with pytest.raises(RuntimeError, match="ripgrep failed"):
            run_search("foo", wiki_dir=fixture_wiki)


def test_cli_search_emits_json(fixture_wiki: Path) -> None:
    if shutil.which("rg") is None:
        pytest.skip("ripgrep not available")
    result = runner.invoke(app, ["search", "foo", "--wiki-dir", str(fixture_wiki)])
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert isinstance(payload, list)
    assert len(payload) == 3
    for item in payload:
        assert set(item.keys()) == {"page", "line", "snippet"}


def test_cli_search_limit(fixture_wiki: Path) -> None:
    if shutil.which("rg") is None:
        pytest.skip("ripgrep not available")
    result = runner.invoke(app, ["search", "foo", "--wiki-dir", str(fixture_wiki), "--limit", "1"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert len(payload) == 1


def test_cli_search_missing_rg_shows_clear_error(fixture_wiki: Path) -> None:
    with patch("ai_research.search.shutil.which", return_value=None):
        result = runner.invoke(app, ["search", "foo", "--wiki-dir", str(fixture_wiki)])
    assert result.exit_code != 0
    assert "ripgrep" in (result.stdout + (result.stderr or "")).lower()


# ---------------------------------------------------------------------------
# Coverage gap tests added by QA gate (story 01.3-002)
# ---------------------------------------------------------------------------


def test_extract_text_bytes_fallback() -> None:
    """_extract_text returns '' when the obj has no 'text' key (bytes-encoded path)."""
    from ai_research.search import _extract_text

    # bytes form — not text-decodable; we discard and return empty string
    result = _extract_text({"bytes": "aGVsbG8="})
    assert result == ""


def test_extract_text_with_text_key() -> None:
    """_extract_text returns the value of the 'text' key when present."""
    from ai_research.search import _extract_text

    assert _extract_text({"text": "hello world"}) == "hello world"


def test_run_search_skips_blank_and_invalid_json_lines(fixture_wiki: Path) -> None:
    """Blank lines and non-JSON output from rg are silently skipped."""

    def fake_run(*args, **kwargs):  # type: ignore[no-untyped-def]
        # Mix: blank line, invalid JSON, then a valid match event
        valid_match = json.dumps(
            {
                "type": "match",
                "data": {
                    "path": {"text": "wiki/alpha.md"},
                    "lines": {"text": "The quick brown foo jumps.\n"},
                    "line_number": 3,
                },
            }
        )
        stdout = "\n" + "not-json-at-all\n" + valid_match + "\n"
        return subprocess.CompletedProcess(args[0], returncode=0, stdout=stdout, stderr="")

    with patch("ai_research.search.subprocess.run", side_effect=fake_run):
        hits = run_search("foo", wiki_dir=fixture_wiki)

    assert len(hits) == 1
    assert hits[0].page == "wiki/alpha.md"
    assert hits[0].line == 3


def test_run_search_skips_non_match_events(fixture_wiki: Path) -> None:
    """rg emits begin/end/summary events; only 'match' type produces hits."""

    def fake_run(*args, **kwargs):  # type: ignore[no-untyped-def]
        begin_event = json.dumps({"type": "begin", "data": {"path": {"text": "wiki/alpha.md"}}})
        summary_event = json.dumps({"type": "summary", "data": {}})
        stdout = begin_event + "\n" + summary_event + "\n"
        return subprocess.CompletedProcess(args[0], returncode=0, stdout=stdout, stderr="")

    with patch("ai_research.search.subprocess.run", side_effect=fake_run):
        hits = run_search("foo", wiki_dir=fixture_wiki)

    assert hits == []


def test_run_search_skips_match_with_missing_page_or_line(fixture_wiki: Path) -> None:
    """Match events that lack a text path or line_number are silently skipped."""

    def fake_run(*args, **kwargs):  # type: ignore[no-untyped-def]
        # Missing page text (bytes form → _extract_text returns "")
        no_page = json.dumps(
            {
                "type": "match",
                "data": {
                    "path": {"bytes": "aGVsbG8="},
                    "lines": {"text": "something\n"},
                    "line_number": 1,
                },
            }
        )
        # Missing line_number
        no_line = json.dumps(
            {
                "type": "match",
                "data": {
                    "path": {"text": "wiki/alpha.md"},
                    "lines": {"text": "something\n"},
                },
            }
        )
        stdout = no_page + "\n" + no_line + "\n"
        return subprocess.CompletedProcess(args[0], returncode=0, stdout=stdout, stderr="")

    with patch("ai_research.search.subprocess.run", side_effect=fake_run):
        hits = run_search("foo", wiki_dir=fixture_wiki)

    assert hits == []


def test_cli_version_prints_version() -> None:
    """The `version` subcommand emits the package __version__ string."""
    from ai_research import __version__

    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_cli_search_missing_wiki_dir_exits_with_code_2(tmp_path: Path) -> None:
    """CLI exits with code 2 and a helpful message when wiki_dir does not exist."""
    missing = str(tmp_path / "no-such-wiki")
    result = runner.invoke(app, ["search", "foo", "--wiki-dir", missing])
    assert result.exit_code == 2
    combined = (result.stdout or "") + (result.stderr or "")
    assert "wiki" in combined.lower() or "not found" in combined.lower()
