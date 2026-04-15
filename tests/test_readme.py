"""Structural smoke tests for the top-level README.

Story 04.3-002: README must document install, every CLI verb, every slash
command, and link to the roadmap. These tests guard against drift.
"""

from __future__ import annotations

import re
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


# ---------------------------------------------------------------------------
# Install section
# ---------------------------------------------------------------------------


def test_readme_has_install_section(readme_text: str) -> None:
    """README must contain an Install section with the `uv tool install .` command."""
    assert "## Install" in readme_text, "README missing '## Install' section"
    assert "uv tool install" in readme_text, (
        "README Install section must reference `uv tool install`"
    )


def test_readme_install_includes_git_clone(readme_text: str) -> None:
    """Install section must show how to clone the repo before installing."""
    assert "git clone" in readme_text, (
        "README Install section must include a `git clone` step so a new user "
        "knows where to get the source"
    )


def test_readme_install_verify_step(readme_text: str) -> None:
    """Install section must show a verify / --help step after install."""
    assert "--help" in readme_text, (
        "README must include an `ai-research --help` verify step after install"
    )


# ---------------------------------------------------------------------------
# Prerequisites
# ---------------------------------------------------------------------------


def test_readme_mentions_prerequisites(readme_text: str) -> None:
    """README must have a Prerequisites section so a clean-machine user knows
    what to install before running `uv tool install .`."""
    assert "Prerequisites" in readme_text, (
        "README missing 'Prerequisites' section — clean-machine users need to "
        "know about uv, poppler, ripgrep, and the claude CLI before installing"
    )


def test_readme_mentions_uv_prerequisite(readme_text: str) -> None:
    """uv must be listed as a prerequisite."""
    assert "uv" in readme_text, "README must mention uv as a prerequisite"


def test_readme_mentions_pdftotext_prerequisite(readme_text: str) -> None:
    """pdftotext / poppler must be listed as a prerequisite."""
    assert "pdftotext" in readme_text or "poppler" in readme_text, (
        "README must mention pdftotext / poppler as a prerequisite"
    )


def test_readme_mentions_ripgrep_prerequisite(readme_text: str) -> None:
    """ripgrep must be listed as a prerequisite."""
    # Accept either the binary name or the package name
    mentions_rg = (
        "ripgrep" in readme_text
        or "`rg`" in readme_text
        or "brew install ripgrep" in readme_text
    )
    assert mentions_rg, "README must mention ripgrep as a prerequisite"


def test_readme_mentions_claude_cli_prerequisite(readme_text: str) -> None:
    """Claude Code CLI must be listed as a prerequisite."""
    assert "Claude Code" in readme_text or "claude" in readme_text, (
        "README must mention the claude CLI as a prerequisite"
    )


# ---------------------------------------------------------------------------
# Invocation modes — /ingest-inbox in all three modes (AC #2)
# ---------------------------------------------------------------------------


def test_readme_ingest_inbox_interactive_mode(readme_text: str) -> None:
    """Acceptance Criteria: README must show /ingest-inbox used interactively
    (inside an open `claude` session)."""
    # The README should show opening a claude session and running /ingest-inbox
    has_open_claude = "claude" in readme_text and "/ingest-inbox" in readme_text
    assert has_open_claude, (
        "README must demonstrate /ingest-inbox used in interactive mode "
        "(opening a claude session and running the command)"
    )


def test_readme_ingest_inbox_loop_mode(readme_text: str) -> None:
    """Acceptance Criteria: README must show /ingest-inbox driven by /loop."""
    assert "/loop" in readme_text, (
        "README must show `/loop` driving `/ingest-inbox` for the self-paced "
        "watcher invocation mode"
    )
    assert "/ingest-inbox" in readme_text, (
        "README must mention /ingest-inbox in the context of /loop usage"
    )


def test_readme_ingest_inbox_headless_mode(readme_text: str) -> None:
    """Acceptance Criteria: README must show headless `claude -p '/ingest-inbox'`."""
    assert 'claude -p' in readme_text, (
        "README must show headless invocation via `claude -p` for scheduled / "
        "pipeline use (e.g. launchd, cron)"
    )


def test_readme_has_three_invocation_modes_table_or_section(readme_text: str) -> None:
    """README must document all three invocation modes: interactive, loop/watcher,
    and headless/scheduled."""
    modes_found = sum([
        "Interactive" in readme_text or "interactive" in readme_text,
        "/loop" in readme_text,
        "Headless" in readme_text or "headless" in readme_text or "scheduled" in readme_text,
    ])
    assert modes_found == 3, (
        f"README must document all three invocation modes (interactive, loop, "
        f"headless); only {modes_found}/3 were detected"
    )


