"""Source archival helper (Story 01.3-003).

Moves an ingested file from a staging location (typically ``raw/``) into the
immutable ``sources/<yyyy>/<mm>/<hash>-<slug>.<ext>`` archive.

The helper is intentionally the *single* archival implementation that slash
commands and future verbs (e.g. ``materialize``) share. It is a pure file-ops
utility: no LLM calls, no state.json mutation. Callers that need to update
``state.json`` should do so after :func:`archive_source` returns the final
archive path.

Design notes
------------
- **Atomic move**: we use :func:`shutil.move`, which falls back to copy+unlink
  across filesystems but is a simple rename on the same volume (the expected
  case when ``raw/`` and ``sources/`` share a disk).
- **Idempotency** is keyed on the SHA-256 of the source bytes and encoded into
  the target filename (first 12 hex chars). If the target exists and its bytes
  hash to the same value, the helper deletes the incoming source and returns
  the existing path — so running ingest twice is a no-op.
- **Collision** means the target path exists but its bytes hash differently.
  This is treated as operator error (a handcrafted file planted under the
  archive, or a truncated write from a prior crash) and requires manual
  review; we refuse to overwrite.
"""

from __future__ import annotations

import hashlib
import re
import shutil
import unicodedata
from datetime import UTC, datetime
from pathlib import Path

__all__ = [
    "ArchiveError",
    "ArchiveHashCollisionError",
    "HASH_PREFIX_LEN",
    "archive_source",
    "compute_archive_path",
    "slugify",
]


HASH_PREFIX_LEN = 12
"""Number of hex chars of the SHA-256 digest embedded in the archive filename.

12 hex chars = 48 bits, collision-resistant enough for a personal wiki while
keeping filenames readable.
"""

_SLUG_MAX_LEN = 80


class ArchiveError(Exception):
    """Base class for archival errors."""


class ArchiveHashCollisionError(ArchiveError):
    """Raised when an archive target exists with a different hash than expected.

    This indicates the archive was tampered with, truncated by a crash, or a
    genuine (astronomically unlikely) hash-prefix collision. Either way, the
    caller must review manually — we do not overwrite archival bytes.
    """


def slugify(value: str, *, max_len: int = _SLUG_MAX_LEN) -> str:
    """Return a filesystem-safe ASCII slug for ``value``.

    - NFKD-normalize and strip combining marks so accented characters
      degrade to ASCII (``café`` -> ``cafe``).
    - Lower-case; non ``[a-z0-9]+`` runs collapse to a single dash.
    - Strip leading/trailing dashes, truncate to ``max_len``, and guarantee a
      non-empty result (``"untitled"`` fallback).
    """
    # Decompose accents, then keep only ASCII bytes.
    normalized = unicodedata.normalize("NFKD", value)
    ascii_bytes = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_lower = ascii_bytes.lower()
    # Collapse any non-alnum run to a single dash.
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_lower).strip("-")
    if not slug:
        return "untitled"
    if len(slug) > max_len:
        slug = slug[:max_len].rstrip("-")
    return slug or "untitled"


def _sha256_of_file(path: Path) -> str:
    """Return hex SHA-256 of the file bytes, streaming to bound memory."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def compute_archive_path(
    *,
    source: Path,
    sources_root: Path,
    title: str | None = None,
    now: datetime | None = None,
) -> Path:
    """Compute the canonical archive path for ``source``.

    The layout is ``<sources_root>/<yyyy>/<mm>/<hash12>-<slug><ext>`` where:
    - ``yyyy/mm`` comes from ``now`` (UTC; defaults to :func:`datetime.utcnow`).
    - ``hash12`` is the first :data:`HASH_PREFIX_LEN` chars of the file's
      SHA-256 digest.
    - ``slug`` is derived from ``title`` when provided, else from the source
      filename stem.
    - ``ext`` preserves the source extension (case-folded).
    """
    source = Path(source)
    when = (now or datetime.now(tz=UTC)).astimezone(UTC)
    digest = _sha256_of_file(source)
    prefix = digest[:HASH_PREFIX_LEN]
    slug_basis = title if title else source.stem
    slug = slugify(slug_basis)
    ext = source.suffix.lower()
    filename = f"{prefix}-{slug}{ext}"
    return Path(sources_root) / f"{when.year:04d}" / f"{when.month:02d}" / filename


def archive_source(
    *,
    source: Path,
    sources_root: Path,
    title: str | None = None,
    now: datetime | None = None,
) -> Path:
    """Move ``source`` into the archive and return the final archive path.

    Behavior:
    - Fresh target: parent dirs are created and the file is moved via
      :func:`shutil.move`.
    - Target exists with matching hash: the incoming ``source`` is deleted and
      the existing archive path is returned (idempotent).
    - Target exists with differing hash: :class:`ArchiveHashCollisionError`
      is raised and the incoming ``source`` is left in place for manual
      review.

    Args:
        source: Path to the file currently living in ``raw/`` (or equivalent).
        sources_root: Root of the archive (typically ``<repo>/sources``).
        title: Optional human-readable title; drives the slug when present,
            else we fall back to the source filename stem.
        now: Override the wall clock (used by tests for deterministic paths).

    Returns:
        The absolute(-ish) path to the archived file.

    Raises:
        FileNotFoundError: ``source`` does not exist.
        ArchiveHashCollisionError: target exists with mismatched bytes.
    """
    src = Path(source)
    if not src.exists():
        raise FileNotFoundError(f"No such source file: {src}")

    target = compute_archive_path(
        source=src,
        sources_root=sources_root,
        title=title,
        now=now,
    )

    if target.exists():
        # Idempotency gate: only accept when the archived bytes match the
        # incoming bytes. Anything else demands operator attention.
        incoming_hash = _sha256_of_file(src)
        existing_hash = _sha256_of_file(target)
        if incoming_hash == existing_hash:
            src.unlink()
            return target
        raise ArchiveHashCollisionError(
            f"archive target {target} exists with hash {existing_hash} "
            f"but incoming source {src} hashes to {incoming_hash}; "
            "refusing to overwrite — manual review required."
        )

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(target))
    return target
