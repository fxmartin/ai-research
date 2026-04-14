"""Markdown / plain-text passthrough extractor (Story 01.2-003).

The extractor is intentionally lossless: the ``text`` field in the returned
record is the *verbatim* file content (including any YAML frontmatter block),
so downstream materialization can round-trip bytes unchanged. Frontmatter, if
present, is additionally parsed into ``metadata.frontmatter`` for callers that
want structured access without re-parsing.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, TypedDict

import frontmatter

SUPPORTED_SUFFIXES: frozenset[str] = frozenset({".md", ".markdown", ".txt"})


class ExtractMetadata(TypedDict):
    """Structured metadata produced by the markdown extractor."""

    source_type: str
    sha256: str
    path: str
    frontmatter: dict[str, Any]


class ExtractResult(TypedDict):
    """Canonical extractor return shape: ``{text, metadata}``."""

    text: str
    metadata: ExtractMetadata


def extract_markdown(path: str | Path) -> dict[str, Any]:
    """Extract a local markdown / text file into an ``{text, metadata}`` record.

    The file bytes are returned untouched under ``text`` to preserve any
    frontmatter block verbatim; the parsed frontmatter (if any) is exposed
    separately under ``metadata.frontmatter``.

    Args:
        path: Filesystem path to a ``.md``, ``.markdown``, or ``.txt`` file.

    Returns:
        A mapping with ``text`` (raw file content) and ``metadata`` containing
        ``source_type``, ``sha256`` (of the raw bytes), resolved ``path``, and
        parsed ``frontmatter`` (empty dict when none is present).

    Raises:
        FileNotFoundError: The path does not exist.
        ValueError: The file extension is not a supported markdown/text type.
    """
    src = Path(path)
    if not src.exists():
        raise FileNotFoundError(f"No such file: {src}")
    if src.suffix.lower() not in SUPPORTED_SUFFIXES:
        raise ValueError(
            f"Unsupported extension for markdown extractor: {src.suffix!r}. "
            f"Expected one of: {sorted(SUPPORTED_SUFFIXES)}"
        )

    raw_bytes = src.read_bytes()
    text = raw_bytes.decode("utf-8")
    parsed_meta = _parse_frontmatter(text)

    metadata: ExtractMetadata = {
        "source_type": "markdown",
        "sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "path": str(src.resolve()),
        "frontmatter": parsed_meta,
    }
    return {"text": text, "metadata": metadata}


def _parse_frontmatter(text: str) -> dict[str, Any]:
    """Return parsed YAML frontmatter (or ``{}`` if none / unparseable).

    We deliberately swallow parse errors: an invalid frontmatter block should
    not prevent ingestion of the file body. The ``text`` field keeps the
    original bytes, so a human curator can still repair the block later.
    """
    try:
        post = frontmatter.loads(text)
    except Exception:
        return {}
    return dict(post.metadata)