# ---------------------------------------------------------------------------
# CLI verbs — presence and example (AC #3)
# ---------------------------------------------------------------------------


def test_readme_links_to_stories_roadmap(readme_text: str) -> None:
    """README must link to docs/STORIES.md for the roadmap."""
    assert "docs/STORIES.md" in readme_text, (
        "README must link to docs/STORIES.md for roadmap navigation"
    )


@pytest.mark.parametrize("verb", CLI_VERBS)
def test_readme_mentions_each_cli_verb(readme_text: str, verb: str) -> None:
    """Every toolkit verb must appear in the README at least once."""
    assert verb in readme_text, f"README does not mention CLI verb `{verb}`"


@pytest.mark.parametrize("verb", CLI_VERBS)
def test_readme_cli_verb_has_example(readme_text: str, verb: str) -> None:
    """Every toolkit verb must have at least one concrete usage example.

    Acceptance Criteria: 'every toolkit verb … there is a one-line description
    and at least one example.'  We look for `ai-research <verb>` appearing in
    a code block (backtick-fenced or indented) anywhere in the README.
    """
    # Match `ai-research <verb>` optionally surrounded by code fences
    pattern = rf"ai-research\s+{re.escape(verb)}"
    assert re.search(pattern, readme_text), (
        f"README must show at least one `ai-research {verb} …` usage example "
        f"(Acceptance Criteria: one-line description + example per verb)"
    )


# ---------------------------------------------------------------------------
# Slash commands — presence
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("command", SLASH_COMMANDS)
def test_readme_mentions_each_slash_command(readme_text: str, command: str) -> None:
    """Every slash command must appear in the README at least once."""
    assert command in readme_text, f"README does not mention slash command `{command}`"


# ---------------------------------------------------------------------------
# Troubleshooting section (AC #4)
# ---------------------------------------------------------------------------


def test_readme_has_troubleshooting_section(readme_text: str) -> None:
    """Acceptance Criteria: README must have a Troubleshooting section."""
    assert "Troubleshoot" in readme_text, (
        "README missing Troubleshooting section — this is an explicit acceptance "
        "criterion for story 04.3-002"
    )


def test_readme_troubleshooting_covers_pdftotext(readme_text: str) -> None:
    """Acceptance Criteria: 'if I hit pdftotext not found, the fix is documented'."""
    assert "pdftotext" in readme_text, (
        "README Troubleshooting must document the `pdftotext: command not found` "
        "error and its fix (brew install poppler)"
    )


def test_readme_troubleshooting_covers_ripgrep(readme_text: str) -> None:
    """Troubleshooting should document the rg / ripgrep missing error."""
    has_rg_trouble = "rg" in readme_text and (
        "command not found" in readme_text or "brew install ripgrep" in readme_text
    )
    assert has_rg_trouble, (
        "README Troubleshooting must document the `rg: command not found` error "
        "and its fix (brew install ripgrep)"
    )


# ---------------------------------------------------------------------------
# Required links (Definition of Done)
# ---------------------------------------------------------------------------


def test_readme_links_to_requirements(readme_text: str) -> None:
    """Definition of Done: README must link to REQUIREMENTS.md."""
    assert "REQUIREMENTS.md" in readme_text, (
        "README must link to REQUIREMENTS.md (Definition of Done for 04.3-002)"
    )


def test_readme_links_to_karpathy_gist(readme_text: str) -> None:
    """Definition of Done: README must link to the Karpathy LLM-Wiki gist."""
    assert "karpathy" in readme_text.lower(), (
        "README must link to or credit Karpathy's LLM-Wiki gist "
        "(Definition of Done for 04.3-002)"
    )


# ---------------------------------------------------------------------------
# CI badge
# ---------------------------------------------------------------------------


def test_readme_has_ci_badge(readme_text: str) -> None:
    """README must include a CI status badge so readers can see build health."""
    has_badge = "badge.svg" in readme_text or "shields.io" in readme_text or "[![CI" in readme_text
    assert has_badge, (
        "README must include a CI status badge (e.g. GitHub Actions badge)"
    )


# ---------------------------------------------------------------------------
# Obsidian vault mention
# ---------------------------------------------------------------------------


def test_readme_mentions_obsidian(readme_text: str) -> None:
    """README must mention Obsidian so users understand the vault output format."""
    assert "Obsidian" in readme_text or "obsidian" in readme_text, (
        "README must mention Obsidian — the vault format is Obsidian-compatible "
        "and this is a key differentiator of the project"
    )
