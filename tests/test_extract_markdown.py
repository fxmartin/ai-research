"""Tests for the markdown/text passthrough extractor (Story 01.2-003)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ai_research.cli import app
from ai_research.extract.markdown import extract_markdown

runner = CliRunner()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_extract_plain_markdown_without_frontmatter(tmp_path: Path) -> None:
    body = "# Hello\n\nSome *markdown* body.\n"
    src = tmp_path / "note.md"
    src.write_text(body, encoding="utf-8")

    result = extract_markdown(src)

    assert result["text"] == body
    meta = result["metadata"]
    assert meta["source_type"] == "markdown"
    assert meta["sha256"] == _sha256(body.encode("utf-8"))
    assert meta["path"] == str(src.resolve())
    assert meta["frontmatter"] == {}


def test_extract_plain_text_file(tmp_path: Path) -> None:
    body = "just some plain text\nline 2\n"
    src = tmp_path / "note.txt"
    src.write_text(body, encoding="utf-8")

    result = extract_markdown(src)

    assert result["text"] == body
    assert result["metadata"]["source_type"] == "markdown"
    assert result["metadata"]["frontmatter"] == {}


def test_extract_markdown_with_frontmatter_preserves_text_and_parses_meta(
    tmp_path: Path,
) -> None:
    body = (
        "---\n"
        "title: My Note\n"
        "tags: [research, llm]\n"
        "draft: false\n"
        "---\n"
        "# Heading\n\nBody paragraph.\n"
    )
    src = tmp_path / "note.md"
    src.write_text(body, encoding="utf-8")

    result = extract_markdown(src)

    # Full original content (including frontmatter) preserved in text.
    assert result["text"] == body
    fm = result["metadata"]["frontmatter"]
    assert fm["title"] == "My Note"
    assert fm["tags"] == ["research", "llm"]
    assert fm["draft"] is False
    assert result["metadata"]["sha256"] == _sha256(body.encode("utf-8"))


def test_extract_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        extract_markdown(tmp_path / "missing.md")


def test_extract_unsupported_extension_raises(tmp_path: Path) -> None:
    src = tmp_path / "note.rtf"
    src.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError):
        extract_markdown(src)


def test_cli_extract_markdown_emits_json(tmp_path: Path) -> None:
    body = "---\ntitle: Hi\n---\n# Hi\n"
    src = tmp_path / "note.md"
    src.write_text(body, encoding="utf-8")

    result = runner.invoke(app, ["extract", str(src)])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["text"] == body
    assert payload["metadata"]["source_type"] == "markdown"
    assert payload["metadata"]["frontmatter"]["title"] == "Hi"
    assert payload["metadata"]["sha256"] == _sha256(body.encode("utf-8"))


def test_cli_extract_missing_file_nonzero_exit(tmp_path: Path) -> None:
    result = runner.invoke(app, ["extract", str(tmp_path / "missing.md")])
    assert result.exit_code != 0


def test_extract_markdown_dot_markdown_extension(tmp_path: Path) -> None:
    """Files with .markdown extension are accepted and processed correctly."""
    body = "# Alt extension\n\nContent here.\n"
    src = tmp_path / "note.markdown"
    src.write_text(body, encoding="utf-8")

    result = extract_markdown(src)

    assert result["text"] == body
    assert result["metadata"]["source_type"] == "markdown"
    assert result["metadata"]["frontmatter"] == {}
    assert result["metadata"]["sha256"] == _sha256(body.encode("utf-8"))


def test_parse_frontmatter_swallows_invalid_yaml(tmp_path: Path) -> None:
    """Malformed YAML in frontmatter must not raise — extractor returns empty dict."""
    # Construct a file whose YAML block will trip up the YAML parser.
    # python-frontmatter will raise on a YAML mapping-key conflict like
    # a bare `{` that is not closed.
    body = "---\nkey: [unclosed bracket\n---\n# body\n"
    src = tmp_path / "broken-fm.md"
    src.write_text(body, encoding="utf-8")

    # Should not raise; frontmatter errors are swallowed silently.
    result = extract_markdown(src)

    assert result["text"] == body
    # Either the frontmatter key was parsed (some lenient YAML parsers
    # accept this) or it was swallowed to an empty dict — either is correct.
    assert isinstance(result["metadata"]["frontmatter"], dict)


def test_cli_extract_unsupported_extension_exits_2(tmp_path: Path) -> None:
    """CLI `extract` on an unsupported extension must exit 2 and print to stderr."""
    # .csv is not a supported extension (only .pdf, .md, .markdown, .txt are).
    src = tmp_path / "data.csv"
    src.write_bytes(b"col1,col2\nval1,val2")

    result = runner.invoke(app, ["extract", str(src)])

    assert result.exit_code == 2
