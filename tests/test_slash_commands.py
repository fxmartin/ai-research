"""Tests for Claude Code slash command specs under ``.claude/commands/``.

Slash commands are prose, not Python, but the front-matter is a machine contract
(``description``, ``argument-hint``, ``allowed-tools``) consumed by the Claude Code
harness. These tests guard that contract so a stray edit cannot silently break the
headless invocation path (``claude -p "/ingest ..."``).
"""

from __future__ import annotations

import re
from pathlib import Path

import frontmatter
import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
COMMANDS_DIR = REPO_ROOT / ".claude" / "commands"


def _load(name: str) -> frontmatter.Post:
    path = COMMANDS_DIR / name
    assert path.exists(), f"slash command missing: {path}"
    return frontmatter.load(path)


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

    def test_raises_when_frontmatter_is_not_a_mapping(self) -> None:
        """YAML front-matter that parses to a non-dict (bare scalar) must be rejected."""
        # A bare scalar at the top of the YAML block is syntactically valid YAML but
        # an invalid slash-command contract — the Claude Code harness expects a mapping.
        src = "---\njust a string\n---\nbody\n"
        with pytest.raises(AssertionError, match="frontmatter must be a YAML mapping"):
            _split_frontmatter(src)


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
            "body must use --skip-index on per-stub materialize calls to avoid O(n) index rebuilds"
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

    def test_body_documents_page_status_tokens(self, parsed: tuple[dict[str, object], str]) -> None:
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


# ---------------------------------------------------------------------------
# Contract tests for .claude/commands/ingest-inbox.md  (Story 03.2-001)
# ---------------------------------------------------------------------------


