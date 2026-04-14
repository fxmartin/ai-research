"""Tests for ai_research.wiki.materialize (Story 02.1-001)."""

from __future__ import annotations

import io
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import frontmatter
import pytest

from ai_research.state import State, load_state, save_state
from ai_research.wiki.materialize import (
    MaterializeResult,
    materialize,
)

FIXED_NOW = datetime(2026, 4, 14, 12, 0, 0, tzinfo=UTC)


def _setup_source(tmp_path: Path, content: str = "raw source bytes\n") -> Path:
    src = tmp_path / "sources" / "paper.md"
    src.parent.mkdir(parents=True)
    src.write_text(content, encoding="utf-8")
    return src


def test_materialize_writes_page_with_frontmatter(tmp_path: Path) -> None:
    source = _setup_source(tmp_path)
    draft = tmp_path / "draft.md"
    draft.write_text("# Attention Is All You Need\n\nBody paragraph.\n", encoding="utf-8")
    wiki_dir = tmp_path / "wiki"
    state_path = tmp_path / ".ai-research" / "state.json"

    result = materialize(
        source=source,
        draft_path=draft,
        wiki_dir=wiki_dir,
        state_path=state_path,
        now=FIXED_NOW,
    )

    assert isinstance(result, MaterializeResult)
    page_path = wiki_dir / "attention-is-all-you-need.md"
    assert result.page_path == page_path
    assert page_path.exists()

    post = frontmatter.loads(page_path.read_text(encoding="utf-8"))
    assert post["title"] == "Attention Is All You Need"
    assert post["source"] == str(source)
    assert post["ingested_at"] == FIXED_NOW.isoformat()
    assert post["source_hash"] == result.source_hash
    assert post["locked"] is False
    # Body now ends with the ## Sources back-reference (Story 02.2-003).
    assert "Body paragraph." in post.content
    assert post.content.rstrip().endswith(f"]({source.relative_to(tmp_path)})")


def test_materialize_updates_state_mapping(tmp_path: Path) -> None:
    source = _setup_source(tmp_path)
    draft = tmp_path / "draft.md"
    draft.write_text("# Foo\n\nBody.\n", encoding="utf-8")
    wiki_dir = tmp_path / "wiki"
    state_path = tmp_path / ".ai-research" / "state.json"

    result = materialize(
        source=source,
        draft_path=draft,
        wiki_dir=wiki_dir,
        state_path=state_path,
        now=FIXED_NOW,
    )

    state = load_state(state_path)
    rel = str(result.page_path.relative_to(tmp_path))
    assert state.sources[result.source_hash] == rel
    assert state.pages[rel] == [result.source_hash]


def test_materialize_reads_stdin_when_draft_is_none(tmp_path: Path) -> None:
    source = _setup_source(tmp_path)
    wiki_dir = tmp_path / "wiki"
    state_path = tmp_path / ".ai-research" / "state.json"

    stdin = io.StringIO("# From Stdin\n\nStreamed body.\n")
    result = materialize(
        source=source,
        draft_path=None,
        wiki_dir=wiki_dir,
        state_path=state_path,
        now=FIXED_NOW,
        stdin=stdin,
    )

    page_path = wiki_dir / "from-stdin.md"
    assert result.page_path == page_path
    assert "Streamed body." in page_path.read_text(encoding="utf-8")


def test_materialize_slug_falls_back_to_source_stem_when_no_title(tmp_path: Path) -> None:
    source = tmp_path / "sources" / "my-paper.md"
    source.parent.mkdir(parents=True)
    source.write_text("bytes", encoding="utf-8")
    draft = tmp_path / "draft.md"
    draft.write_text("Body without heading.\n", encoding="utf-8")
    wiki_dir = tmp_path / "wiki"
    state_path = tmp_path / ".ai-research" / "state.json"

    result = materialize(
        source=source,
        draft_path=draft,
        wiki_dir=wiki_dir,
        state_path=state_path,
        now=FIXED_NOW,
    )

    assert result.page_path == wiki_dir / "my-paper.md"
    post = frontmatter.loads(result.page_path.read_text(encoding="utf-8"))
    assert post["title"] == "my-paper"


