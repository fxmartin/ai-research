"""Scan a wiki/raw/ inbox directory for files eligible for ingest.

Zero LLM calls. Deterministic file-ops verb used by ``/ingest-inbox`` to iterate
safely: files that were modified less than ``min_age_seconds`` ago are skipped
(they may still be in the middle of a copy), and files whose SHA-256 is already
recorded in :class:`~ai_research.state.State.sources` can be skipped when
``skip_known`` is set.
"""

from __future__ import annotations

import hashlib
import time
from pathlib import Path

from ai_research.state import State

__all__ = ["DEFAULT_MIN_AGE_SECONDS", "scan_raw", "sha256_file"]

DEFAULT_MIN_AGE_SECONDS: float = 5.0

# Stream file contents through SHA-256 in 64 KiB chunks so scanning a large
# inbox does not need to hold entire files in memory.
_HASH_CHUNK_BYTES = 64 * 1024


def sha256_file(path: Path) -> str:
    """Return the hex SHA-256 digest of ``path``'s bytes."""
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(_HASH_CHUNK_BYTES):
            h.update(chunk)
    return h.hexdigest()


def scan_raw(
    raw_dir: Path,
    *,
    min_age_seconds: float = DEFAULT_MIN_AGE_SECONDS,
    skip_known: bool = False,
    state: State | None = None,
    now: float | None = None,
) -> list[str]:
    """List files in ``raw_dir`` eligible for ingest.

    A file is eligible when:

    * It is a regular file (directories and symlinks-to-dirs are ignored).
    * Its name does not start with ``.`` (dotfiles like ``.gitkeep`` and
      ``.DS_Store`` are never real sources).
    * Its mtime is at least ``min_age_seconds`` in the past — this guards
      against partial writes from a still-running copy.
    * If ``skip_known`` is set, its SHA-256 is not already present in
      ``state.sources``.

    Args:
        raw_dir: Directory to scan. Must exist.
        min_age_seconds: Minimum age (seconds) since last mtime. Defaults to 5.
        skip_known: When True, hash each candidate and exclude those already
            recorded in ``state.sources``.
        state: State ledger used for ``skip_known`` lookups. When ``skip_known``
            is True but ``state`` is ``None``, an empty :class:`State` is used
            (i.e. nothing is considered known).
        now: Optional override for the reference time (seconds since epoch),
            primarily for deterministic testing.

    Returns:
        Sorted list of absolute file paths (as strings).

    Raises:
        FileNotFoundError: If ``raw_dir`` does not exist.
    """
    raw_dir = Path(raw_dir)
    if not raw_dir.exists():
        raise FileNotFoundError(f"raw directory not found: {raw_dir}")

    reference = time.time() if now is None else now
    known_hashes = set(state.sources.keys()) if (skip_known and state is not None) else set()

    eligible: list[str] = []
    for entry in sorted(raw_dir.iterdir()):
        if not entry.is_file():
            continue
        if entry.name.startswith("."):
            continue
        mtime = entry.stat().st_mtime
        if reference - mtime < min_age_seconds:
            continue
        if skip_known and known_hashes and sha256_file(entry) in known_hashes:
            continue
        eligible.append(str(entry.resolve()))

    return eligible
