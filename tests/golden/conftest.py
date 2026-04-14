"""Golden-file test harness for deterministic toolkit verbs (Story 04.1-001).

Design
------
A golden-file test records a deterministic verb's output on a recorded
fixture input and asserts that subsequent runs produce byte-identical
output. Timestamps (and a handful of environment-coupled fields such as
absolute paths) are normalized with stable placeholders before comparison
so CI on any machine still diffs to zero bytes.

Pass ``--update-golden`` to rewrite expected files rather than fail on
mismatch. Intended for deliberate refreshes only; the resulting diff should
be reviewed in the PR.
"""

from __future__ import annotations

import difflib
import re
from collections.abc import Callable
from pathlib import Path

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--update-golden",
        action="store_true",
        default=False,
        help="Rewrite golden expected files instead of failing on mismatch.",
    )


# Match an ISO-8601 UTC timestamp like 2026-04-14T12:00:00+00:00 or with Z suffix.
_ISO_TIMESTAMP_RE = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})"
)


def normalize_timestamps(text: str) -> str:
    """Replace ISO-8601 timestamps with a stable placeholder.

    The placeholder token ``<TIMESTAMP>`` is deliberately pipe-free so
    index.md's ``·``-delimited format stays aligned.
    """
    return _ISO_TIMESTAMP_RE.sub("<TIMESTAMP>", text)


def normalize_paths(text: str, *substitutions: tuple[str, str]) -> str:
    """Apply literal ``(needle, replacement)`` substitutions in order.

    Used to scrub tmp-path prefixes that vary between machines out of
    emitted records so goldens stay byte-stable.
    """
    for needle, replacement in substitutions:
        text = text.replace(needle, replacement)
    return text


GoldenNormalizer = Callable[[str], str]


def _diff(expected: str, actual: str, label: str) -> str:
    return "\n".join(
        difflib.unified_diff(
            expected.splitlines(),
            actual.splitlines(),
            fromfile=f"{label} (expected)",
            tofile=f"{label} (actual)",
            lineterm="",
        )
    )


class GoldenComparator:
    """Helper bound to the active pytest config for update/compare dispatch."""

    def __init__(self, *, update: bool) -> None:
        self.update = update

    def compare(self, expected_path: Path, actual: str, *, label: str | None = None) -> None:
        """Compare ``actual`` string against the file at ``expected_path``.

        When ``--update-golden`` is active, rewrites the expected file and
        passes; otherwise fails with a unified diff on mismatch.
        """
        label = label or expected_path.name
        if self.update:
            expected_path.parent.mkdir(parents=True, exist_ok=True)
            expected_path.write_text(actual, encoding="utf-8")
            return
        if not expected_path.exists():
            pytest.fail(
                f"Golden file missing: {expected_path}. Rerun with --update-golden to create it."
            )
        expected = expected_path.read_text(encoding="utf-8")
        if expected != actual:
            pytest.fail(
                "Golden mismatch for "
                f"{label}:\n{_diff(expected, actual, label)}\n"
                "Rerun with --update-golden to accept."
            )


@pytest.fixture
def golden(request: pytest.FixtureRequest) -> GoldenComparator:
    """Return a :class:`GoldenComparator` respecting ``--update-golden``."""
    return GoldenComparator(update=request.config.getoption("--update-golden"))


FIXTURES_ROOT = Path(__file__).parent / "fixtures"


@pytest.fixture
def golden_fixtures() -> Path:
    """Absolute path to ``tests/golden/fixtures/``."""
    return FIXTURES_ROOT
