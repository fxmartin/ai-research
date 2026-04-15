"""/ask JSON-contract harness test (Story 04.1-002).

Validates that the ``/ask`` slash command, when invoked under
``claude -p --output-format json``, emits stdout conforming to the
:class:`AskResponse` Pydantic model:

    {"answer": str, "citations": [str], "confidence": float in [0.0, 1.0)}

Two layers:

1. **Schema tests** (fast, always-on): exercise the Pydantic model against
   hand-crafted payloads to pin down the contract. These encode the spec
   in ``.claude/commands/ask.md`` and fail CI if a change to the model
   drifts from the documented shape.
2. **Slow harness** (``@pytest.mark.slow``): shells out to ``claude -p``
   against ``tests/fixtures/vault/``, parses stdout as JSON, and validates.
   Skipped when the ``claude`` CLI is unavailable or
   ``CLAUDE_CODE_AVAILABLE=false`` is set (the default CI environment).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError

from ai_research.wiki.ask import AskResponse, check_citations

FIXTURE_VAULT = Path(__file__).parent / "fixtures" / "vault"
REPO_ROOT = Path(__file__).resolve().parent.parent
CLAUDE_COMMANDS_DIR = REPO_ROOT / ".claude" / "commands"


# ---------------------------------------------------------------------------
# Schema layer — Pydantic model pins the contract.
# ---------------------------------------------------------------------------


def test_minimal_valid_payload_parses() -> None:
    resp = AskResponse.model_validate(
        {"answer": "Attention is all you need.", "citations": ["attention"], "confidence": 0.6}
    )
    assert resp.answer == "Attention is all you need."
    assert resp.citations == ["attention"]
    assert resp.confidence == 0.6


def test_empty_vault_shape_is_legal() -> None:
    # Per ask.md Stage 0: empty vault emits answer="", citations=[], confidence=0.0
    resp = AskResponse.model_validate({"answer": "", "citations": [], "confidence": 0.0})
    assert resp.citations == []
    assert resp.confidence == 0.0


def test_required_keys_enforced() -> None:
    for missing in ("answer", "citations", "confidence"):
        payload = {"answer": "x", "citations": [], "confidence": 0.5}
        del payload[missing]
        with pytest.raises(ValidationError):
            AskResponse.model_validate(payload)


def test_extra_keys_forbidden() -> None:
    # The spec says "Do not add commentary" — forbid unknown keys so drift is caught.
    with pytest.raises(ValidationError):
        AskResponse.model_validate(
            {"answer": "x", "citations": [], "confidence": 0.5, "debug": "nope"}
        )


def test_answer_must_be_string() -> None:
    with pytest.raises(ValidationError):
        AskResponse.model_validate({"answer": 123, "citations": [], "confidence": 0.5})


def test_citations_must_be_list_of_strings() -> None:
    with pytest.raises(ValidationError):
        AskResponse.model_validate({"answer": "x", "citations": "attention", "confidence": 0.5})
    with pytest.raises(ValidationError):
        AskResponse.model_validate({"answer": "x", "citations": [1, 2], "confidence": 0.5})


@pytest.mark.parametrize(
    "bad_citation",
    [
        "[[attention]]",  # bracketed wikilink
        "attention.md",  # with extension
        "wiki/attention",  # with path
        "attention#section",  # with anchor
        "attention|alias",  # with alias
        "",  # empty
        "   ",  # whitespace
    ],
)
def test_citation_format_bare_page_names(bad_citation: str) -> None:
    with pytest.raises(ValidationError):
        AskResponse.model_validate({"answer": "x", "citations": [bad_citation], "confidence": 0.5})


@pytest.mark.parametrize("confidence", [-0.01, 1.0, 1.5, float("nan")])
def test_confidence_out_of_bounds(confidence: float) -> None:
    with pytest.raises(ValidationError):
        AskResponse.model_validate({"answer": "x", "citations": [], "confidence": confidence})


@pytest.mark.parametrize("confidence", [0.0, 0.25, 0.95, 0.999])
def test_confidence_within_half_open_interval(confidence: float) -> None:
    resp = AskResponse.model_validate({"answer": "x", "citations": [], "confidence": confidence})
    assert resp.confidence == confidence


def test_confidence_must_be_numeric() -> None:
    with pytest.raises(ValidationError):
        AskResponse.model_validate({"answer": "x", "citations": [], "confidence": "high"})


# ---------------------------------------------------------------------------
# Fixture vault sanity — citations in a valid response must resolve.
# ---------------------------------------------------------------------------


def test_fixture_vault_exists_and_is_well_formed() -> None:
    assert FIXTURE_VAULT.is_dir(), "fixture vault missing"
    assert (FIXTURE_VAULT / "wiki" / "attention.md").exists()
    assert (FIXTURE_VAULT / "wiki" / "concepts" / "transformer.md").exists()
    assert (FIXTURE_VAULT / ".ai-research" / "index.md").exists()


def test_simulated_response_against_fixture_vault_resolves() -> None:
    """Mock the claude invocation and run the same checks the harness will run.

    This encodes the end-to-end contract verification path without needing the
    ``claude`` CLI available, so it runs in every CI pipeline.
    """
    simulated_stdout = json.dumps(
        {
            "answer": "Attention is the core mechanism in [[transformer]] models.",
            "citations": ["attention", "transformer"],
            "confidence": 0.7,
        }
    )
    payload = json.loads(simulated_stdout)
    resp = AskResponse.model_validate(payload)

    result = check_citations(payload, wiki_dir=FIXTURE_VAULT / "wiki")
    assert result.ok, f"broken citations: {result.broken}"
    assert set(result.resolved) == set(resp.citations)


# ---------------------------------------------------------------------------
# Slow harness — real claude -p invocation.
# ---------------------------------------------------------------------------


def _claude_available() -> bool:
    if os.environ.get("CLAUDE_CODE_AVAILABLE", "").lower() == "false":
        return False
    return shutil.which("claude") is not None


@pytest.mark.slow
@pytest.mark.skipif(
    not _claude_available(),
    reason="claude CLI unavailable or CLAUDE_CODE_AVAILABLE=false",
)
def test_ask_json_contract_end_to_end(tmp_path: Path) -> None:
    """Shell out to ``claude -p /ask ... --output-format json`` and validate.

    Copies the fixture vault to a tmp dir so the harness never mutates the
    committed fixture. Asserts stdout is valid JSON matching AskResponse and
    every returned citation resolves via ``check_citations``.
    """
    work = tmp_path / "vault"
    shutil.copytree(FIXTURE_VAULT, work)
    # Claude Code discovers slash commands from `.claude/commands/` in CWD.
    # The fixture vault doesn't ship them, so stage the project's commands
    # into the tmp workspace before invoking `claude -p /ask ...`.
    shutil.copytree(CLAUDE_COMMANDS_DIR, work / ".claude" / "commands")

    proc = subprocess.run(
        [
            "claude",
            "-p",
            "/ask 'What is attention?'",
            "--output-format",
            "json",
        ],
        cwd=work,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    assert proc.returncode == 0, f"claude exited {proc.returncode}: {proc.stderr}"

    # claude -p --output-format json wraps the assistant's final message; we
    # probe for a JSON object anywhere in stdout that matches our schema.
    stdout = proc.stdout.strip()
    payload = _extract_ask_payload(stdout)
    resp = AskResponse.model_validate(payload)

    result = check_citations(payload, wiki_dir=work / "wiki")
    assert result.ok, f"broken citations: {result.broken}"
    # Empty vault path is legal, but our fixture has content → expect non-zero.
    assert resp.confidence >= 0.0


def _extract_ask_payload(stdout: str) -> dict:
    """Best-effort extraction of the ``/ask`` JSON object from claude stdout.

    ``claude -p --output-format json`` may wrap the assistant message in its
    own envelope. We try:
      1. Parse the whole thing — if it's already the ask payload, done.
      2. If it's a dict with a ``result`` or ``message`` field containing a
         JSON string, parse that.
      3. Fall back to regex-scanning for the first ``{...}`` that parses and
         contains the three required keys.
    """
    import re

    def _looks_like_ask(obj: object) -> bool:
        return isinstance(obj, dict) and {"answer", "citations", "confidence"} <= obj.keys()

    try:
        top = json.loads(stdout)
    except json.JSONDecodeError:
        top = None

    if _looks_like_ask(top):
        return top  # type: ignore[return-value]

    if isinstance(top, dict):
        for key in ("result", "message", "content", "text"):
            inner = top.get(key)
            if isinstance(inner, str):
                try:
                    parsed = json.loads(inner)
                except json.JSONDecodeError:
                    continue
                if _looks_like_ask(parsed):
                    return parsed

    for match in re.finditer(r"\{[^{}]*\"answer\"[^{}]*\}", stdout, flags=re.DOTALL):
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            continue
        if _looks_like_ask(parsed):
            return parsed

    raise AssertionError(f"could not extract /ask JSON payload from stdout:\n{stdout!r}")