class TestIngestInboxCommand:
    """Contract tests for ``.claude/commands/ingest-inbox.md`` (Story 03.2-001).

    ``/ingest-inbox`` drains ``raw/`` by shelling out to
    ``ai-research scan raw/ --skip-known`` then inlining the per-file ingest
    pipeline (extract → draft → stub → materialize) in a single Claude Code
    turn, rebuilding the index exactly once at the end.
    """

    @pytest.fixture
    def command_path(self) -> Path:
        path = COMMANDS_DIR / "ingest-inbox.md"
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

    def test_allowed_tools_enables_bash_and_write(
        self, parsed: tuple[dict[str, object], str]
    ) -> None:
        fm, _ = parsed
        tokens = {t.strip() for t in str(fm["allowed-tools"]).split(",")}
        for required in ("Bash", "Write", "Read"):
            assert required in tokens, f"ingest-inbox must permit {required!r} — got {tokens}"

    # ------------------------------------------------------------------
    # Scan → ingest loop
    # ------------------------------------------------------------------

    def test_body_invokes_scan_verb(self, parsed: tuple[dict[str, object], str]) -> None:
        _, body = parsed
        assert "ai-research scan" in body, (
            "body must shell out to `ai-research scan raw/` to enumerate eligible files"
        )

    def test_body_scans_raw_directory(self, parsed: tuple[dict[str, object], str]) -> None:
        _, body = parsed
        assert "raw/" in body, "body must target the raw/ inbox directory"

    def test_body_loops_inline_not_via_slash_ingest(
        self, parsed: tuple[dict[str, object], str]
    ) -> None:
        """Per technical notes, the loop must call Python verbs directly, NOT /ingest."""
        _, body = parsed
        # The body must reference the per-file verbs directly.
        for verb in ("ai-research extract", "ai-research materialize"):
            assert verb in body, f"body must call `{verb}` directly per file"
        # And explicitly avoid re-entering the slash command.
        assert re.search(r"not.*re-?enter|not.*re-?invoking|NOT.*/ingest", body, re.IGNORECASE), (
            "body must explicitly document that it does NOT re-invoke /ingest per file"
        )

    # ------------------------------------------------------------------
    # Idempotency
    # ------------------------------------------------------------------

    def test_body_uses_skip_known_for_idempotency(
        self, parsed: tuple[dict[str, object], str]
    ) -> None:
        _, body = parsed
        assert "--skip-known" in body, (
            "body must pass --skip-known to scan so already-ingested sources "
            "are filtered out (idempotency)"
        )

    def test_body_documents_idempotency_contract(
        self, parsed: tuple[dict[str, object], str]
    ) -> None:
        _, body = parsed
        assert re.search(r"idempoten", body, re.IGNORECASE), (
            "body must state the idempotency contract explicitly"
        )

    def test_body_mentions_mtime_skip(self, parsed: tuple[dict[str, object], str]) -> None:
        """Files younger than 5s must be deferred to the next tick."""
        _, body = parsed
        assert re.search(r"mtime|min-age|5\s*s|5-?second", body, re.IGNORECASE), (
            "body must document the mtime-based skip for very new files"
        )

    # ------------------------------------------------------------------
    # Index rebuild exactly once
    # ------------------------------------------------------------------

    def test_body_rebuilds_index_exactly_once(self, parsed: tuple[dict[str, object], str]) -> None:
        _, body = parsed
        assert "ai-research index-rebuild" in body, "body must invoke index-rebuild once at the end"
        assert "--skip-index" in body, (
            "per-file materialize calls must pass --skip-index so the batch "
            "only rebuilds the index once"
        )
        assert re.search(r"once|exactly once", body, re.IGNORECASE), (
            "body must explicitly pin that index-rebuild runs exactly once"
        )

    def test_body_index_rebuild_after_loop(self, parsed: tuple[dict[str, object], str]) -> None:
        _, body = parsed
        idx_materialize = body.rfind("ai-research materialize")
        idx_index = body.rfind("ai-research index-rebuild")
        assert 0 < idx_materialize < idx_index, (
            "ai-research index-rebuild must appear after the per-file materialize "
            "prose — ordering signals the once-at-end contract"
        )

    # ------------------------------------------------------------------
    # Failure handling
    # ------------------------------------------------------------------

    def test_body_documents_partial_failure_continues(
        self, parsed: tuple[dict[str, object], str]
    ) -> None:
        """One bad file must not abort the batch."""
        _, body = parsed
        assert re.search(r"continue|do not abort|not abort", body, re.IGNORECASE), (
            "body must document that per-file failures do not abort the batch"
        )

    def test_body_documents_empty_inbox_clean_exit(
        self, parsed: tuple[dict[str, object], str]
    ) -> None:
        """Empty raw/ is a clean exit, not an error."""
        _, body = parsed
        assert "nothing to ingest" in body, (
            "body must document the `nothing to ingest` message for empty raw/"
        )

    # ------------------------------------------------------------------
    # Structured output
    # ------------------------------------------------------------------

    def test_body_documents_structured_output(self, parsed: tuple[dict[str, object], str]) -> None:
        _, body = parsed
        for line_key in ("scanned:", "ingested:", "pages:", "index:"):
            assert line_key in body, (
                f"output summary missing key `{line_key}` — headless callers parse this"
            )

    def test_body_reports_failures_in_output(self, parsed: tuple[dict[str, object], str]) -> None:
        _, body = parsed
        assert "failures:" in body or "failed" in body, (
            "body must surface per-file failures in the output summary"
        )

    def test_argument_hint_is_no_arguments(self, parsed: tuple[dict[str, object], str]) -> None:
        """`argument-hint` must signal this command takes no arguments.

        Unlike `/ingest` (hint: ``<path-or-url>``), ``/ingest-inbox`` takes nothing;
        the hint must make that explicit so the Claude Code harness shows the right UX.
        """
        fm, _ = parsed
        hint = str(fm.get("argument-hint", ""))
        # Accept the literal value used in the spec or any phrasing that conveys
        # "no arguments" clearly.
        assert re.search(r"no arguments|\(no arguments\)", hint, re.IGNORECASE) or hint == "", (
            f"argument-hint must indicate the command takes no arguments, got: {hint!r}"
        )

    def test_body_scan_uses_json_flag(self, parsed: tuple[dict[str, object], str]) -> None:
        """``ai-research scan`` must be invoked with ``--json`` so output is machine-parseable.

        The batch loop parses the scan output as a JSON array of paths; without
        ``--json`` the output format is undefined and loop logic would break.
        """
        _, body = parsed
        assert "--json" in body, (
            "body must pass --json to `ai-research scan` so the path list is "
            "machine-parseable by the batch loop"
        )


# ---------------------------------------------------------------------------
# Contract tests for .claude/commands/ask.md  (Story 03.3-001)
# ---------------------------------------------------------------------------


