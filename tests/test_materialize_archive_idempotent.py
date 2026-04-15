"""Idempotency tests for re-materializing an already-archived source (Story 07.1-003).

Covers two paths the story calls out:

1. Explicit opt-out: ``materialize --no-archive`` against a source under
   ``sources/`` succeeds without attempting a move.
2. Implicit no-op: without ``--no-archive``, an already-archived source (same
   canonical target path, same hash) is detected by :func:`archive_source` and
   no-ops silently — the source stays where it is and state.json still points
   at the correct archive path.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from ai_research.archive import archive_source, compute_archive_path
from ai_research.state import load_state
from ai_research.wiki.materialize import MaterializeStatus, materialize

FIXED_NOW = datetime(2026, 4, 14, 12, 0, 0, tzinfo=UTC)


def _draft(tmp_path: Path, body: str = "# Foo\n\nBody.\n") -> Path:
    d = tmp_path / "draft.md"
    d.write_text(body, encoding="utf-8")
    return d


def _place_in_archive(tmp_path: Path, content: str = "raw bytes\n") -> tuple[Path, Path]:
    """Create ``sources/<yyyy>/<mm>/<hash>-foo.md`` directly and return (src, sources_root)."""
    sources_root = tmp_path / "sources"
    seed = tmp_path / "seed-foo.md"
    seed.write_text(content, encoding="utf-8")
    target = compute_archive_path(
        source=seed,
        sources_root=sources_root,
        title="Foo",
        now=FIXED_NOW,
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    seed.unlink()
    return target, sources_root


def test_no_archive_against_prearchived_source_succeeds(tmp_path: Path) -> None:
    """Explicit --no-archive opt-out against a source already under sources/."""
    archived, _ = _place_in_archive(tmp_path)
    wiki = tmp_path / "wiki"
    state_path = tmp_path / ".ai-research" / "state.json"
    draft = _draft(tmp_path)

    result = materialize(
        source=archived,
        draft_path=draft,
        wiki_dir=wiki,
        state_path=state_path,
        now=FIXED_NOW,
        no_archive=True,
    )

    assert result.status is MaterializeStatus.CREATED
    # Source preserved in-place — we never moved it.
    assert archived.exists()
    assert archived.read_text(encoding="utf-8") == "raw bytes\n"
    # state.archive_path stays None on the --no-archive path (the caller asserts
    # responsibility for tracking the archive out-of-band).
    state = load_state(state_path)
    assert state.sources[result.source_hash].archive_path is None


def test_archive_source_noop_when_src_equals_target(tmp_path: Path) -> None:
    """archive_source on an already-archived file is a silent no-op.

    Core invariant for Story 07.1-003 AC2: re-running ``materialize`` against a
    source at its canonical ``sources/<yyyy>/<mm>/<hash>-<slug>.<ext>`` path
    without ``--no-archive`` must not destroy the archived bytes.
    """
    archived, sources_root = _place_in_archive(tmp_path)
    original_bytes = archived.read_bytes()

    returned = archive_source(
        source=archived,
        sources_root=sources_root,
        title="Foo",
        now=FIXED_NOW,
    )

    # Returns the canonical path and file is still intact (NOT unlinked).
    assert returned == archived
    assert archived.exists(), "already-archived source must not be deleted"
    assert archived.read_bytes() == original_bytes


def test_rematerialize_prearchived_source_without_no_archive(tmp_path: Path) -> None:
    """Re-materialize against an already-archived source is a full no-op on bytes."""
    archived, sources_root = _place_in_archive(tmp_path)
    wiki = tmp_path / "wiki"
    state_path = tmp_path / ".ai-research" / "state.json"
    draft = _draft(tmp_path)

    result = materialize(
        source=archived,
        draft_path=draft,
        wiki_dir=wiki,
        state_path=state_path,
        now=FIXED_NOW,
        sources_root=sources_root,
    )

    assert result.status is MaterializeStatus.CREATED
    # The archived file is still present — archive_source detected
    # src == target (same hash) and no-oped silently.
    assert archived.exists()
    assert archived.read_text(encoding="utf-8") == "raw bytes\n"
    # State correctly records the archive path.
    state = load_state(state_path)
    record = state.sources[result.source_hash]
    assert record.archive_path is not None
    resolved = (state_path.resolve().parent.parent / record.archive_path).resolve()
    assert resolved == archived.resolve()
