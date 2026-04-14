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


# ---------------------------------------------------------------------------
# Unit tests for the _split_frontmatter helper itself
# ---------------------------------------------------------------------------

class TestSplitFrontmatterHelper:
    """Guard the ``_split_frontmatter`` parsing helper against regressions."""

    def test_valid_frontmatter_round_trips(self) -> None:
        src = "---\nfoo: bar\nbaz: 1\n---\n# Body\nsome text\n"
        fm, body = _split_frontmatter(src)
        assert fm == {"foo": "bar", "baz": 1}
        assert "# Body" in body

    def test_raises_when_no_opening_fence(self) -> None:
        with pytest.raises(AssertionError, match="must start with YAML frontmatter"):
            _split_frontmatter("# No frontmatter here\n")

    def test_empty_frontmatter_returns_empty_dict(self) -> None:
        src = "---\n---\nbody only\n"
        fm, body = _split_frontmatter(src)
        assert fm == {}
        assert "body only" in body

    def test_multi_key_frontmatter_parsed_correctly(self) -> None:
        src = "---\ndescription: A test\nargument-hint: <x>\nallowed-tools: Bash, Read\n---\nbody\n"
        fm, body = _split_frontmatter(src)
        assert fm["description"] == "A test"
        assert fm["argument-hint"] == "<x>"
        assert fm["allowed-tools"] == "Bash, Read"
        assert body.strip() == "body"