def test_materialize_crash_mid_write_leaves_no_partial_file(tmp_path: Path) -> None:
    source = _setup_source(tmp_path)
    draft = tmp_path / "draft.md"
    draft.write_text("# Title\n\nBody.\n", encoding="utf-8")
    wiki_dir = tmp_path / "wiki"
    state_path = tmp_path / ".ai-research" / "state.json"

    def boom(_src: str, _dst: str) -> None:
        raise OSError("simulated crash before rename")

    with patch("ai_research.state.os.replace", side_effect=boom):
        with pytest.raises(OSError):
            materialize(
                source=source,
                draft_path=draft,
                wiki_dir=wiki_dir,
                state_path=state_path,
                now=FIXED_NOW,
            )

    assert not (wiki_dir / "title.md").exists()
    assert list(wiki_dir.glob("*.tmp*")) == [] if wiki_dir.exists() else True


def test_materialize_stdin_requires_stream(tmp_path: Path) -> None:
    source = _setup_source(tmp_path)
    wiki_dir = tmp_path / "wiki"
    state_path = tmp_path / ".ai-research" / "state.json"

    with pytest.raises(ValueError, match="draft_path or stdin"):
        materialize(
            source=source,
            draft_path=None,
            wiki_dir=wiki_dir,
            state_path=state_path,
            now=FIXED_NOW,
            stdin=None,
        )


def test_materialize_missing_source_raises(tmp_path: Path) -> None:
    draft = tmp_path / "draft.md"
    draft.write_text("# x\n", encoding="utf-8")
    with pytest.raises(FileNotFoundError):
        materialize(
            source=tmp_path / "missing.md",
            draft_path=draft,
            wiki_dir=tmp_path / "wiki",
            state_path=tmp_path / "state.json",
            now=FIXED_NOW,
        )


def test_materialize_preserves_existing_frontmatter_in_draft(tmp_path: Path) -> None:
    """If the draft already contains frontmatter, merge with ours (ours wins)."""
    source = _setup_source(tmp_path)
    draft = tmp_path / "draft.md"
    draft.write_text(
        "---\ntitle: Custom Title\ntags: [ml, transformers]\n---\n# Ignored H1\n\nBody.\n",
        encoding="utf-8",
    )
    wiki_dir = tmp_path / "wiki"
    state_path = tmp_path / ".ai-research" / "state.json"

    result = materialize(
        source=source,
        draft_path=draft,
        wiki_dir=wiki_dir,
        state_path=state_path,
        now=FIXED_NOW,
    )

    post = frontmatter.loads(result.page_path.read_text(encoding="utf-8"))
    assert post["title"] == "Custom Title"
    assert post["tags"] == ["ml", "transformers"]
    assert post["source_hash"] == result.source_hash
    assert post["locked"] is False
    assert result.page_path == wiki_dir / "custom-title.md"


