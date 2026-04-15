"""Tests for the ``ai-research source lookup <slug>`` verb (Story 07.3-001)."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from ai_research.cli import app
from ai_research.state import SourceRecord, State, save_state

runner = CliRunner()


def _write_state(tmp_path: Path, state: State) -> Path:
    state_file = tmp_path / ".ai-research" / "state.json"
    save_state(state_file, state)
    return state_file


def test_lookup_prints_archive_path_for_materialized_page(tmp_path: Path) -> None:
    """Happy path: slug maps to a page with a recorded archive_path."""
    state = State(
        sources={
            "deadbeef": SourceRecord(
                page="wiki/dario-amodei.md",
                archive_path="sources/2026/04/deadbeef-dario-amodei.md",
            )
        },
        pages={"wiki/dario-amodei.md": ["deadbeef"]},
    )
    state_file = _write_state(tmp_path, state)

    result = runner.invoke(
        app, ["source", "lookup", "dario-amodei", "--state-file", str(state_file)]
    )

    assert result.exit_code == 0, result.output
    assert result.stdout.strip() == "sources/2026/04/deadbeef-dario-amodei.md"


def test_lookup_json_mode(tmp_path: Path) -> None:
    """`--json` emits a structured payload with slug, page, archive_path, source_hash."""
    state = State(
        sources={
            "cafef00d": SourceRecord(
                page="wiki/transformers.md",
                archive_path="sources/2026/04/cafef00d-transformers.md",
            )
        },
        pages={"wiki/transformers.md": ["cafef00d"]},
    )
    state_file = _write_state(tmp_path, state)

    result = runner.invoke(
        app,
        ["source", "lookup", "transformers", "--state-file", str(state_file), "--json"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload == {
        "slug": "transformers",
        "page": "wiki/transformers.md",
        "archive_path": "sources/2026/04/cafef00d-transformers.md",
        "source_hash": "cafef00d",
    }


def test_lookup_stub_only_concept_exits_nonzero(tmp_path: Path) -> None:
    """A slug that lives only as a stub under wiki/concepts/ is a hard error."""
    wiki = tmp_path / "wiki"
    (wiki / "concepts").mkdir(parents=True)
    (wiki / "concepts" / "mechanistic-interpretability.md").write_text("stub\n")

    state = State()  # empty state: the stub is not a full page
    state_file = _write_state(tmp_path, state)

    result = runner.invoke(
        app,
        [
            "source",
            "lookup",
            "mechanistic-interpretability",
            "--state-file",
            str(state_file),
            "--wiki-dir",
            str(wiki),
        ],
    )

    combined = (result.stdout or "") + (result.stderr or "")
    assert result.exit_code != 0
    assert "stub" in combined.lower()
    assert "mechanistic-interpretability" in combined


def test_lookup_pre_migration_null_archive_path(tmp_path: Path) -> None:
    """Page exists, but archive_path is None (pre-migration ingest) — exit 0 with note."""
    state = State(
        sources={"abc123": SourceRecord(page="wiki/old-page.md", archive_path=None)},
        pages={"wiki/old-page.md": ["abc123"]},
    )
    state_file = _write_state(tmp_path, state)

    result = runner.invoke(
        app, ["source", "lookup", "old-page", "--state-file", str(state_file)]
    )

    assert result.exit_code == 0, result.output
    combined = (result.stdout or "") + (result.stderr or "")
    assert "not archived" in combined.lower()
    assert "pre-migration" in combined.lower()


def test_lookup_pre_migration_null_archive_path_json(tmp_path: Path) -> None:
    """JSON mode for a null archive_path still emits a structured payload."""
    state = State(
        sources={"abc123": SourceRecord(page="wiki/old-page.md", archive_path=None)},
        pages={"wiki/old-page.md": ["abc123"]},
    )
    state_file = _write_state(tmp_path, state)

    result = runner.invoke(
        app,
        ["source", "lookup", "old-page", "--state-file", str(state_file), "--json"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["slug"] == "old-page"
    assert payload["page"] == "wiki/old-page.md"
    assert payload["archive_path"] is None
    assert payload["source_hash"] == "abc123"


def test_lookup_unknown_slug_exits_nonzero(tmp_path: Path) -> None:
    """A slug that exists nowhere is a non-zero exit with a helpful message."""
    state = State()
    state_file = _write_state(tmp_path, state)

    result = runner.invoke(
        app, ["source", "lookup", "nope", "--state-file", str(state_file)]
    )

    combined = (result.stdout or "") + (result.stderr or "")
    assert result.exit_code != 0
    assert "nope" in combined


def test_lookup_missing_state_file(tmp_path: Path) -> None:
    """Missing state.json is a usage-style error (non-zero exit, helpful message)."""
    result = runner.invoke(
        app,
        [
            "source",
            "lookup",
            "whatever",
            "--state-file",
            str(tmp_path / "does-not-exist.json"),
        ],
    )

    assert result.exit_code != 0