class TestAskCommand:
    """Story 03.3-001: `/ask` slash command."""

    @pytest.fixture(scope="class")
    def post(self) -> frontmatter.Post:
        return _load("ask.md")

    # ------------------------------------------------------------------
    # Frontmatter field tests
    # ------------------------------------------------------------------

    def test_file_exists(self) -> None:
        assert (COMMANDS_DIR / "ask.md").is_file()

    def test_frontmatter_parses(self, post: frontmatter.Post) -> None:
        # python-frontmatter returns an empty metadata dict for malformed
        # frontmatter rather than raising; assert we got non-empty metadata.
        assert post.metadata, "frontmatter did not parse or is empty"

    def test_frontmatter_has_description(self, post: frontmatter.Post) -> None:
        assert isinstance(post.metadata.get("description"), str)
        assert post.metadata["description"].strip()

    def test_frontmatter_has_argument_hint(self, post: frontmatter.Post) -> None:
        assert "argument-hint" in post.metadata

    def test_frontmatter_argument_hint_value(self, post: frontmatter.Post) -> None:
        """The argument-hint must describe a question string, not a file path."""
        hint = str(post.metadata.get("argument-hint", ""))
        assert "question" in hint.lower() or hint.strip() == "<question>", (
            f"argument-hint should indicate a question, got: {hint!r}"
        )

    def test_frontmatter_allowed_tools_field_present(self, post: frontmatter.Post) -> None:
        assert "allowed-tools" in post.metadata

    def test_allowed_tools_includes_required(self, post: frontmatter.Post) -> None:
        allowed = post.metadata.get("allowed-tools", "")
        # Support either a CSV string or a YAML list.
        if isinstance(allowed, list):
            tools = {t.strip() for t in allowed}
        else:
            tools = {t.strip() for t in str(allowed).split(",")}
        for required in ("Read", "Grep", "Bash"):
            assert required in tools, f"allowed-tools missing {required!r}: {tools}"

    # ------------------------------------------------------------------
    # Body structural section tests (two-stage retrieval protocol)
    # ------------------------------------------------------------------

    @pytest.mark.parametrize(
        "section",
        [
            "Output modes",
            "Protocol",
            "Stage 1",
            "Stage 2",
            "JSON",
            "confidence",
            "citations",
            "$ARGUMENTS",
            ".ai-research/index.md",
            "ai-research search",
            "[[page-name]]",
        ],
    )
    def test_body_contains(self, post: frontmatter.Post, section: str) -> None:
        assert section in post.content, f"ask.md body missing required marker: {section!r}"

    # ------------------------------------------------------------------
    # JSON output contract tests
    # ------------------------------------------------------------------

    def test_json_schema_keys_pinned(self, post: frontmatter.Post) -> None:
        body = post.content
        for key in ('"answer"', '"citations"', '"confidence"'):
            assert key in body, f"JSON schema key {key} not pinned in ask.md"

    def test_json_schema_answer_is_string_typed(self, post: frontmatter.Post) -> None:
        """The spec must document that `answer` is a string."""
        body = post.content
        # The schema block should associate "answer" with "string"
        assert re.search(r'"answer".*string', body, re.DOTALL), (
            "ask.md does not specify 'answer' as string type in JSON schema"
        )

    def test_json_schema_citations_is_array_typed(self, post: frontmatter.Post) -> None:
        """The spec must document that `citations` is an array of strings."""
        body = post.content
        assert "string[]" in body or re.search(r'"citations".*\[', body, re.DOTALL), (
            "ask.md does not specify 'citations' as array in JSON schema"
        )

    def test_json_schema_confidence_is_number_typed(self, post: frontmatter.Post) -> None:
        """The spec must document that `confidence` is a numeric float."""
        body = post.content
        assert re.search(r'"confidence".*(?:float|number|\[0)', body, re.DOTALL), (
            "ask.md does not specify 'confidence' as numeric in JSON schema"
        )

    def test_json_exact_keys_instruction_present(self, post: frontmatter.Post) -> None:
        """The spec must explicitly instruct the model to emit ONLY the defined keys."""
        body = post.content
        # Look for language that pins the key set (no extra keys)
        pattern = r"EXACTLY\s+these\s+keys|no extra keys|no prose|no markdown"
        assert re.search(pattern, body, re.IGNORECASE), (
            "ask.md does not pin the JSON output to exactly the defined keys"
        )

    # ------------------------------------------------------------------
    # Two-stage retrieval instruction tests
    # ------------------------------------------------------------------

    def test_stage0_empty_vault_behavior_pinned(self, post: frontmatter.Post) -> None:
        """Spec must describe what happens when the vault is empty."""
        body = post.content
        assert "empty" in body.lower() and "vault" in body.lower(), (
            "ask.md does not describe empty-vault behavior"
        )

    def test_empty_vault_answer_is_empty_string(self, post: frontmatter.Post) -> None:
        """Empty vault must yield answer='' in JSON output, per AC."""
        body = post.content
        # The spec should express that the answer is "" or empty string for empty vault
        assert re.search(r'answer.*""|\"\"|empty string', body, re.DOTALL), (
            "ask.md does not specify that answer is empty string when vault is empty"
        )

    def test_empty_vault_confidence_is_zero(self, post: frontmatter.Post) -> None:
        """Empty vault must yield confidence=0.0, per AC."""
        body = post.content
        assert "0.0" in body, "ask.md does not specify confidence=0.0 for empty vault"

    def test_shortlist_minimum_bound_pinned(self, post: frontmatter.Post) -> None:
        """Spec must pin the minimum shortlist size of 3 pages."""
        body = post.content
        assert re.search(r"\b3\b", body), "ask.md does not pin minimum shortlist of 3"

    def test_shortlist_maximum_bound_pinned(self, post: frontmatter.Post) -> None:
        """Spec must pin the maximum shortlist size of 8 pages."""
        body = post.content
        assert re.search(r"\b8\b", body), "ask.md does not pin maximum shortlist of 8"

    def test_shortlist_bounds_in_stage1(self, post: frontmatter.Post) -> None:
        """Stage 1 must explicitly constrain the shortlist to 3–8 pages."""
        body = post.content
        assert "3" in body and "8" in body, (
            "ask.md Stage 1 does not bound the shortlist between 3 and 8"
        )

    def test_lexical_fallback_instruction_present(self, post: frontmatter.Post) -> None:
        """Spec must instruct the model to fall back to ai-research search on low confidence."""
        body = post.content
        assert "fallback" in body.lower() or "ai-research search" in body, (
            "ask.md does not describe the lexical fallback step"
        )

    def test_deduplication_instruction_present(self, post: frontmatter.Post) -> None:
        """After fallback merge, the spec should require de-duplication by page name."""
        body = post.content
        assert re.search(r"[Dd]e.duplic|dedup|unique", body), (
            "ask.md does not mention de-duplication after fallback merge"
        )

    # ------------------------------------------------------------------
    # Citation integrity tests
    # ------------------------------------------------------------------

    def test_citation_integrity_rule_present(self, post: frontmatter.Post) -> None:
        """Spec must prohibit citing pages that were not read."""
        body = post.content
        # The spec should say something like "only cite what you read"
        pattern = r"only cite|not invent|do not invent|did not read|actually read"
        assert re.search(pattern, body, re.IGNORECASE), (
            "ask.md does not enforce citation integrity (only cite pages actually read)"
        )

    def test_citation_format_bare_page_name(self, post: frontmatter.Post) -> None:
        """The spec must define citations as bare page names (no brackets, no .md)."""
        body = post.content
        assert re.search(r"bare page name|no brackets|no \.md|no path", body, re.IGNORECASE), (
            "ask.md does not specify citations as bare page names"
        )

    # ------------------------------------------------------------------
    # Read-only constraint test
    # ------------------------------------------------------------------

    def test_read_only_constraint_stated(self, post: frontmatter.Post) -> None:
        """Spec must state that /ask never modifies disk."""
        body = post.content
        assert re.search(r"read.only|never modify|not modify|do not write", body, re.IGNORECASE), (
            "ask.md does not declare the read-only constraint"
        )

    # ------------------------------------------------------------------
    # Confidence calibration tests
    # ------------------------------------------------------------------

    def test_confidence_upper_bound_never_one(self, post: frontmatter.Post) -> None:
        """Spec must instruct model never to emit confidence=1.0."""
        body = post.content
        assert re.search(r"[Nn]ever.*1\.0|1\.0.*[Nn]ever|reserve.*1\.0", body), (
            "ask.md does not instruct the model to never emit confidence=1.0"
        )

    def test_confidence_range_specified(self, post: frontmatter.Post) -> None:
        """Spec must define the confidence scale (0.0 to <1.0)."""
        body = post.content
        # Should have at least one confidence range band described
        assert re.search(r"0\.\d+.*0\.\d+|0\.0.*0\.9", body, re.DOTALL), (
            "ask.md does not define confidence scale bands"
        )

    # ------------------------------------------------------------------
    # Interactive mode tests
    # ------------------------------------------------------------------

    def test_interactive_mode_sources_list(self, post: frontmatter.Post) -> None:
        """Interactive output must end with a Sources bullet list per spec."""
        body = post.content
        assert re.search(r"[Ss]ources", body), (
            "ask.md does not describe the Sources list for interactive mode"
        )

    def test_interactive_mode_wikilink_citations(self, post: frontmatter.Post) -> None:
        """Interactive answer must use [[wikilinks]] as inline citations."""
        body = post.content
        # The spec uses [[page-name]] notation — already checked in parametrize but
        # this test verifies it in the interactive-mode context specifically.
        assert "wikilink" in body.lower() or "[[" in body, (
            "ask.md does not require [[wikilink]] citations in interactive mode"
        )

    # ------------------------------------------------------------------
    # Stage 0 precondition tests
    # ------------------------------------------------------------------

    def test_stage0_index_existence_check(self, post: frontmatter.Post) -> None:
        """Spec must check that .ai-research/index.md exists before proceeding."""
        body = post.content
        assert "index.md" in body and ("exists" in body.lower() or "verify" in body.lower()), (
            "ask.md Stage 0 does not verify .ai-research/index.md existence"
        )

    def test_stage0_wiki_dir_existence_check(self, post: frontmatter.Post) -> None:
        """Spec must verify wiki/ directory exists and contains .md files."""
        body = post.content
        assert "wiki/" in body, "ask.md Stage 0 does not check wiki/ directory"
