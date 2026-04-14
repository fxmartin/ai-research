"""Tests for Claude Code slash command specs under ``.claude/commands/``.

Slash commands are prose, not Python, but the front-matter is a machine contract
(``description``, ``argument-hint``, ``allowed-tools``) consumed by the Claude Code
harness. These tests guard that contract so a stray edit cannot silently break the
headless invocation path (``claude -p "/ingest ..."``).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
COMMANDS_DIR = REPO_ROOT / ".claude" / "commands"


def _split_frontmatter(text: str) -> tuple[dict[str, object], str]:
    """Split a markdown file into (frontmatter dict, body).

    Raises ``AssertionError`` if the file does not open with a ``---`` fence.
    """

    assert text.startswith("---\n"), "slash command must start with YAML frontmatter"
    _, fm, body = text.split("---\n", 2)
    data = yaml.safe_load(fm) or {}
    assert isinstance(data, dict), "frontmatter must be a YAML mapping"
    return data, body


class TestIngestCommand:
    """Contract tests for ``.claude/commands/ingest.md`` (Story 03.1-001)."""

    @pytest.fixture
    def command_path(self) -> Path:
        path = COMMANDS_DIR / "ingest.md"
        assert path.is_file(), f"missing slash command spec: {path}"
        return path

    @pytest.fixture
    def parsed(self, command_path: Path) -> tuple[dict[str, object], str]:
        return _split_frontmatter(command_path.read_text(encoding="utf-8"))

    def test_frontmatter_has_required_fields(self, parsed: tuple[dict[str, object], str]) -> None:
        fm, _ = parsed
        for key in ("description", "argument-hint", "allowed-tools"):
            assert key in fm, f"frontmatter missing required key: {key}"
        assert isinstance(fm["description"], str) and fm["description"].strip()
        assert fm["argument-hint"] == "<path-or-url>"

    def test_allowed_tools_enables_bash(self, parsed: tuple[dict[str, object], str]) -> None:
        fm, _ = parsed
        tools = fm["allowed-tools"]
        # allowed-tools is a comma-separated string in Claude Code conventions.
        tokens = {t.strip() for t in str(tools).split(",")}
        assert "Bash" in tokens, "ingest must be allowed to shell out to toolkit verbs"

    def test_body_references_toolkit_verbs(self, parsed: tuple[dict[str, object], str]) -> None:
        _, body = parsed
        # The prose must compose the deterministic toolkit; drift here means the
        # pipeline would silently skip a stage.
        for verb in (
            "ai-research extract",
            "ai-research materialize",
            "ai-research index-rebuild",
        ):
            assert verb in body, f"body must invoke `{verb}`"

    def test_body_documents_argument_placeholder(
        self, parsed: tuple[dict[str, object], str]
    ) -> None:
        _, body = parsed
        assert "$ARGUMENTS" in body, "body must consume the $ARGUMENTS placeholder"

    def test_body_covers_idempotency_and_stubs(self, parsed: tuple[dict[str, object], str]) -> None:
        _, body = parsed
        assert "already ingested" in body, "idempotency acceptance criterion not covered"
        assert "--stub" in body, "concept stub creation path not documented"
