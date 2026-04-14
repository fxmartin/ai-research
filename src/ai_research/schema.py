"""Typed loader for ``.ai-research/schema.toml``.

The schema declares wiki metadata and page templates. Parsing uses stdlib
``tomllib`` and the result is validated through Pydantic so downstream verbs
can rely on a typed object rather than poking at raw dicts.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import BaseModel, Field

__all__ = ["PageTemplate", "Schema", "WikiMeta", "load_schema"]


class WikiMeta(BaseModel):
    """Top-level ``[wiki]`` metadata table."""

    name: str
    version: int = 1


class PageTemplate(BaseModel):
    """A single ``[[page_templates]]`` entry."""

    id: str
    path_prefix: str
    frontmatter_required: list[str] = Field(default_factory=list)


class Schema(BaseModel):
    """Parsed ``schema.toml`` document."""

    wiki: WikiMeta
    page_templates: list[PageTemplate] = Field(default_factory=list)


def load_schema(path: Path) -> Schema:
    """Load and validate ``schema.toml`` at ``path``.

    Raises:
        FileNotFoundError: if ``path`` does not exist.
        ValueError: if the TOML is malformed or fails schema validation.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"schema file not found: {path}")
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"schema file at {path} is not valid TOML: {exc}") from exc
    try:
        return Schema.model_validate(raw)
    except Exception as exc:  # pydantic ValidationError
        raise ValueError(f"schema file at {path} failed validation: {exc}") from exc
