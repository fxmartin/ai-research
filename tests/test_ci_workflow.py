"""Smoke tests for the GitHub Actions CI workflow file.

These tests verify that `.github/workflows/ci.yml` is valid YAML and wires up
the quality gates required by Story 04.3-001:
- ruff check
- ruff format --check
- pyright
- pytest
- vault-lint (in a dedicated job).
"""

from __future__ import annotations

from pathlib import Path

import yaml

WORKFLOW_PATH = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci.yml"


def _load_workflow() -> dict:
    assert WORKFLOW_PATH.exists(), f"CI workflow missing: {WORKFLOW_PATH}"
    with WORKFLOW_PATH.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    assert isinstance(data, dict), "Workflow YAML must parse to a mapping"
    return data


def test_ci_workflow_is_valid_yaml() -> None:
    _load_workflow()


def test_ci_workflow_has_quality_job_with_required_steps() -> None:
    wf = _load_workflow()
    jobs = wf.get("jobs", {})
    assert "quality" in jobs, "Expected a 'quality' job"

    steps = jobs["quality"].get("steps", [])
    run_blobs = " \n ".join(step.get("run", "") for step in steps if isinstance(step, dict))

    assert "ruff check" in run_blobs
    assert "ruff format --check" in run_blobs
    assert "pyright" in run_blobs
    assert "pytest" in run_blobs


def test_ci_workflow_triggers_on_push_pr_and_schedule() -> None:
    wf = _load_workflow()
    # PyYAML parses the bare `on:` key as the boolean True — handle both.
    triggers = wf.get("on", wf.get(True, {}))
    assert "push" in triggers
    assert "pull_request" in triggers
    assert "schedule" in triggers


def test_ci_workflow_uses_uv_and_python_312() -> None:
    wf = _load_workflow()
    quality = wf["jobs"]["quality"]
    matrix = quality.get("strategy", {}).get("matrix", {})
    assert "3.12" in matrix.get("python-version", [])

    uses = [s.get("uses", "") for s in quality["steps"] if isinstance(s, dict)]
    assert any("astral-sh/setup-uv" in u for u in uses), "CI must use astral-sh/setup-uv"


def test_ci_workflow_has_vault_lint_job() -> None:
    wf = _load_workflow()
    assert "vault-lint" in wf.get("jobs", {}), "Expected a 'vault-lint' job"


def test_ci_workflow_push_restricted_to_main_branch() -> None:
    wf = _load_workflow()
    triggers = wf.get("on", wf.get(True, {}))
    push_config = triggers.get("push", {}) or {}
    branches = push_config.get("branches", [])
    assert "main" in branches, "push trigger must be restricted to main branch"


def test_ci_workflow_has_concurrency_cancel_in_progress() -> None:
    wf = _load_workflow()
    concurrency = wf.get("concurrency", {})
    assert concurrency, "Workflow must define a concurrency block to avoid duplicate runs"
    assert concurrency.get("cancel-in-progress") is True, (
        "cancel-in-progress must be true to avoid redundant CI runs"
    )


def test_ci_workflow_nightly_cron_schedule() -> None:
    wf = _load_workflow()
    triggers = wf.get("on", wf.get(True, {}))
    schedules = triggers.get("schedule", [])
    assert schedules, "schedule trigger must contain at least one cron entry"
    crons = [entry.get("cron", "") for entry in schedules if isinstance(entry, dict)]
    assert any(cron for cron in crons), "schedule must have a non-empty cron expression"


def test_ci_workflow_quality_uses_checkout_v4() -> None:
    wf = _load_workflow()
    quality = wf["jobs"]["quality"]
    uses_list = [s.get("uses", "") for s in quality["steps"] if isinstance(s, dict)]
    assert any("actions/checkout@v4" in u for u in uses_list), (
        "quality job must use actions/checkout@v4"
    )


