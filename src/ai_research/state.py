"""State persistence for ai-research.

`state.json` is the durable idempotency ledger: source hash ->
:class:`SourceRecord` (page path + optional archive path), plus a reverse
page -> sources index. All writes are atomic (temp file + ``os.replace``) so
concurrent writers or crashes can never leave a half-written JSON blob on
disk.

Schema evolution (Story 07.1-001):
    The pre-07.1 schema stored ``sources[hash]`` as a plain string (the page
    path). :func:`load_state` transparently migrates old-format records to the
    new dict shape (``archive_path`` defaults to ``None``) so on-disk files
    written by earlier releases keep loading cleanly. The migration is
    in-memory; the new shape is persisted on the next :func:`save_state`.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

__all__ = [
    "SourceRecord",
    "State",
    "atomic_write",
    "find_page_by_source_hash",
    "load_state",
    "save_state",
]

logger = logging.getLogger(__name__)


class SourceRecord(BaseModel):
    """A single source's ingest record.

    Attributes:
        page: Relative (or absolute) wiki page path the source was
            materialized into.
        archive_path: Relative (or absolute) path under ``sources/`` where the
            raw bytes live, once archived. ``None`` for pre-07.1 records that
            predate archiving, or for sources that have not yet been moved.
    """

    page: str
    archive_path: str | None = None


class State(BaseModel):
    """Durable ingest state.

    Attributes:
        sources: Map of source ``sha256`` -> :class:`SourceRecord`.
        pages: Reverse index of page path -> list of source hashes that
            contributed to it.
    """

    sources: dict[str, SourceRecord] = Field(default_factory=dict)
    pages: dict[str, list[str]] = Field(default_factory=dict)


def atomic_write(path: Path, data: bytes) -> None:
    """Write ``data`` to ``path`` atomically.

    Writes to a sibling temp file on the same filesystem, fsyncs, then calls
    ``os.replace`` which is atomic on POSIX and Windows. On any failure the
    temp file is removed and the original (if any) is untouched.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(
        prefix=f"{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(str(tmp_path), str(path))
    except BaseException:
        # Best-effort cleanup of the temp file if rename never happened.
        try:
            tmp_path.unlink()
        except FileNotFoundError:
            pass
        raise


def _migrate_sources(raw_sources: Any) -> dict[str, dict[str, Any]]:
    """Normalize pre-07.1 string-valued ``sources`` entries to the dict shape.

    Old format: ``{"<hash>": "wiki/foo.md"}``
    New format: ``{"<hash>": {"page": "wiki/foo.md", "archive_path": null}}``

    Any entries already in the new dict shape are passed through untouched.
    Non-dict ``raw_sources`` is returned as-is so pydantic surfaces a clear
    schema-validation error downstream.
    """
    if not isinstance(raw_sources, dict):
        return raw_sources
    migrated: dict[str, dict[str, Any]] = {}
    did_migrate = False
    for source_hash, value in raw_sources.items():
        if isinstance(value, str):
            migrated[source_hash] = {"page": value, "archive_path": None}
            did_migrate = True
        else:
            migrated[source_hash] = value
    if did_migrate:
        logger.warning(
            "state.json: migrated %d pre-07.1 string-valued source record(s) "
            "to the new {page, archive_path} shape; run will persist on next save.",
            sum(1 for v in raw_sources.values() if isinstance(v, str)),
        )
    return migrated


def load_state(path: Path) -> State:
    """Load state from ``path``; return an empty :class:`State` if missing.

    Transparently migrates the pre-07.1 string-valued ``sources`` schema to
    the new :class:`SourceRecord` dict shape in memory.

    Raises:
        ValueError: if the file exists but is not valid JSON / schema.
    """
    path = Path(path)
    if not path.exists():
        return State()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"state file at {path} is not valid JSON: {exc}") from exc
    if isinstance(raw, dict) and "sources" in raw:
        raw = {**raw, "sources": _migrate_sources(raw["sources"])}
    try:
        return State.model_validate(raw)
    except Exception as exc:  # pydantic ValidationError
        raise ValueError(f"state file at {path} failed schema validation: {exc}") from exc


def save_state(path: Path, state: State) -> None:
    """Persist ``state`` to ``path`` atomically in the post-07.1 schema."""
    payload = json.dumps(
        state.model_dump(),
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
    ).encode("utf-8")
    atomic_write(Path(path), payload)


def find_page_by_source_hash(state: State, source_hash: str) -> str | None:
    """Return the page path associated with ``source_hash`` or ``None``."""
    record = state.sources.get(source_hash)
    return record.page if record is not None else None
