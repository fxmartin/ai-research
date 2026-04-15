"""Tests for ai_research.wiki.stubs (Story 02.1-003)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import frontmatter

from ai_research.wiki.materialize import materialize
from ai_research.wiki.stubs import (
    create_stub,
    create_stubs_for_body,
    extract_wikilinks,
    retire_stub_if_exists,
)

FIXED_NOW = datetime(2026, 4, 14, 12, 0, 0, tzinfo=UTC)


# ---------------------------------------------------------------------------
# extract_wikilinks
# ---------------------------------------------------------------------------


def test_extract_wikilinks_finds_basic_links() -> None:
    body = "See [[Attention]] and [[Transformer]] for context."
    assert extract_wikilinks(body) == ["Attention", "Transformer"]


def test_extract_wikilinks_deduplicates_preserving_order() -> None:
    body = "[[A]] and [[B]] and [[A]] again"
    assert extract_wikilinks(body) == ["A", "B"]


def test_extract_wikilinks_strips_alias_and_anchor() -> None:
    body = "[[Target Page|display]] and [[Page#Section]] and [[Page#Sec|alias]]"
    assert extract_wikilinks(body) == ["Target Page", "Page"]


def test_extract_wikilinks_empty_when_none() -> None:
    assert extract_wikilinks("no links here") == []


def test_extract_wikilinks_ignores_empty_link() -> None:
    assert extract_wikilinks("[[   ]] nothing") == []


# ---------------------------------------------------------------------------
# create_stub
# ---------------------------------------------------------------------------


def test_create_stub_writes_new_file(tmp_path: Path) -> None:
    wiki_dir = tmp_path / "wiki"
    result = create_stub("Self Attention", wiki_dir=wiki_dir, now=FIXED_NOW)

    stub_path = wiki_dir / "concepts" / "self-attention.md"
    assert result == stub_path
    assert stub_path.exists()

    post = frontmatter.loads(stub_path.read_text(encoding="utf-8"))
    assert post["type"] == "concept"
    assert post["stub"] is True
    assert post["title"] == "Self Attention"
    assert post["created"] == FIXED_NOW.isoformat()
    assert "Self Attention" in post.content


def test_create_stub_is_idempotent(tmp_path: Path) -> None:
    wiki_dir = tmp_path / "wiki"
    first = create_stub("Topic", wiki_dir=wiki_dir, now=FIXED_NOW)
    mtime_before = first.stat().st_mtime_ns

    later = datetime(2027, 1, 1, tzinfo=UTC)
    second = create_stub("Topic", wiki_dir=wiki_dir, now=later)

    assert second == first
    assert first.stat().st_mtime_ns == mtime_before


def test_create_stub_skips_when_full_page_exists_at_same_slug(tmp_path: Path) -> None:
    """A full wiki page at wiki/<slug>.md means the concept is already covered."""
    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir()
    existing = wiki_dir / "transformer.md"
    existing.write_text("---\ntitle: Transformer\n---\nFull page.\n", encoding="utf-8")

    result = create_stub("Transformer", wiki_dir=wiki_dir, now=FIXED_NOW)

    assert result == existing
    assert not (wiki_dir / "concepts" / "transformer.md").exists()


def test_create_stub_defaults_now_to_wallclock(tmp_path: Path) -> None:
    wiki_dir = tmp_path / "wiki"
    stub_path = create_stub("Wall Clock", wiki_dir=wiki_dir)
    post = frontmatter.loads(stub_path.read_text(encoding="utf-8"))
    # ISO-8601 round-trip; must be tz-aware UTC.
    parsed = datetime.fromisoformat(str(post["created"]))
    assert parsed.tzinfo is not None


# ---------------------------------------------------------------------------
# create_stubs_for_body
# ---------------------------------------------------------------------------


def test_create_stubs_for_body_creates_only_missing(tmp_path: Path) -> None:
    wiki_dir = tmp_path / "wiki"
    (wiki_dir).mkdir()
    (wiki_dir / "transformer.md").write_text(
        "---\ntitle: Transformer\n---\nFull.\n", encoding="utf-8"
    )

    body = "See [[Transformer]] and [[Self Attention]] and [[Softmax]]."
    created = create_stubs_for_body(body, wiki_dir=wiki_dir, now=FIXED_NOW)

    # Transformer is a full page — not a new stub.
    assert sorted(p.name for p in created) == [
        "self-attention.md",
        "softmax.md",
    ]
    assert (wiki_dir / "concepts" / "self-attention.md").exists()
    assert (wiki_dir / "concepts" / "softmax.md").exists()
    assert not (wiki_dir / "concepts" / "transformer.md").exists()


def test_create_stubs_for_body_no_links_returns_empty(tmp_path: Path) -> None:
    wiki_dir = tmp_path / "wiki"
    assert create_stubs_for_body("nothing", wiki_dir=wiki_dir, now=FIXED_NOW) == []


# ---------------------------------------------------------------------------
# Integration with materialize()
# ---------------------------------------------------------------------------


def _setup_source(tmp_path: Path) -> Path:
    src = tmp_path / "sources" / "paper.md"
    src.parent.mkdir(parents=True)
    src.write_text("raw source bytes\n", encoding="utf-8")
    return src


def test_materialize_creates_stubs_for_wikilinks(tmp_path: Path) -> None:
    source = _setup_source(tmp_path)
    draft = tmp_path / "draft.md"
    draft.write_text(
        "# Main Page\n\nDiscusses [[Attention]] and [[Residual Connection]].\n",
        encoding="utf-8",
    )
    wiki_dir = tmp_path / "wiki"
    state_path = tmp_path / ".ai-research" / "state.json"

    materialize(
        source=source,
        draft_path=draft,
        wiki_dir=wiki_dir,
        state_path=state_path,
        now=FIXED_NOW,
    )

    assert (wiki_dir / "concepts" / "attention.md").exists()
    assert (wiki_dir / "concepts" / "residual-connection.md").exists()
    stub = frontmatter.loads((wiki_dir / "concepts" / "attention.md").read_text(encoding="utf-8"))
    assert stub["stub"] is True
    assert stub["type"] == "concept"


def test_materialize_does_not_stub_self_reference(tmp_path: Path) -> None:
    """A page shouldn't create a stub pointing back to itself."""
    source = _setup_source(tmp_path)
    draft = tmp_path / "draft.md"
    draft.write_text(
        "# Attention\n\nThis page references [[Attention]] by name.\n",
        encoding="utf-8",
    )
    wiki_dir = tmp_path / "wiki"
    state_path = tmp_path / ".ai-research" / "state.json"

    materialize(
        source=source,
        draft_path=draft,
        wiki_dir=wiki_dir,
        state_path=state_path,
        now=FIXED_NOW,
    )

    # The main page exists; no redundant stub.
    assert (wiki_dir / "attention.md").exists()
    assert not (wiki_dir / "concepts" / "attention.md").exists()


