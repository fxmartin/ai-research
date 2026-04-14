"""Golden test for extract_markdown (Story 04.1-001).

Verifies that the markdown extractor produces byte-identical output for a
recorded fixture, modulo the absolute-path field which is normalized to a
stable placeholder.
"""

from __future__ import annotations

import json
from pathlib import Path

from ai_research.extract.markdown import extract_markdown
from tests.golden.conftest import GoldenComparator, normalize_paths


def test_extract_markdown_golden(golden: GoldenComparator, golden_fixtures: Path) -> None:
    fixture_dir = golden_fixtures / "extract_markdown"
    input_path = fixture_dir / "input" / "sample.md"
    expected_path = fixture_dir / "expected" / "sample.extract.json"

    result = extract_markdown(input_path)

    # The resolved path is machine-specific; scrub it to a stable placeholder.
    resolved = str(input_path.resolve())
    result["metadata"]["path"] = "<FIXTURE>/sample.md"
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    rendered = normalize_paths(rendered, (resolved, "<FIXTURE>/sample.md"))

    golden.compare(expected_path, rendered, label="extract_markdown/sample")