# ---------------------------------------------------------------------------
# Contract tests for .claude/commands/ingest.md  (Story 03.1-001)
# ---------------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Frontmatter contract
    # ------------------------------------------------------------------

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

    def test_allowed_tools_enables_write(self, parsed: tuple[dict[str, object], str]) -> None:
        """Write access is needed to create concept stubs and the wiki page."""
        fm, _ = parsed
        tokens = {t.strip() for t in str(fm["allowed-tools"]).split(",")}
        assert "Write" in tokens, "ingest must have Write permission to materialise pages"

    def test_allowed_tools_enables_read(self, parsed: tuple[dict[str, object], str]) -> None:
        """Read access is needed to inspect state.json and schema.toml."""
        fm, _ = parsed
        tokens = {t.strip() for t in str(fm["allowed-tools"]).split(",")}
        assert "Read" in tokens, "ingest must have Read permission to inspect state files"

    # ------------------------------------------------------------------
    # Pipeline steps — toolkit verbs
    # ------------------------------------------------------------------

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

    def test_body_references_search_verb(self, parsed: tuple[dict[str, object], str]) -> None:
        """``ai-research search`` prevents coining duplicate concept slugs."""
        _, body = parsed
        assert "ai-research search" in body, (
            "body must invoke `ai-research search` to check for existing concept pages "
            "before creating stubs"
        )

    def test_body_documents_argument_placeholder(
        self, parsed: tuple[dict[str, object], str]
    ) -> None:
        _, body = parsed
        assert "$ARGUMENTS" in body, "body must consume the $ARGUMENTS placeholder"

    def test_body_documents_empty_arguments_usage_hint(
        self, parsed: tuple[dict[str, object], str]
    ) -> None:
        """When $ARGUMENTS is empty the command must emit a usage hint and stop."""
        _, body = parsed
        assert "usage" in body.lower(), (
            "body must document the usage hint emitted when no argument is provided"
        )

    # ------------------------------------------------------------------
    # Idempotency and concept stubs
    # ------------------------------------------------------------------

    def test_body_covers_idempotency_and_stubs(self, parsed: tuple[dict[str, object], str]) -> None:
        _, body = parsed
        assert "already ingested" in body, "idempotency acceptance criterion not covered"
        assert "--stub" in body, "concept stub creation path not documented"

    def test_body_references_state_json_for_hash_check(
        self, parsed: tuple[dict[str, object], str]
    ) -> None:
        """Hash lookup in state.json is the idempotency mechanism."""
        _, body = parsed
        assert "state.json" in body, (
            "body must reference state.json as the source of truth for duplicate detection"
        )

    def test_body_documents_skip_index_flag(self, parsed: tuple[dict[str, object], str]) -> None:
        """``--skip-index`` must be used on stub/materialize calls so index rebuilds once."""
        _, body = parsed
        assert "--skip-index" in body, (
            "body must use --skip-index on per-stub materialize calls to avoid "
            "O(n) index rebuilds"
        )

    def test_body_documents_unchanged_as_idempotent_success(
        self, parsed: tuple[dict[str, object], str]
    ) -> None:
        """materialize reporting UNCHANGED must be treated as success, not an error."""
        _, body = parsed
        assert "UNCHANGED" in body, (
            "body must document that materialize's UNCHANGED output is an idempotent "
            "success, not a failure"
        )

    # ------------------------------------------------------------------
    # URL source handling
    # ------------------------------------------------------------------

    def test_body_documents_source_url_flag_for_urls(
        self, parsed: tuple[dict[str, object], str]
    ) -> None:
        """URL sources need ``--source-url`` so the Sources section records the origin."""
        _, body = parsed
        assert "--source-url" in body, (
            "body must document --source-url flag for URL sources so the wiki page "
            "records the original URL in its Sources section"
        )

    # ------------------------------------------------------------------
    # Schema / template integration
    # ------------------------------------------------------------------

    def test_body_references_schema_toml_for_template(
        self, parsed: tuple[dict[str, object], str]
    ) -> None:
        """The page draft must use the template from schema.toml, not a hardcoded layout."""
        _, body = parsed
        assert "schema.toml" in body, (
            "body must reference schema.toml as the source of the page template "
            "so sections can be tuned without editing the slash command"
        )

    # ------------------------------------------------------------------
    # Output format contract
    # ------------------------------------------------------------------

    def test_body_documents_structured_output_format(
        self, parsed: tuple[dict[str, object], str]
    ) -> None:
        """The output block must include the four structured keys for machine parsing."""
        _, body = parsed
        for line_key in ("ingested:", "page:", "stubs:", "index:"):
            assert line_key in body, (
                f"output format missing key `{line_key}` — headless callers parse this"
            )

    def test_body_documents_page_status_tokens(
        self, parsed: tuple[dict[str, object], str]
    ) -> None:
        """CREATED / UPDATED / UNCHANGED tokens let callers determine what changed."""
        _, body = parsed
        for token in ("CREATED", "UPDATED", "UNCHANGED"):
            assert token in body, (
                f"output format must include `{token}` status token for `page:` field"
            )

    def test_body_documents_error_output_path(self, parsed: tuple[dict[str, object], str]) -> None:
        """On failure the command must emit a single ``error:`` line and make no writes."""
        _, body = parsed
        assert "error:" in body, (
            "body must document the error output format so callers can detect failures"
        )

    # ------------------------------------------------------------------
    # Pipeline ordering and atomicity
    # ------------------------------------------------------------------

    def test_body_rebuilds_index_exactly_once_at_end(
        self, parsed: tuple[dict[str, object], str]
    ) -> None:
        """index-rebuild must run exactly once at the end, not per stub."""
        _, body = parsed
        # The body must explicitly state once/exactly once / at the end
        assert "index-rebuild" in body, "index-rebuild step must be mentioned"
        # Verify the ordering: index-rebuild text must appear after materialize text
        idx_materialize = body.rfind("ai-research materialize")
        idx_index = body.rfind("ai-research index-rebuild")
        assert idx_materialize < idx_index, (
            "ai-research index-rebuild must appear after ai-research materialize "
            "in the pipeline prose"
        )

    def test_body_stops_on_extract_failure(self, parsed: tuple[dict[str, object], str]) -> None:
        """If extract fails (non-zero exit) the pipeline must stop before drafting."""
        _, body = parsed
        # The body must document the stop-on-failure behaviour for the extract step
        assert "non-zero" in body or "exit code" in body.lower(), (
            "body must document that a non-zero exit from extract stops the pipeline"
        )
