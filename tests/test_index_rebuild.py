"""Tests for ai_research.wiki.index_rebuild (Story 02.2-001)."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from ai_research.cli import app
from ai_research.wiki.index_rebuild import IndexEntry, rebuild_index


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _sample_page(
    title: str = "Attention Is All You Need",
    tags: list[str] | None = None,
    summary: str = "Seminal transformer paper.",
    body: str = (
        "# Attention Is All You Need\n\n"
        "The transformer replaces recurrence with self-attention.\n\n"
        "## Architecture\n\nEncoder-decoder stack.\n\n"
        "## Results\n\nSee [[bleu]] and [[wmt]] and [[bleu]].\n"
    ),
) -> str:
    tag_line = ""
    if tags is not None:
        tag_line = "tags:\n" + "".join(f"  - {t}\n" for t in tags)
    return f"---\ntitle: {title}\n{tag_line}summary: {summary}\n---\n{body}"


def test_rebuild_index_excludes_wiki_raw_inbox(tmp_path: Path) -> None:
    """Web Clipper inbox at wiki/raw/ must NOT be indexed (Issue #27).

    Raw clippings are ephemeral ingest inputs living inside the vault for
    Obsidian visibility. They must not appear in .ai-research/index.md or
    compete for retrieval shortlisting alongside curated pages.
    """
    wiki = tmp_path / "wiki"
    _write(wiki / "attention.md", _sample_page())
    _write(
        wiki / "raw" / "clip.md",
        "---\ntitle: Raw Clipping\n---\n# Raw Clipping\n\ndo not index.\n",
    )
    index_path = tmp_path / ".ai-research" / "index.md"

    entries = rebuild_index(wiki_dir=wiki, index_path=index_path)

    rel_paths = {e.relative_path.as_posix() for e in entries}
    assert "attention.md" in rel_paths
    assert not any(p.startswith("raw/") for p in rel_paths), rel_paths

    content = index_path.read_text(encoding="utf-8")
    assert "raw/clip.md" not in content
    assert "Raw Clipping" not in content


def test_rebuild_index_creates_file(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    _write(wiki / "attention.md", _sample_page(tags=["ml", "nlp"]))
    index_path = tmp_path / ".ai-research" / "index.md"

    entries = rebuild_index(wiki_dir=wiki, index_path=index_path)

    assert index_path.exists()
    assert len(entries) == 1
    entry = entries[0]
    assert isinstance(entry, IndexEntry)
    assert entry.title == "Attention Is All You Need"
    assert entry.tags == ["ml", "nlp"]
    assert entry.summary == "Seminal transformer paper."
    assert entry.h1s == ["Attention Is All You Need"]
    # Three wikilinks in body (bleu, wmt, bleu).
    assert entry.outbound_links == 3

    content = index_path.read_text(encoding="utf-8")
    assert "Attention Is All You Need" in content
    assert "ml" in content and "nlp" in content
    assert "links:3" in content


def test_rebuild_index_is_deterministic(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    _write(wiki / "a.md", _sample_page(title="Alpha"))
    _write(wiki / "b.md", _sample_page(title="Beta"))
    index_path = tmp_path / ".ai-research" / "index.md"

    rebuild_index(wiki_dir=wiki, index_path=index_path)
    first = index_path.read_bytes()
    rebuild_index(wiki_dir=wiki, index_path=index_path)
    second = index_path.read_bytes()

    assert first == second


def test_rebuild_index_title_falls_back_to_h1_then_stem(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    # No title frontmatter; H1 in body.
    _write(
        wiki / "no-title.md",
        "---\nfoo: bar\n---\n# From H1\n\nbody\n",
    )
    # No frontmatter at all, no H1 — fall back to stem.
    _write(wiki / "bare.md", "just a body with no heading\n")
    index_path = tmp_path / "index.md"

    entries = rebuild_index(wiki_dir=wiki, index_path=index_path)
    titles = {e.path.name: e.title for e in entries}
    assert titles["no-title.md"] == "From H1"
    assert titles["bare.md"] == "bare"


def test_rebuild_index_marks_invalid_frontmatter(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    # Malformed YAML inside the frontmatter fence.
    _write(
        wiki / "broken.md",
        "---\ntitle: [unterminated\n  bad: : :\n---\nbody\n",
    )
    index_path = tmp_path / "index.md"

    entries = rebuild_index(wiki_dir=wiki, index_path=index_path)
    assert len(entries) == 1
    assert entries[0].invalid is True
    content = index_path.read_text(encoding="utf-8")
    assert "[INVALID]" in content


def test_rebuild_index_empty_wiki(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    wiki.mkdir()
    index_path = tmp_path / "index.md"
    entries = rebuild_index(wiki_dir=wiki, index_path=index_path)
    assert entries == []
    assert index_path.exists()
    assert index_path.read_text(encoding="utf-8") == ""


def test_rebuild_index_missing_wiki_dir(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        rebuild_index(wiki_dir=tmp_path / "nope", index_path=tmp_path / "index.md")


def test_rebuild_index_sorts_by_relative_path(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    _write(wiki / "zeta.md", _sample_page(title="Zeta"))
    _write(wiki / "concepts" / "alpha.md", _sample_page(title="Alpha"))
    _write(wiki / "beta.md", _sample_page(title="Beta"))
    index_path = tmp_path / "index.md"
    entries = rebuild_index(wiki_dir=wiki, index_path=index_path)
    rel_paths = [str(e.relative_path) for e in entries]
    assert rel_paths == sorted(rel_paths)


def test_rebuild_index_ignores_dotfiles_and_non_md(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    _write(wiki / "page.md", _sample_page())
    _write(wiki / ".hidden.md", _sample_page(title="Hidden"))
    _write(wiki / "notes.txt", "ignored\n")
    index_path = tmp_path / "index.md"
    entries = rebuild_index(wiki_dir=wiki, index_path=index_path)
    names = [e.path.name for e in entries]
    assert names == ["page.md"]


def test_rebuild_index_line_format(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    _write(
        wiki / "p.md",
        _sample_page(
            title="T",
            tags=["x"],
            summary="S",
            body="# T\n\n# One\n\n# Two\n\nbody [[a]]\n",
        ),
    )
    index_path = tmp_path / "index.md"
    rebuild_index(wiki_dir=wiki, index_path=index_path)
    line = index_path.read_text(encoding="utf-8").strip()
    # Format: <relpath> · title: <title> · tags: <csv> · h1: <a;b> · links:<n> · <summary>
    assert line.startswith("p.md")
    assert "title: T" in line
    assert "tags: x" in line
    assert "h1: T; One; Two" in line
    assert "links:1" in line
    assert line.endswith("S")


def test_rebuild_index_scalar_tag(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    # Frontmatter ``tags`` as a bare scalar rather than a list.
    _write(wiki / "p.md", "---\ntitle: T\ntags: solo\n---\nbody\n")
    index_path = tmp_path / "index.md"
    entries = rebuild_index(wiki_dir=wiki, index_path=index_path)
    assert entries[0].tags == ["solo"]


def test_cli_index_rebuild(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    _write(wiki / "p.md", _sample_page(title="T", tags=["a"]))
    index_path = tmp_path / ".ai-research" / "index.md"

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "index-rebuild",
            "--wiki-dir",
            str(wiki),
            "--index-file",
            str(index_path),
        ],
    )
    assert result.exit_code == 0, result.output
    assert index_path.exists()
    assert "T" in index_path.read_text(encoding="utf-8")


def test_cli_index_rebuild_missing_wiki(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "index-rebuild",
            "--wiki-dir",
            str(tmp_path / "nope"),
            "--index-file",
            str(tmp_path / "index.md"),
        ],
    )
    assert result.exit_code == 2
