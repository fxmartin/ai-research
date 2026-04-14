"""Golden test for rebuild_index (Story 04.1-001).

``rebuild_index`` sorts pages by POSIX relative path and emits one line per
page, so repeat runs on an unchanged vault diff to zero bytes. No timestamps
are produced, so only path normalization is needed (and only implicitly —
the index records relative paths already).
"""

from __future__ import annotations

import shutil
from pathlib import Path

from ai_research.wiki.index_rebuild import rebuild_index
from tests.golden.conftest import GoldenComparator


def test_rebuild_index_golden(
    golden: GoldenComparator, golden_fixtures: Path, tmp_path: Path
) -> None:
    fixture_dir = golden_fixtures / "index_rebuild"
    expected_path = fixture_dir / "expected" / "index.md"

    # Copy fixture wiki to a tmp workspace so rebuild_index's atomic_write
    # never pollutes the repo tree, and so tests stay hermetic.
    wiki_src = fixture_dir / "input" / "wiki"
    wiki_dir = tmp_path / "wiki"
    shutil.copytree(wiki_src, wiki_dir)
    index_path = tmp_path / ".ai-research" / "index.md"

    rebuild_index(wiki_dir=wiki_dir, index_path=index_path)

    rendered = index_path.read_text(encoding="utf-8")
    golden.compare(expected_path, rendered, label="index_rebuild/index.md")
