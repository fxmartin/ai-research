"""Tests for the source archival helper (Story 01.3-003)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from ai_research.archive import (
    ArchiveHashCollisionError,
    archive_source,
    compute_archive_path,
    slugify,
)

# --- slug generation -------------------------------------------------------


def test_slugify_basic() -> None:
    assert slugify("Attention Is All You Need") == "attention-is-all-you-need"


def test_slugify_strips_punctuation_and_collapses_whitespace() -> None:
    assert slugify("  Hello, World!!  Foo___Bar  ") == "hello-world-foo-bar"


def test_slugify_unicode_ascii_fallback() -> None:
    # Non-ASCII chars are dropped; we stay in ASCII for cross-FS safety.
    assert slugify("naïve café") == "naive-cafe"


def test_slugify_empty_yields_untitled() -> None:
    assert slugify("") == "untitled"
    assert slugify("   ") == "untitled"
    assert slugify("!!!") == "untitled"


def test_slugify_truncates_long_input() -> None:
    long = "word " * 40
    out = slugify(long, max_len=60)
    assert len(out) <= 60
    assert not out.endswith("-")


# --- path computation ------------------------------------------------------


def test_compute_archive_path_shape(tmp_path: Path) -> None:
    src = tmp_path / "paper.pdf"
    src.write_bytes(b"pdf-bytes")
    fixed = datetime(2026, 3, 7, tzinfo=UTC)
    path = compute_archive_path(
        source=src,
        sources_root=tmp_path / "sources",
        title="Attention Is All You Need",
        now=fixed,
    )
    # <root>/2026/03/<hash12>-<slug>.pdf
    assert path.parent == tmp_path / "sources" / "2026" / "03"
    assert path.suffix == ".pdf"
    name = path.name
    hash_part, _, rest = name.partition("-")
    assert len(hash_part) == 12
    assert rest.startswith("attention-is-all-you-need")


def test_compute_archive_path_falls_back_to_filename_stem(tmp_path: Path) -> None:
    src = tmp_path / "MyNotes.md"
    src.write_bytes(b"hi")
    fixed = datetime(2026, 1, 1, tzinfo=UTC)
    path = compute_archive_path(
        source=src,
        sources_root=tmp_path / "sources",
        title=None,
        now=fixed,
    )
    assert path.name.split("-", 1)[1] == "mynotes.md"


# --- archive_source behavior ----------------------------------------------


def test_archive_source_moves_file_fresh(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()
    src = raw / "paper.pdf"
    src.write_bytes(b"hello world")
    fixed = datetime(2026, 4, 14, tzinfo=UTC)

    dest = archive_source(
        source=src,
        sources_root=tmp_path / "sources",
        title="My Paper",
        now=fixed,
    )

    assert dest.exists()
    assert not src.exists(), "source should be moved, not copied"
    assert dest.read_bytes() == b"hello world"
    assert dest.parent == tmp_path / "sources" / "2026" / "04"


def test_archive_source_idempotent_same_hash(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()
    # First archive
    src1 = raw / "paper.pdf"
    src1.write_bytes(b"identical-bytes")
    fixed = datetime(2026, 4, 14, tzinfo=UTC)
    dest1 = archive_source(
        source=src1,
        sources_root=tmp_path / "sources",
        title="Paper",
        now=fixed,
    )

    # Second, identical content at a new raw path
    src2 = raw / "paper-copy.pdf"
    src2.write_bytes(b"identical-bytes")
    dest2 = archive_source(
        source=src2,
        sources_root=tmp_path / "sources",
        title="Paper",
        now=fixed,
    )

    assert dest2 == dest1
    assert dest2.read_bytes() == b"identical-bytes"
    assert not src2.exists(), "duplicate source must be deleted on idempotent archive"


def test_archive_source_hash_collision_raises(tmp_path: Path) -> None:
    """If the computed target path exists but bytes differ, refuse to overwrite."""
    raw = tmp_path / "raw"
    raw.mkdir()
    fixed = datetime(2026, 4, 14, tzinfo=UTC)

    src1 = raw / "a.pdf"
    src1.write_bytes(b"A-bytes")
    dest1 = archive_source(
        source=src1,
        sources_root=tmp_path / "sources",
        title="Paper",
        now=fixed,
    )

    # Tamper: replace the archived bytes so hash mismatches what the path implies.
    dest1.write_bytes(b"TAMPERED-bytes")

    src2 = raw / "b.pdf"
    src2.write_bytes(b"A-bytes")

    with pytest.raises(ArchiveHashCollisionError):
        archive_source(
            source=src2,
            sources_root=tmp_path / "sources",
            title="Paper",
            now=fixed,
        )
    # Source preserved for manual review on collision.
    assert src2.exists()


def test_archive_source_missing_source(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        archive_source(
            source=tmp_path / "nope.pdf",
            sources_root=tmp_path / "sources",
        )


def test_archive_source_creates_parent_dirs(tmp_path: Path) -> None:
    src = tmp_path / "x.md"
    src.write_bytes(b"data")
    dest = archive_source(
        source=src,
        sources_root=tmp_path / "nested" / "sources-root",
    )
    assert dest.exists()
    assert dest.parent.is_dir()
