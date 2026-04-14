"""Tests for schema.toml loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_research.schema import PromptTemplate, Schema, load_schema

VALID_SCHEMA = """
[wiki]
name = "ai-research"
version = 1

[[page_templates]]
id = "concept"
path_prefix = "concepts/"
frontmatter_required = ["title", "tags"]

[[page_templates]]
id = "source"
path_prefix = "sources/"
frontmatter_required = ["title", "source_type", "sha256"]
"""

VALID_SCHEMA_WITH_PROMPT = """
[wiki]
name = "ai-research"
version = 1

[prompts.page_draft]
sections = ["Summary", "Key Claims", "Connections"]
tone = "neutral, encyclopedic"
bullet_density = "prefer bullets over prose for claims"
instructions = \"\"\"Draft an Obsidian-compatible wiki page.
Use [[wikilinks]] for cross-references.\"\"\"
"""


def test_load_schema_valid(tmp_path: Path) -> None:
    schema_path = tmp_path / "schema.toml"
    schema_path.write_text(VALID_SCHEMA)
    schema = load_schema(schema_path)
    assert isinstance(schema, Schema)
    assert schema.wiki.name == "ai-research"
    assert schema.wiki.version == 1
    assert len(schema.page_templates) == 2
    assert schema.page_templates[0].id == "concept"
    assert schema.page_templates[1].frontmatter_required == [
        "title",
        "source_type",
        "sha256",
    ]


def test_load_schema_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_schema(tmp_path / "nope.toml")


def test_load_schema_corrupt_raises(tmp_path: Path) -> None:
    schema_path = tmp_path / "schema.toml"
    schema_path.write_text("this is = not = valid toml [[[")
    with pytest.raises(ValueError):
        load_schema(schema_path)


def test_load_schema_invalid_structure_raises(tmp_path: Path) -> None:
    schema_path = tmp_path / "schema.toml"
    # Missing required [wiki] table
    schema_path.write_text('[[page_templates]]\nid = "x"\npath_prefix = "x/"\n')
    with pytest.raises(ValueError):
        load_schema(schema_path)


def test_load_schema_without_prompts_backwards_compatible(tmp_path: Path) -> None:
    """Schemas predating prompt templates still load with prompts == None."""
    schema_path = tmp_path / "schema.toml"
    schema_path.write_text(VALID_SCHEMA)
    schema = load_schema(schema_path)
    assert schema.prompts is None


def test_load_schema_with_page_draft_prompt(tmp_path: Path) -> None:
    schema_path = tmp_path / "schema.toml"
    schema_path.write_text(VALID_SCHEMA_WITH_PROMPT)
    schema = load_schema(schema_path)
    assert schema.prompts is not None
    page_draft = schema.prompts.page_draft
    assert isinstance(page_draft, PromptTemplate)
    assert page_draft.sections == ["Summary", "Key Claims", "Connections"]
    assert page_draft.tone == "neutral, encyclopedic"
    assert page_draft.bullet_density is not None
    assert "Obsidian" in (page_draft.instructions or "")


def test_load_schema_prompt_requires_non_empty_sections(tmp_path: Path) -> None:
    schema_path = tmp_path / "schema.toml"
    schema_path.write_text(
        """
[wiki]
name = "ai-research"
version = 1

[prompts.page_draft]
sections = []
"""
    )
    with pytest.raises(ValueError):
        load_schema(schema_path)


def test_load_schema_prompt_rejects_blank_section(tmp_path: Path) -> None:
    schema_path = tmp_path / "schema.toml"
    schema_path.write_text(
        """
[wiki]
name = "ai-research"
version = 1

[prompts.page_draft]
sections = ["Summary", "   "]
"""
    )
    with pytest.raises(ValueError):
        load_schema(schema_path)


def test_reference_schema_toml_loads() -> None:
    """The committed reference .ai-research/schema.toml validates."""
    repo_root = Path(__file__).resolve().parents[1]
    reference = repo_root / ".ai-research" / "schema.toml"
    assert reference.exists(), f"missing reference schema at {reference}"
    schema = load_schema(reference)
    assert schema.prompts is not None
    assert schema.prompts.page_draft.sections, "reference must define page_draft sections"
