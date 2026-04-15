"""Golden test for materialize (Story 04.1-001).

``materialize`` stamps an ``ingested_at`` timestamp and records the absolute
source path in frontmatter. Both are normalized before comparing against
the golden — timestamps via the shared regex, the source path via a literal
substitution for the tmp-path prefix.
"""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

from ai_research.wiki.materialize import MaterializeStatus, materialize
from tests.golden.conftest import GoldenComparator, normalize_paths, normalize_timestamps

FIXED_NOW = datetime(2026, 4, 14, 12, 0, 0, tzinfo=UTC)


def test_materialize_golden(
    golden: GoldenComparator, golden_fixtures: Path, tmp_path: Path
) -> None:
    fixture_dir = golden_fixtures / "materialize"
    expected_path = fixture_dir / "expected" / "golden-materialize-page.md"

    # Stage fixture inputs into a hermetic workspace so the toolkit's
    # atomic writes never touch the repo tree.
    workspace = tmp_path / "workspace"
    sources_dir = workspace / "sources"
    sources_dir.mkdir(parents=True)
    source = sources_dir / "source.md"
    shutil.copy(fixture_dir / "input" / "source.md", source)
    draft = workspace / "draft.md"
    shutil.copy(fixture_dir / "input" / "draft.md", draft)

    wiki_dir = workspace / "wiki"
    state_path = workspace / ".ai-research" / "state.json"

    result = materialize(
        source=source,
        draft_path=draft,
        wiki_dir=wiki_dir,
        state_path=state_path,
        now=FIXED_NOW,
        no_archive=True,
    )
    assert result.status is MaterializeStatus.CREATED

    rendered = result.page_path.read_text(encoding="utf-8")
    # Normalize volatile bits: wall-clock timestamps and the tmp-path prefix
    # in the recorded ``source:`` field.
    rendered = normalize_timestamps(rendered)
    rendered = normalize_paths(rendered, (str(source), "<FIXTURE>/sources/source.md"))

    golden.compare(expected_path, rendered, label="materialize/golden-materialize-page.md")
