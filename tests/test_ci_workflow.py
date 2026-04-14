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