# ---------------------------------------------------------------------------
# CLI --stub flag
# ---------------------------------------------------------------------------


def test_cli_stub_flag_creates_stubs(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from ai_research.cli import app

    wiki_dir = tmp_path / "wiki"
    runner = CliRunner()
    res = runner.invoke(
        app,
        [
            "materialize",
            "--stub",
            "Self Attention",
            "--stub",
            "Softmax",
            "--wiki-dir",
            str(wiki_dir),
        ],
    )
    assert res.exit_code == 0, res.output
    assert (wiki_dir / "concepts" / "self-attention.md").exists()
    assert (wiki_dir / "concepts" / "softmax.md").exists()


def test_cli_materialize_requires_source_without_stub(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from ai_research.cli import app

    runner = CliRunner()
    res = runner.invoke(
        app,
        [
            "materialize",
            "--from",
            str(tmp_path / "d.md"),
            "--wiki-dir",
            str(tmp_path / "wiki"),
        ],
    )
    assert res.exit_code == 2
    assert "--source" in res.output


def test_create_stub_payload_already_newline_terminated(tmp_path: Path) -> None:
    """Cover the branch where frontmatter.dumps already ends with a newline."""
    from unittest.mock import patch

    real_dumps = frontmatter.dumps

    def dumps_with_newline(post: frontmatter.Post) -> str:
        return real_dumps(post) + "\n"

    with patch(
        "ai_research.wiki.stubs.frontmatter.dumps",
        side_effect=dumps_with_newline,
    ):
        path = create_stub("Newline Topic", wiki_dir=tmp_path / "wiki", now=FIXED_NOW)
    content = path.read_bytes()
    assert content.endswith(b"\n")
    assert not content.endswith(b"\n\n\n")


def test_cli_stub_flag_is_idempotent(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from ai_research.cli import app

    wiki_dir = tmp_path / "wiki"
    runner = CliRunner()
    runner.invoke(app, ["materialize", "--stub", "Topic", "--wiki-dir", str(wiki_dir)])
    mtime_before = (wiki_dir / "concepts" / "topic.md").stat().st_mtime_ns
    res = runner.invoke(app, ["materialize", "--stub", "Topic", "--wiki-dir", str(wiki_dir)])
    assert res.exit_code == 0
    assert (wiki_dir / "concepts" / "topic.md").stat().st_mtime_ns == mtime_before


# ---------------------------------------------------------------------------
# retire_stub_if_exists (Issue #32)
# ---------------------------------------------------------------------------


def test_retire_stub_removes_true_stub(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    (wiki / "concepts").mkdir(parents=True)
    stub = create_stub("Foo", wiki_dir=wiki, now=FIXED_NOW)
    assert stub.exists()

    removed = retire_stub_if_exists("foo", wiki_dir=wiki)
    assert removed == stub
    assert not stub.exists()


def test_retire_stub_noop_when_missing(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    (wiki / "concepts").mkdir(parents=True)
    assert retire_stub_if_exists("foo", wiki_dir=wiki) is None


def test_retire_stub_preserves_human_authored_concept(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    (wiki / "concepts").mkdir(parents=True)
    concept = wiki / "concepts" / "foo.md"
    # Human-authored concept page — no stub: true.
    concept.write_text(
        "---\ntitle: Foo\ntype: concept\n---\n\nCurated content.\n",
        encoding="utf-8",
    )

    removed = retire_stub_if_exists("foo", wiki_dir=wiki)
    assert removed is None
    assert concept.exists()
    assert "Curated content" in concept.read_text(encoding="utf-8")


def test_materialize_retires_stub_when_full_page_written(tmp_path: Path) -> None:
    # End-to-end: create a stub, then materialize the full page for the same
    # slug. The stub must be gone afterwards.
    wiki = tmp_path / "wiki"
    (wiki / "concepts").mkdir(parents=True)
    sources = tmp_path / "sources"
    sources.mkdir()
    state_file = tmp_path / "state.json"

    stub = create_stub("Dario Amodei", wiki_dir=wiki, now=FIXED_NOW)
    assert stub.exists()

    src = sources / "dario.md"
    src.write_text("# src\n\nbody\n", encoding="utf-8")
    draft_path = tmp_path / "draft.md"
    draft_path.write_text(
        "# Dario Amodei\n\n## Summary\n\nFull page body.\n",
        encoding="utf-8",
    )

    result = materialize(
        source=src,
        draft_path=draft_path,
        wiki_dir=wiki,
        state_path=state_file,
        now=FIXED_NOW,
    )
    assert result.page_path == wiki / "dario-amodei.md"
    assert result.page_path.exists()
    assert not stub.exists(), "stub should be retired after full page materialization"
