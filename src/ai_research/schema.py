"""Typed loader for ``.ai-research/schema.toml``.

The schema declares wiki metadata, page templates, and prompt templates used
by slash commands. Parsing uses stdlib ``tomllib`` and the result is validated
through Pydantic so downstream verbs and slash-command prose can rely on a
typed object rather than poking at raw dicts.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import BaseModel, Field, field_validator

__all__ = [
    "PageTemplate",
    "PromptTemplate",
    "Prompts",
    "Schema",
    "WikiMeta",
    "load_schema",
]


class WikiMeta(BaseModel):
    """Top-level ``[wiki]`` metadata table."""

    name: str
    version: int = 1


class PageTemplate(BaseModel):
    """A single ``[[page_templates]]`` entry."""

    id: str
    path_prefix: str
    frontmatter_required: list[str] = Field(default_factory=list)


class PromptTemplate(BaseModel):
    """A structured prompt template consumed by slash commands.

    The template is pure data — no LLM call happens in the Python toolkit.
    Slash-command prose (e.g. ``.claude/commands/ingest.md``) reads this
    through the schema loader and splices it into Claude's drafting context.
    """

    sections: list[str] = Field(
        ...,
        description="Ordered H2 headings the drafted page must contain.",
    )
    tone: str | None = Field(
        default=None,
        description="Short free-form guidance on voice (e.g. 'neutral, encyclopedic').",
    )
    bullet_density: str | None = Field(
        default=None,
        description="Guidance on when to prefer bullets vs prose.",
    )
    instructions: str | None = Field(
        default=None,
        description="Additional drafting directives appended verbatim to the prompt.",
    )

    @field_validator("sections")
    @classmethod
    def _sections_non_empty(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("sections must contain at least one heading")
        cleaned: list[str] = []
        for section in value:
            stripped = section.strip()
            if not stripped:
                raise ValueError("section headings must be non-blank strings")
            cleaned.append(stripped)
        return cleaned


class Prompts(BaseModel):
    """Container for named prompt templates under ``[prompts.*]``."""

    page_draft: PromptTemplate


class Schema(BaseModel):
    """Parsed ``schema.toml`` document."""

    wiki: WikiMeta
    page_templates: list[PageTemplate] = Field(default_factory=list)
    prompts: Prompts | None = None


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
