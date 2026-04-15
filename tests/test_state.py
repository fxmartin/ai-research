"""Tests for state.json atomic read/write."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from ai_research.state import (
    SourceRecord,
    State,
    atomic_write,
    find_page_by_source_hash,
    load_state,
    save_state,
)


def test_load_state_missing_returns_empty(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    state = load_state(state_path)
    assert isinstance(state, State)
    assert state.sources == {}
    assert state.pages == {}


def test_save_then_load_roundtrip(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    state = State(
        sources={"abc123": SourceRecord(page="wiki/concepts/foo.md")},
        pages={"wiki/concepts/foo.md": ["abc123"]},
    )
    save_state(state_path, state)
    loaded = load_state(state_path)
    assert loaded.sources == {"abc123": SourceRecord(page="wiki/concepts/foo.md")}
    assert loaded.pages == {"wiki/concepts/foo.md": ["abc123"]}


def test_save_state_creates_parent_dirs(tmp_path: Path) -> None:
    state_path = tmp_path / "nested" / "dir" / "state.json"
    save_state(state_path, State())
    assert state_path.exists()


def test_load_state_corrupt_raises(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    state_path.write_text("{not valid json")
    with pytest.raises(ValueError):
        load_state(state_path)


def test_atomic_write_uses_temp_then_rename(tmp_path: Path) -> None:
    target = tmp_path / "out.json"
    atomic_write(target, b'{"hello": "world"}')
    assert target.read_text() == '{"hello": "world"}'
    # No leftover temp files
    leftovers = list(tmp_path.glob("*.tmp*"))
    assert leftovers == []


def test_atomic_write_leaves_original_on_crash(tmp_path: Path) -> None:
    """If os.replace is interrupted, the original file must remain intact."""
    target = tmp_path / "out.json"
    target.write_text('{"original": true}')

    def boom(_src: str, _dst: str) -> None:
        raise OSError("simulated crash before rename")

    with patch("ai_research.state.os.replace", side_effect=boom):
        with pytest.raises(OSError):
            atomic_write(target, b'{"new": true}')

    # Original preserved
    assert json.loads(target.read_text()) == {"original": True}
    # Temp file should have been cleaned up
    assert list(tmp_path.glob("*.tmp*")) == []


def test_concurrent_writes_never_half_written(tmp_path: Path) -> None:
    """Simulate two writers; final state must be one of the complete payloads."""
    target = tmp_path / "state.json"
    payload_a = State(sources={"a" * 8: SourceRecord(page="wiki/a.md")})
    payload_b = State(sources={"b" * 8: SourceRecord(page="wiki/b.md")})
    save_state(target, payload_a)
    save_state(target, payload_b)
    loaded = load_state(target)
    assert loaded.sources in (payload_a.sources, payload_b.sources)


def test_find_page_by_source_hash_hit(tmp_path: Path) -> None:
    state = State(sources={"deadbeef": SourceRecord(page="wiki/concepts/x.md")})
    assert find_page_by_source_hash(state, "deadbeef") == "wiki/concepts/x.md"


def test_find_page_by_source_hash_miss(tmp_path: Path) -> None:
    state = State(sources={"deadbeef": SourceRecord(page="wiki/concepts/x.md")})
    assert find_page_by_source_hash(state, "nope") is None


# ---------------------------------------------------------------------------
# Story 07.1-001: schema migration — old string-valued sources to new dict
# ---------------------------------------------------------------------------


def test_load_state_migrates_old_string_sources(tmp_path: Path) -> None:
    """A pre-07.1 state.json with string-valued sources must load into the
    new :class:`SourceRecord` shape with ``archive_path`` defaulting to None."""
    state_path = tmp_path / "state.json"
    state_path.write_text(
        json.dumps(
            {
                "sources": {
                    "deadbeef": "wiki/concepts/foo.md",
                    "cafef00d": "wiki/concepts/bar.md",
                },
                "pages": {
                    "wiki/concepts/foo.md": ["deadbeef"],
                    "wiki/concepts/bar.md": ["cafef00d"],
                },
            }
        ),
        encoding="utf-8",
    )

    loaded = load_state(state_path)
    assert loaded.sources == {
        "deadbeef": SourceRecord(page="wiki/concepts/foo.md", archive_path=None),
        "cafef00d": SourceRecord(page="wiki/concepts/bar.md", archive_path=None),
    }
    # pages index must survive migration unchanged.
    assert loaded.pages == {
        "wiki/concepts/foo.md": ["deadbeef"],
        "wiki/concepts/bar.md": ["cafef00d"],
    }


def test_save_after_migration_persists_new_shape(tmp_path: Path) -> None:
    """A single save_state after migrating an old file writes the new shape."""
    state_path = tmp_path / "state.json"
    state_path.write_text(
        json.dumps({"sources": {"abc": "wiki/x.md"}, "pages": {}}),
        encoding="utf-8",
    )

    loaded = load_state(state_path)
    save_state(state_path, loaded)

    raw = json.loads(state_path.read_text(encoding="utf-8"))
    assert raw["sources"] == {
        "abc": {"page": "wiki/x.md", "archive_path": None},
    }


def test_save_load_roundtrip_with_archive_path(tmp_path: Path) -> None:
    """New-shape entries with a set ``archive_path`` must round-trip verbatim."""
    state_path = tmp_path / "state.json"
    state = State(
        sources={
            "hash1": SourceRecord(
                page="wiki/concepts/foo.md",
                archive_path="sources/2026/04/hash1-foo.md",
            ),
            "hash2": SourceRecord(page="wiki/concepts/bar.md"),  # archive_path=None
        },
        pages={
            "wiki/concepts/foo.md": ["hash1"],
            "wiki/concepts/bar.md": ["hash2"],
        },
    )
    save_state(state_path, state)
    loaded = load_state(state_path)
    assert loaded == state


def test_scan_skip_known_still_works_after_migration(tmp_path: Path) -> None:
    """Regression guard: ``scan --skip-known`` keys off ``state.sources.keys()``
    — after old-format migration, hash membership must still be detectable."""
    from ai_research.scan import scan_raw

    state_path = tmp_path / "state.json"
    # Seed an old-format state file containing one known hash.
    known_hash = "a" * 64
    state_path.write_text(
        json.dumps({"sources": {known_hash: "wiki/known.md"}, "pages": {}}),
        encoding="utf-8",
    )

    migrated = load_state(state_path)
    # Migration must surface the hash as a key so ``.keys()`` lookup works.
    assert known_hash in migrated.sources

    inbox = tmp_path / "raw"
    inbox.mkdir()
    unknown = inbox / "new.md"
    unknown.write_text("# Fresh\n\nBody.\n", encoding="utf-8")

    # ``now`` is bumped well past the file mtime so min-age doesn't hide it.
    results = scan_raw(
        inbox,
        state=migrated,
        skip_known=True,
        now=unknown.stat().st_mtime + 3600,
    )
    # The fresh file's hash is not ``known_hash`` → it should be eligible.
    # Path is returned as a resolved absolute string.
    assert str(unknown.resolve()) in results


def test_load_state_invalid_schema_raises(tmp_path: Path) -> None:
    """Valid JSON that violates the State pydantic schema must raise ValueError."""
    state_path = tmp_path / "state.json"
    # sources must be dict[str, str]; give it a list to trigger ValidationError
    state_path.write_text('{"sources": ["not", "a", "dict"], "pages": {}}')
    with pytest.raises(ValueError, match="failed schema validation"):
        load_state(state_path)


def test_atomic_write_temp_already_gone_before_cleanup(tmp_path: Path) -> None:
    """Cleanup branch: if the temp file disappears before unlink, the
    FileNotFoundError is silently swallowed and the original error is re-raised."""
    target = tmp_path / "out.json"

    def replace_then_vanish(src: str, dst: str) -> None:
        # Remove the temp file to simulate it having been consumed elsewhere,
        # then raise so the except BaseException cleanup branch executes.
        Path(src).unlink(missing_ok=True)
        raise OSError("simulated failure after temp removed")

    with patch("ai_research.state.os.replace", side_effect=replace_then_vanish):
        with pytest.raises(OSError, match="simulated failure"):
            atomic_write(target, b'{"hello": "world"}')

    # Target must not exist — the write was aborted before rename completed.
    assert not target.exists()
    # And no temp files left behind.
    assert list(tmp_path.glob("*.tmp*")) == []
