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


# ---------------------------------------------------------------------------
# Coverage-gate additions: contract tests for story 03.1-002
# ---------------------------------------------------------------------------


def test_wiki_meta_version_defaults_to_1(tmp_path: Path) -> None:
    """WikiMeta.version should default to 1 when omitted from TOML."""
    schema_path = tmp_path / "schema.toml"
    schema_path.write_text('[wiki]\nname = "test-wiki"\n')
    schema = load_schema(schema_path)
    assert schema.wiki.version == 1


def test_page_template_frontmatter_required_defaults_empty(tmp_path: Path) -> None:
    """PageTemplate.frontmatter_required should default to [] when omitted."""
    schema_path = tmp_path / "schema.toml"
    schema_path.write_text(
        '[wiki]\nname = "test-wiki"\n\n[[page_templates]]\nid = "note"\npath_prefix = "notes/"\n'
    )
    schema = load_schema(schema_path)
    assert schema.page_templates[0].frontmatter_required == []


def test_prompt_template_sections_only(tmp_path: Path) -> None:
    """PromptTemplate is valid with only the required ``sections`` field."""
    schema_path = tmp_path / "schema.toml"
    schema_path.write_text(
        '[wiki]\nname = "test-wiki"\n\n[prompts.page_draft]\nsections = ["Summary"]\n'
    )
    schema = load_schema(schema_path)
    assert schema.prompts is not None
    pt = schema.prompts.page_draft
    assert pt.sections == ["Summary"]
    assert pt.tone is None
    assert pt.bullet_density is None
    assert pt.instructions is None


def test_load_schema_accepts_string_path(tmp_path: Path) -> None:
    """load_schema should coerce a str argument to Path internally."""
    schema_path = tmp_path / "schema.toml"
    schema_path.write_text('[wiki]\nname = "test-wiki"\n')
    schema = load_schema(str(schema_path))  # type: ignore[arg-type]
    assert schema.wiki.name == "test-wiki"


def test_prompt_template_sections_whitespace_stripped(tmp_path: Path) -> None:
    """Section heading strings with leading/trailing whitespace are stripped."""
    schema_path = tmp_path / "schema.toml"
    schema_path.write_text(
        "[wiki]\n"
        'name = "test-wiki"\n\n'
        "[prompts.page_draft]\n"
        'sections = ["  Summary  ", " Key Claims "]\n'
    )
    schema = load_schema(schema_path)
    assert schema.prompts is not None
    assert schema.prompts.page_draft.sections == ["Summary", "Key Claims"]


def test_schema_no_page_templates_is_valid(tmp_path: Path) -> None:
    """A schema with no [[page_templates]] entries is valid (defaults to [])."""
    schema_path = tmp_path / "schema.toml"
    schema_path.write_text('[wiki]\nname = "test-wiki"\n')
    schema = load_schema(schema_path)
    assert schema.page_templates == []
