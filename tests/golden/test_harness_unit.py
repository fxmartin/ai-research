"""Unit tests for the golden-file harness itself (Story 04.1-001).

Exercises the edge cases in ``conftest.py`` that the three golden tests
do not reach: the update path, missing-file detection, mismatch failure,
``_diff`` helper, ``normalize_paths``, and ``normalize_timestamps``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.golden.conftest import (
    GoldenComparator,
    _diff,
    normalize_paths,
    normalize_timestamps,
)

# ---------------------------------------------------------------------------
# normalize_timestamps
# ---------------------------------------------------------------------------


def test_normalize_timestamps_replaces_utc_z_suffix() -> None:
    result = normalize_timestamps("ingested_at: 2026-04-14T12:00:00Z")
    assert result == "ingested_at: <TIMESTAMP>"


def test_normalize_timestamps_replaces_offset_suffix() -> None:
    result = normalize_timestamps("at: 2026-04-14T12:00:00+00:00 done")
    assert result == "at: <TIMESTAMP> done"


def test_normalize_timestamps_leaves_non_timestamp_alone() -> None:
    text = "no timestamps here"
    assert normalize_timestamps(text) == text


def test_normalize_timestamps_replaces_multiple() -> None:
    text = "a: 2026-04-14T12:00:00Z b: 2025-01-01T00:00:00+00:00"
    result = normalize_timestamps(text)
    assert result == "a: <TIMESTAMP> b: <TIMESTAMP>"


# ---------------------------------------------------------------------------
# normalize_paths
# ---------------------------------------------------------------------------


def test_normalize_paths_single_substitution() -> None:
    result = normalize_paths("/tmp/abc/sources/file.md", ("/tmp/abc", "<ROOT>"))
    assert result == "<ROOT>/sources/file.md"


def test_normalize_paths_multiple_substitutions_applied_in_order() -> None:
    result = normalize_paths(
        "/tmp/abc/xyz",
        ("/tmp/abc", "<ROOT>"),
        ("/tmp", "<TMPDIR>"),
    )
    # First substitution fires, second sees <ROOT>/xyz — no /tmp left to match.
    assert result == "<ROOT>/xyz"


def test_normalize_paths_no_substitutions_returns_unchanged() -> None:
    text = "nothing to replace"
    assert normalize_paths(text) == text


# ---------------------------------------------------------------------------
# _diff helper
# ---------------------------------------------------------------------------


def test_diff_returns_empty_string_when_equal() -> None:
    result = _diff("same\n", "same\n", "label")
    assert result == ""


def test_diff_returns_unified_diff_on_mismatch() -> None:
    result = _diff("old line\n", "new line\n", "myfile")
    assert "--- myfile (expected)" in result
    assert "+++ myfile (actual)" in result
    assert "-old line" in result
    assert "+new line" in result


# ---------------------------------------------------------------------------
# GoldenComparator — update path
# ---------------------------------------------------------------------------


def test_golden_comparator_update_creates_file(tmp_path: Path) -> None:
    """With update=True the expected file is written and the call does not raise."""
    expected_path = tmp_path / "sub" / "golden.txt"
    comparator = GoldenComparator(update=True)
    comparator.compare(expected_path, "hello\n", label="test")

    assert expected_path.exists()
    assert expected_path.read_text() == "hello\n"


def test_golden_comparator_update_overwrites_existing(tmp_path: Path) -> None:
    """update=True silently overwrites a stale golden file."""
    expected_path = tmp_path / "golden.txt"
    expected_path.write_text("old content\n", encoding="utf-8")

    comparator = GoldenComparator(update=True)
    comparator.compare(expected_path, "new content\n")

    assert expected_path.read_text() == "new content\n"


# ---------------------------------------------------------------------------
# GoldenComparator — compare path (update=False)
# ---------------------------------------------------------------------------


def test_golden_comparator_missing_file_fails(tmp_path: Path) -> None:
    """When the golden file does not exist, pytest.fail is called."""
    comparator = GoldenComparator(update=False)
    with pytest.raises(pytest.fail.Exception, match="Golden file missing"):
        comparator.compare(tmp_path / "nonexistent.txt", "actual")


def test_golden_comparator_mismatch_fails_with_diff(tmp_path: Path) -> None:
    """A content mismatch triggers pytest.fail with a unified diff in the message."""
    expected_path = tmp_path / "golden.txt"
    expected_path.write_text("expected content\n", encoding="utf-8")

    comparator = GoldenComparator(update=False)
    with pytest.raises(pytest.fail.Exception, match="Golden mismatch"):
        comparator.compare(expected_path, "actual content\n", label="mytest")


def test_golden_comparator_match_passes(tmp_path: Path) -> None:
    """Identical content does not raise."""
    expected_path = tmp_path / "golden.txt"
    expected_path.write_text("same content\n", encoding="utf-8")

    comparator = GoldenComparator(update=False)
    # Should complete without exception.
    comparator.compare(expected_path, "same content\n")


def test_golden_comparator_label_defaults_to_filename(tmp_path: Path) -> None:
    """When label is omitted the filename appears in the failure message."""
    expected_path = tmp_path / "myfile.txt"
    expected_path.write_text("foo\n", encoding="utf-8")

    comparator = GoldenComparator(update=False)
    with pytest.raises(pytest.fail.Exception, match="myfile.txt"):
        comparator.compare(expected_path, "bar\n")


# ---------------------------------------------------------------------------
# golden_fixtures fixture — smoke
# ---------------------------------------------------------------------------


def test_golden_fixtures_path_exists(golden_fixtures: Path) -> None:
    """The golden_fixtures fixture resolves to an existing directory."""
    assert golden_fixtures.is_dir()
