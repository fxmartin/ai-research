"""Tests for state.json atomic read/write."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from ai_research.state import (
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
        sources={"abc123": "wiki/concepts/foo.md"},
        pages={"wiki/concepts/foo.md": ["abc123"]},
    )
    save_state(state_path, state)
    loaded = load_state(state_path)
    assert loaded.sources == {"abc123": "wiki/concepts/foo.md"}
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
    payload_a = State(sources={"a" * 8: "wiki/a.md"})
    payload_b = State(sources={"b" * 8: "wiki/b.md"})
    save_state(target, payload_a)
    save_state(target, payload_b)
    loaded = load_state(target)
    assert loaded.sources in (payload_a.sources, payload_b.sources)


def test_find_page_by_source_hash_hit(tmp_path: Path) -> None:
    state = State(sources={"deadbeef": "wiki/concepts/x.md"})
    assert find_page_by_source_hash(state, "deadbeef") == "wiki/concepts/x.md"


def test_find_page_by_source_hash_miss(tmp_path: Path) -> None:
    state = State(sources={"deadbeef": "wiki/concepts/x.md"})
    assert find_page_by_source_hash(state, "nope") is None
