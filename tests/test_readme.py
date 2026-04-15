"""Structural smoke tests for the top-level README.

Story 04.3-002: README must document install, every CLI verb, every slash
command, and link to the roadmap. These tests guard against drift.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
README = REPO_ROOT / "README.md"

CLI_VERBS: tuple[str, ...] = (
    "extract",
    "archive",
    "materialize",
    "index-rebuild",
    "scan",
    "search",
    "vault-lint",
    "ask-check",
)

SLASH_COMMANDS: tuple[str, ...] = (
    "/ingest",
    "/ingest-inbox",
    "/ask",
)


@pytest.fixture(scope="module")
def readme_text() -> str:
    assert README.exists(), f"README not found at {README}"
    return README.read_text(encoding="utf-8")


def test_readme_has_install_section(readme_text: str) -> None:
    """README must contain an Install section with the `uv tool install .` command."""
    assert "## Install" in readme_text, "README missing '## Install' section"
    assert "uv tool install" in readme_text, (
        "README Install section must reference `uv tool install`"
    )


def test_readme_links_to_stories_roadmap(readme_text: str) -> None:
    """README must link to docs/STORIES.md for the roadmap."""
    assert "docs/STORIES.md" in readme_text, (
        "README must link to docs/STORIES.md for roadmap navigation"
    )


@pytest.mark.parametrize("verb", CLI_VERBS)
def test_readme_mentions_each_cli_verb(readme_text: str, verb: str) -> None:
    """Every toolkit verb must appear in the README at least once."""
    assert verb in readme_text, f"README does not mention CLI verb `{verb}`"


@pytest.mark.parametrize("command", SLASH_COMMANDS)
def test_readme_mentions_each_slash_command(readme_text: str, command: str) -> None:
    """Every slash command must appear in the README at least once."""
    assert command in readme_text, f"README does not mention slash command `{command}`"
