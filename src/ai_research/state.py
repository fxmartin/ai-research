"""State persistence for ai-research.

`state.json` is the durable idempotency ledger: source hash -> page path, plus a
reverse page -> sources index. All writes are atomic (temp file + ``os.replace``)
so concurrent writers or crashes can never leave a half-written JSON blob on
disk.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from pydantic import BaseModel, Field

__all__ = [
    "State",
    "atomic_write",
    "find_page_by_source_hash",
    "load_state",
    "save_state",
]


class State(BaseModel):
    """Durable ingest state.

    Attributes:
        sources: Map of source ``sha256`` -> relative wiki page path.
        pages: Reverse index of page path -> list of source hashes that
            contributed to it.
    """

    sources: dict[str, str] = Field(default_factory=dict)
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


def load_state(path: Path) -> State:
    """Load state from ``path``; return an empty :class:`State` if missing.

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
    try:
        return State.model_validate(raw)
    except Exception as exc:  # pydantic ValidationError
        raise ValueError(f"state file at {path} failed schema validation: {exc}") from exc


def save_state(path: Path, state: State) -> None:
    """Persist ``state`` to ``path`` atomically."""
    payload = json.dumps(
        state.model_dump(),
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
    ).encode("utf-8")
    atomic_write(Path(path), payload)


def find_page_by_source_hash(state: State, source_hash: str) -> str | None:
    """Return the page path associated with ``source_hash`` or ``None``."""
    return state.sources.get(source_hash)
