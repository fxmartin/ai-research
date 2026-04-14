"""Tests for schema.toml loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_research.schema import Schema, load_schema

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