def test_ci_workflow_quality_syncs_all_extras_dev() -> None:
    wf = _load_workflow()
    quality = wf["jobs"]["quality"]
    steps = quality.get("steps", [])
    run_blobs = " \n ".join(step.get("run", "") for step in steps if isinstance(step, dict))
    assert "uv sync" in run_blobs, "quality job must run uv sync to install dependencies"


def test_ci_workflow_quality_uses_fail_fast() -> None:
    wf = _load_workflow()
    quality = wf["jobs"]["quality"]
    fail_fast = quality.get("strategy", {}).get("fail-fast")
    assert fail_fast is True, "quality job strategy must have fail-fast: true"


def test_ci_workflow_quality_has_slow_and_fast_pytest_steps() -> None:
    """The quality job must have conditional pytest steps for nightly vs regular runs."""
    wf = _load_workflow()
    quality = wf["jobs"]["quality"]
    steps = quality.get("steps", [])
    step_ifs = [step.get("if", "") for step in steps if isinstance(step, dict)]
    run_blobs = [step.get("run", "") for step in steps if isinstance(step, dict)]

    # There must be a step that runs pytest -m "not slow" for non-schedule events
    has_fast_test = any(
        "not slow" in run and "schedule" in cond
        for run, cond in zip(run_blobs, step_ifs, strict=False)
        if run and cond
    )
    assert has_fast_test, (
        "quality job must have a conditional pytest step for non-schedule (fast) runs"
    )

    # And a step that runs the full suite for nightly schedule
    has_slow_test = any(
        "pytest" in run and "schedule" in cond and "not slow" not in run
        for run, cond in zip(run_blobs, step_ifs, strict=False)
        if run and cond
    )
    assert has_slow_test, (
        "quality job must have a conditional pytest step for schedule (full suite) runs"
    )


def test_ci_workflow_vault_lint_depends_on_quality_job() -> None:
    wf = _load_workflow()
    vault_lint = wf["jobs"]["vault-lint"]
    needs = vault_lint.get("needs", [])
    # needs can be a string or list
    if isinstance(needs, str):
        needs = [needs]
    assert "quality" in needs, "vault-lint job must declare needs: quality"


def test_ci_workflow_vault_lint_runs_only_on_push_and_schedule() -> None:
    wf = _load_workflow()
    vault_lint = wf["jobs"]["vault-lint"]
    condition = vault_lint.get("if", "")
    assert "push" in condition, "vault-lint if condition must include push event"
    assert "schedule" in condition, "vault-lint if condition must include schedule event"


def test_ci_workflow_vault_lint_uses_uv_and_checkout() -> None:
    wf = _load_workflow()
    vault_lint = wf["jobs"]["vault-lint"]
    steps = vault_lint.get("steps", [])
    uses_list = [s.get("uses", "") for s in steps if isinstance(s, dict)]
    assert any("actions/checkout@v4" in u for u in uses_list), (
        "vault-lint job must use actions/checkout@v4"
    )
    assert any("astral-sh/setup-uv" in u for u in uses_list), (
        "vault-lint job must use astral-sh/setup-uv"
    )


def test_ci_workflow_vault_lint_steps_invoke_ai_research_vault_lint() -> None:
    wf = _load_workflow()
    vault_lint = wf["jobs"]["vault-lint"]
    steps = vault_lint.get("steps", [])
    run_blobs = " \n ".join(step.get("run", "") for step in steps if isinstance(step, dict))
    assert "vault-lint" in run_blobs, (
        "vault-lint job must invoke 'ai-research vault-lint' in at least one step"
    )


def test_ci_workflow_vault_lint_checks_fixture_and_wiki_dirs() -> None:
    """Both tests/fixtures/vault and wiki/ must be guarded in vault-lint steps."""
    wf = _load_workflow()
    vault_lint = wf["jobs"]["vault-lint"]
    steps = vault_lint.get("steps", [])
    run_blobs = " \n ".join(step.get("run", "") for step in steps if isinstance(step, dict))
    assert "tests/fixtures/vault" in run_blobs, "vault-lint job must lint tests/fixtures/vault"
    assert "wiki" in run_blobs, "vault-lint job must lint wiki/ directory"
