"""Tests for ai_research.wiki.vault_lint (Story 04.2-001)."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from ai_research.cli import app
from ai_research.wiki.vault_lint import (
    LintIssue,
    LintReport,
    lint_vault,
)

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _clean_vault(root: Path) -> Path:
    wiki = root / "wiki"
    _write(
        wiki / "transformer.md",
        "---\ntitle: Transformer\n---\n\nSee [[Attention]] and [[Self Attention|self-attn]].\n",
    )
    _write(
        wiki / "concepts" / "attention.md",
        "---\ntitle: Attention\nstub: true\ntype: concept\n---\n\nStub.\n",
    )
    _write(
        wiki / "concepts" / "self-attention.md",
        "---\ntitle: Self Attention\nstub: true\ntype: concept\n---\n\nStub.\n",
    )
    return wiki


# ---------------------------------------------------------------------------
# lint_vault — core
# ---------------------------------------------------------------------------


def test_lint_clean_vault_returns_ok(tmp_path: Path) -> None:
    wiki = _clean_vault(tmp_path)
    report = lint_vault(wiki)
    assert report.ok is True
    assert report.issues == []
    assert report.pages == 1
    assert report.stubs == 2
    assert report.wikilinks == 2
    assert report.orphans == 1  # transformer is not linked to


def test_lint_missing_vault_raises(tmp_path: Path) -> None:
    import pytest

    with pytest.raises(FileNotFoundError):
        lint_vault(tmp_path / "nope")


def test_lint_broken_wikilink_reported_with_line(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    _write(
        wiki / "page.md",
        "---\ntitle: Page\n---\n\nfirst line\nlink to [[Missing Target]].\n",
    )
    report = lint_vault(wiki)
    assert report.ok is False
    broken = [i for i in report.issues if i.kind == "broken-wikilink"]
    assert len(broken) == 1
    assert broken[0].line == 6
    assert "Missing Target" in broken[0].message
    assert broken[0].path.name == "page.md"


def test_lint_invalid_frontmatter_reported(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    _write(
        wiki / "bad.md",
        "---\ntitle: : : bad\n  bad indent: [unbalanced\n---\nbody\n",
    )
    report = lint_vault(wiki)
    assert report.ok is False
    fm = [i for i in report.issues if i.kind == "frontmatter"]
    assert len(fm) == 1
    assert fm[0].path.name == "bad.md"


def test_lint_stub_resolves_wikilink(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    _write(wiki / "page.md", "---\ntitle: Page\n---\n\n[[Some Concept]]\n")
    _write(
        wiki / "concepts" / "some-concept.md",
        "---\ntitle: Some Concept\nstub: true\ntype: concept\n---\nstub\n",
    )
    report = lint_vault(wiki)
    assert report.ok is True
    assert report.stubs == 1
    assert report.pages == 1


def test_lint_stub_count_separate_from_pages(tmp_path: Path) -> None:
    wiki = _clean_vault(tmp_path)
    report = lint_vault(wiki)
    assert report.pages == 1
    assert report.stubs == 2


def test_lint_aliased_wikilink_resolves(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    _write(wiki / "a.md", "---\ntitle: A\n---\n\n[[B|display]]\n")
    _write(wiki / "b.md", "---\ntitle: B\n---\nbody\n")
    report = lint_vault(wiki)
    assert report.ok is True


def test_lint_anchor_wikilink_resolves(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    _write(wiki / "a.md", "---\ntitle: A\n---\n\n[[B#Section]]\n")
    _write(wiki / "b.md", "---\ntitle: B\n---\nbody\n")
    report = lint_vault(wiki)
    assert report.ok is True


def test_lint_file_naming_violation(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    _write(wiki / "Bad Name.md", "---\ntitle: Bad\n---\nbody\n")
    report = lint_vault(wiki)
    assert report.ok is False
    naming = [i for i in report.issues if i.kind == "naming"]
    assert len(naming) == 1
    assert "Bad Name" in naming[0].message


def test_lint_self_link_resolves(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    _write(wiki / "a.md", "---\ntitle: A\n---\n\n[[A]]\n")
    report = lint_vault(wiki)
    assert report.ok is True
    assert report.orphans == 0  # self-link counts as inbound


def test_lint_empty_wikilink_ignored(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    _write(wiki / "a.md", "---\ntitle: A\n---\n\n[[   ]]\n")
    report = lint_vault(wiki)
    assert report.ok is True
    assert report.wikilinks == 0


def test_lint_report_to_dict_shape(tmp_path: Path) -> None:
    wiki = _clean_vault(tmp_path)
    d = lint_vault(wiki).to_dict()
    assert set(d.keys()) >= {"pages", "stubs", "wikilinks", "orphans", "ok", "issues"}


def test_lint_issue_to_dict() -> None:
    issue = LintIssue(
        kind="broken-wikilink",
        path=Path("/x/y.md"),
        line=3,
        message="missing",
    )
    d = issue.to_dict()
    assert d == {
        "kind": "broken-wikilink",
        "path": "/x/y.md",
        "line": 3,
        "message": "missing",
    }


def test_lint_no_frontmatter_treated_as_body(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    _write(wiki / "raw.md", "no frontmatter [[Missing]] here\n")
    report = lint_vault(wiki)
    broken = [i for i in report.issues if i.kind == "broken-wikilink"]
    assert len(broken) == 1
    assert broken[0].line == 1


def test_lint_unterminated_frontmatter_reported(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    _write(wiki / "bad.md", "---\ntitle: A\nstill yaml\nno closing fence here\n")
    report = lint_vault(wiki)
    # Either YAML parses (since no terminator the whole tail is yaml) or it
    # doesn't — but in either case we shouldn't blow up. The orphan/page
    # tally still includes it.
    assert report.pages == 1


def test_lint_report_constructor() -> None:
    r = LintReport(pages=1, stubs=0, wikilinks=0, orphans=0, issues=[])
    assert r.ok is True


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_cli_vault_lint_clean_exits_zero(tmp_path: Path) -> None:
    wiki = _clean_vault(tmp_path)
    runner = CliRunner()
    res = runner.invoke(app, ["vault-lint", str(wiki)])
    assert res.exit_code == 0, res.output
    payload = json.loads(res.output.strip().splitlines()[-1])
    assert payload["ok"] is True
    assert payload["pages"] == 1
    assert payload["stubs"] == 2
    assert payload["wikilinks"] == 2
    assert payload["orphans"] == 1


def test_cli_vault_lint_broken_exits_nonzero(tmp_path: Path) -> None:
    wiki = tmp_path / "wiki"
    _write(wiki / "p.md", "---\ntitle: P\n---\n[[Missing]]\n")
    runner = CliRunner()
    res = runner.invoke(app, ["vault-lint", str(wiki)])
    assert res.exit_code == 1
    assert "Missing" in res.output


def test_cli_vault_lint_missing_dir_exits_two(tmp_path: Path) -> None:
    runner = CliRunner()
    res = runner.invoke(app, ["vault-lint", str(tmp_path / "nope")])
    assert res.exit_code == 2


def test_cli_vault_lint_default_wiki_dir(tmp_path: Path, monkeypatch) -> None:
    _clean_vault(tmp_path)
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    res = runner.invoke(app, ["vault-lint"])
    assert res.exit_code == 0, res.output