def test_materialize_cli_command(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from ai_research.cli import app

    source = _setup_source(tmp_path)
    draft = tmp_path / "draft.md"
    draft.write_text("# CLI Page\n\nHello.\n", encoding="utf-8")
    wiki_dir = tmp_path / "wiki"
    state_path = tmp_path / "state.json"

    runner = CliRunner()
    res = runner.invoke(
        app,
        [
            "materialize",
            "--source",
            str(source),
            "--from",
            str(draft),
            "--wiki-dir",
            str(wiki_dir),
            "--state-file",
            str(state_path),
        ],
    )
    assert res.exit_code == 0, res.output
    assert (wiki_dir / "cli-page.md").exists()
    assert str(wiki_dir / "cli-page.md") in res.output


def test_materialize_cli_stdin(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from ai_research.cli import app

    source = _setup_source(tmp_path)
    wiki_dir = tmp_path / "wiki"
    state_path = tmp_path / "state.json"

    runner = CliRunner()
    res = runner.invoke(
        app,
        [
            "materialize",
            "--source",
            str(source),
            "--stdin",
            "--wiki-dir",
            str(wiki_dir),
            "--state-file",
            str(state_path),
        ],
        input="# Piped Page\n\nBody from stdin.\n",
    )
    assert res.exit_code == 0, res.output
    assert (wiki_dir / "piped-page.md").exists()


def test_materialize_cli_requires_from_or_stdin(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from ai_research.cli import app

    source = _setup_source(tmp_path)
    runner = CliRunner()
    res = runner.invoke(
        app,
        [
            "materialize",
            "--source",
            str(source),
            "--wiki-dir",
            str(tmp_path / "wiki"),
            "--state-file",
            str(tmp_path / "state.json"),
        ],
    )
    assert res.exit_code == 2
    assert "--from" in res.output or "--stdin" in res.output


def test_materialize_cli_missing_source(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from ai_research.cli import app

    runner = CliRunner()
    res = runner.invoke(
        app,
        [
            "materialize",
            "--source",
            str(tmp_path / "nope.md"),
            "--from",
            str(tmp_path / "draft.md"),
        ],
    )
    assert res.exit_code != 0


def test_materialize_re_records_same_hash_without_duplicating(tmp_path: Path) -> None:
    """Calling materialize twice should not double-append the hash to pages[]."""
    source = _setup_source(tmp_path)
    draft = tmp_path / "draft.md"
    draft.write_text("# Page\n\nBody.\n", encoding="utf-8")
    wiki_dir = tmp_path / "wiki"
    state_path = tmp_path / ".ai-research" / "state.json"

    r1 = materialize(
        source=source,
        draft_path=draft,
        wiki_dir=wiki_dir,
        state_path=state_path,
        now=FIXED_NOW,
    )
    r2 = materialize(
        source=source,
        draft_path=draft,
        wiki_dir=wiki_dir,
        state_path=state_path,
        now=FIXED_NOW,
    )
    assert r1.source_hash == r2.source_hash
    state = load_state(state_path)
    rel = str(r1.page_path.relative_to(tmp_path))
    assert state.pages[rel] == [r1.source_hash]


def test_materialize_page_outside_state_root_falls_back_to_absolute(tmp_path: Path) -> None:
    """When the page lives outside state_path's anchor, use absolute path."""
    source = _setup_source(tmp_path)
    draft = tmp_path / "draft.md"
    draft.write_text("# Out\n\nBody.\n", encoding="utf-8")
    # state.json at tmp_path/s/state.json -> anchor is tmp_path/.. (above tmp_path)
    # so a wiki page inside tmp_path IS relative — we need the opposite:
    # put state.json deep and wiki elsewhere.
    state_path = tmp_path / "a" / "b" / "c" / "state.json"
    wiki_dir = tmp_path / "elsewhere" / "wiki"

    result = materialize(
        source=source,
        draft_path=draft,
        wiki_dir=wiki_dir,
        state_path=state_path,
        now=FIXED_NOW,
    )
    state = load_state(state_path)
    # Expect an absolute path string (fallback branch).
    recorded = state.sources[result.source_hash]
    assert Path(recorded).is_absolute()


def test_materialize_payload_already_newline_terminated(tmp_path: Path) -> None:
    """Frontmatter.dumps normally ends with no trailing newline; force the
    already-terminated branch by patching dumps."""
    from unittest.mock import patch as _patch

    source = _setup_source(tmp_path)
    draft = tmp_path / "draft.md"
    draft.write_text("# Nl\n\nBody.\n", encoding="utf-8")
    wiki_dir = tmp_path / "wiki"
    state_path = tmp_path / "state.json"

    real_dumps = frontmatter.dumps

    def dumps_with_trailing_newline(post: frontmatter.Post) -> str:
        return real_dumps(post) + "\n"

    with _patch(
        "ai_research.wiki.materialize.frontmatter.dumps",
        side_effect=dumps_with_trailing_newline,
    ):
        result = materialize(
            source=source,
            draft_path=draft,
            wiki_dir=wiki_dir,
            state_path=state_path,
            now=FIXED_NOW,
        )
    content = result.page_path.read_bytes()
    assert content.endswith(b"\n")
    assert not content.endswith(b"\n\n\n")


def test_materialize_writes_sources_section(tmp_path: Path) -> None:
    """AC1: page body ends with ## Sources listing the archived source."""
    source = _setup_source(tmp_path)
    draft = tmp_path / "draft.md"
    draft.write_text("# Page\n\nBody.\n", encoding="utf-8")
    wiki_dir = tmp_path / "wiki"
    state_path = tmp_path / "state.json"

    result = materialize(
        source=source,
        draft_path=draft,
        wiki_dir=wiki_dir,
        state_path=state_path,
        now=FIXED_NOW,
    )
    text = result.page_path.read_text(encoding="utf-8")
    assert "## Sources" in text
    # Path should be relative to the vault's parent (tmp_path).
    assert "- [Page](sources/paper.md)" in text


def test_materialize_rematerialize_same_source_is_idempotent(tmp_path: Path) -> None:
    """AC: re-running with the same source does not duplicate the bullet."""
    source = _setup_source(tmp_path)
    draft = tmp_path / "draft.md"
    draft.write_text("# Page\n\nBody.\n", encoding="utf-8")
    wiki_dir = tmp_path / "wiki"
    state_path = tmp_path / "state.json"

    materialize(
        source=source,
        draft_path=draft,
        wiki_dir=wiki_dir,
        state_path=state_path,
        now=FIXED_NOW,
    )
    r2 = materialize(
        source=source,
        draft_path=draft,
        wiki_dir=wiki_dir,
        state_path=state_path,
        now=FIXED_NOW,
    )
    text = r2.page_path.read_text(encoding="utf-8")
    assert text.count("- [Page](sources/paper.md)") == 1
    assert text.count("## Sources") == 1


def test_materialize_appends_new_source_to_existing_page(tmp_path: Path) -> None:
    """AC2: re-materializing with a different source path appends a new bullet."""
    source_a = _setup_source(tmp_path, content="alpha\n")
    draft = tmp_path / "draft.md"
    draft.write_text("# Page\n\nBody.\n", encoding="utf-8")
    wiki_dir = tmp_path / "wiki"
    state_path = tmp_path / "state.json"

    materialize(
        source=source_a,
        draft_path=draft,
        wiki_dir=wiki_dir,
        state_path=state_path,
        now=FIXED_NOW,
    )

    # Different source file with the same resulting title (so same page slug).
    source_b = tmp_path / "sources" / "paper2.md"
    source_b.write_text("beta\n", encoding="utf-8")
    r2 = materialize(
        source=source_b,
        draft_path=draft,
        wiki_dir=wiki_dir,
        state_path=state_path,
        now=FIXED_NOW,
    )
    text = r2.page_path.read_text(encoding="utf-8")
    assert "sources/paper.md" in text
    assert "sources/paper2.md" in text
    assert text.count("## Sources") == 1


def test_materialize_url_source_records_original_url(tmp_path: Path) -> None:
    """AC3: URL sources embed both archived path AND original URL."""
    source = _setup_source(tmp_path)
    draft = tmp_path / "draft.md"
    draft.write_text("# Gist\n\nBody.\n", encoding="utf-8")
    wiki_dir = tmp_path / "wiki"
    state_path = tmp_path / "state.json"

    url = "https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f"
    result = materialize(
        source=source,
        draft_path=draft,
        wiki_dir=wiki_dir,
        state_path=state_path,
        now=FIXED_NOW,
        source_url=url,
    )
    text = result.page_path.read_text(encoding="utf-8")
    assert "## Sources" in text
    assert "sources/paper.md" in text
    assert url in text


def test_materialize_cli_passes_source_url(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from ai_research.cli import app

    source = _setup_source(tmp_path)
    draft = tmp_path / "draft.md"
    draft.write_text("# Urlpage\n\nBody.\n", encoding="utf-8")
    wiki_dir = tmp_path / "wiki"
    state_path = tmp_path / "state.json"

    runner = CliRunner()
    res = runner.invoke(
        app,
        [
            "materialize",
            "--source",
            str(source),
            "--from",
            str(draft),
            "--wiki-dir",
            str(wiki_dir),
            "--state-file",
            str(state_path),
            "--source-url",
            "https://example.com/doc",
        ],
    )
    assert res.exit_code == 0, res.output
    text = (wiki_dir / "urlpage.md").read_text(encoding="utf-8")
    assert "https://example.com/doc" in text


def test_materialize_appends_to_existing_state(tmp_path: Path) -> None:
    """An existing state.json entry is preserved when we add a new page."""
    state_path = tmp_path / "state.json"
    save_state(state_path, State(sources={"deadbeef": "wiki/other.md"}))

    source = _setup_source(tmp_path)
    draft = tmp_path / "draft.md"
    draft.write_text("# Fresh\n\nBody.\n", encoding="utf-8")
    wiki_dir = tmp_path / "wiki"

    result = materialize(
        source=source,
        draft_path=draft,
        wiki_dir=wiki_dir,
        state_path=state_path,
        now=FIXED_NOW,
    )

    state = load_state(state_path)
    assert state.sources["deadbeef"] == "wiki/other.md"
    assert result.source_hash in state.sources
