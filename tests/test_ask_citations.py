"""Tests for /ask citation integrity check (Story 03.3-002)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ai_research.cli import app
from ai_research.wiki.ask import (
    AskPayloadError,
    CitationCheckResult,
    check_citations,
    normalize_citation,
)

runner = CliRunner()


def _make_vault(tmp_path: Path) -> Path:
    wiki = tmp_path / "wiki"
    (wiki / "concepts").mkdir(parents=True)
    (wiki / "attention.md").write_text("# Attention\n", encoding="utf-8")
    (wiki / "concepts" / "transformer.md").write_text("# Transformer\n", encoding="utf-8")
    return wiki


# ---------------------------------------------------------------------------
# normalize_citation
# ---------------------------------------------------------------------------


def test_normalize_strips_wikilink_brackets() -> None:
    assert normalize_citation("[[Attention]]") == "Attention"


def test_normalize_strips_alias_and_anchor() -> None:
    assert normalize_citation("[[Attention#Heading|alias]]") == "Attention"


def test_normalize_passes_through_plain_name() -> None:
    assert normalize_citation("attention") == "attention"


def test_normalize_rejects_empty() -> None:
    with pytest.raises(AskPayloadError):
        normalize_citation("[[]]")


# ---------------------------------------------------------------------------
# check_citations
# ---------------------------------------------------------------------------


def test_all_valid_citations(tmp_path: Path) -> None:
    wiki = _make_vault(tmp_path)
    result = check_citations(
        {"answer": "x", "citations": ["[[Attention]]", "Transformer"], "confidence": 0.9},
        wiki_dir=wiki,
    )
    assert isinstance(result, CitationCheckResult)
    assert result.ok is True
    assert result.broken == []
    assert set(result.resolved) == {"Attention", "Transformer"}


def test_missing_page_is_broken(tmp_path: Path) -> None:
    wiki = _make_vault(tmp_path)
    result = check_citations(
        {"answer": "x", "citations": ["Attention", "Ghost"], "confidence": 0.5},
        wiki_dir=wiki,
    )
    assert result.ok is False
    assert result.broken == ["Ghost"]


def test_empty_citations_list_is_ok(tmp_path: Path) -> None:
    wiki = _make_vault(tmp_path)
    result = check_citations(
        {"answer": "", "citations": [], "confidence": 0.0},
        wiki_dir=wiki,
    )
    assert result.ok is True
    assert result.broken == []
    assert result.resolved == []


def test_wikilink_with_alias_and_anchor_resolves(tmp_path: Path) -> None:
    wiki = _make_vault(tmp_path)
    result = check_citations(
        {
            "answer": "see [[Attention#Scaled|attn]]",
            "citations": ["[[Attention#Scaled|attn]]", "[[Transformer|T]]"],
            "confidence": 0.7,
        },
        wiki_dir=wiki,
    )
    assert result.ok is True


def test_citation_resolves_via_slug(tmp_path: Path) -> None:
    # "Self Attention" slugifies to "self-attention"; the page exists at that slug.
    wiki = _make_vault(tmp_path)
    (wiki / "self-attention.md").write_text("# Self Attention\n", encoding="utf-8")
    result = check_citations(
        {"answer": "x", "citations": ["Self Attention"], "confidence": 0.5},
        wiki_dir=wiki,
    )
    assert result.ok is True


def test_rejects_non_dict_payload(tmp_path: Path) -> None:
    wiki = _make_vault(tmp_path)
    with pytest.raises(AskPayloadError):
        check_citations([], wiki_dir=wiki)  # type: ignore[arg-type]


def test_rejects_missing_citations_key(tmp_path: Path) -> None:
    wiki = _make_vault(tmp_path)
    with pytest.raises(AskPayloadError):
        check_citations({"answer": "x", "confidence": 0.1}, wiki_dir=wiki)


def test_rejects_non_list_citations(tmp_path: Path) -> None:
    wiki = _make_vault(tmp_path)
    with pytest.raises(AskPayloadError):
        check_citations(
            {"answer": "x", "citations": "Attention", "confidence": 0.1},
            wiki_dir=wiki,
        )


def test_rejects_non_string_citation_entry(tmp_path: Path) -> None:
    wiki = _make_vault(tmp_path)
    with pytest.raises(AskPayloadError):
        check_citations(
            {"answer": "x", "citations": [42], "confidence": 0.1},
            wiki_dir=wiki,
        )


def test_missing_wiki_dir_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        check_citations(
            {"answer": "x", "citations": ["Attention"], "confidence": 0.1},
            wiki_dir=tmp_path / "nope",
        )


# ---------------------------------------------------------------------------
# CLI: ai-research ask-check
# ---------------------------------------------------------------------------


def test_cli_ask_check_file_success(tmp_path: Path) -> None:
    wiki = _make_vault(tmp_path)
    payload = tmp_path / "answer.json"
    payload.write_text(
        json.dumps(
            {"answer": "x", "citations": ["[[Attention]]", "Transformer"], "confidence": 0.9}
        ),
        encoding="utf-8",
    )
    result = runner.invoke(app, ["ask-check", "--json", str(payload), "--wiki-dir", str(wiki)])
    assert result.exit_code == 0, result.output
    out = json.loads(result.stdout)
    assert out["ok"] is True
    assert out["broken"] == []


def test_cli_ask_check_file_broken(tmp_path: Path) -> None:
    wiki = _make_vault(tmp_path)
    payload = tmp_path / "answer.json"
    payload.write_text(
        json.dumps({"answer": "x", "citations": ["Ghost"], "confidence": 0.1}),
        encoding="utf-8",
    )
    result = runner.invoke(app, ["ask-check", "--json", str(payload), "--wiki-dir", str(wiki)])
    assert result.exit_code == 1
    out = json.loads(result.stdout)
    assert out["ok"] is False
    assert out["broken"] == ["Ghost"]


def test_cli_ask_check_stdin(tmp_path: Path) -> None:
    wiki = _make_vault(tmp_path)
    payload = json.dumps({"answer": "x", "citations": ["Attention"], "confidence": 0.9})
    result = runner.invoke(app, ["ask-check", "--stdin", "--wiki-dir", str(wiki)], input=payload)
    assert result.exit_code == 0, result.output
    out = json.loads(result.stdout)
    assert out["ok"] is True


def test_cli_ask_check_requires_input(tmp_path: Path) -> None:
    wiki = _make_vault(tmp_path)
    result = runner.invoke(app, ["ask-check", "--wiki-dir", str(wiki)])
    assert result.exit_code == 2


def test_cli_ask_check_invalid_json(tmp_path: Path) -> None:
    wiki = _make_vault(tmp_path)
    payload = tmp_path / "bad.json"
    payload.write_text("not-json", encoding="utf-8")
    result = runner.invoke(app, ["ask-check", "--json", str(payload), "--wiki-dir", str(wiki)])
    assert result.exit_code == 2


def test_cli_ask_check_payload_schema_error(tmp_path: Path) -> None:
    wiki = _make_vault(tmp_path)
    payload = tmp_path / "answer.json"
    payload.write_text(json.dumps({"answer": "x"}), encoding="utf-8")
    result = runner.invoke(app, ["ask-check", "--json", str(payload), "--wiki-dir", str(wiki)])
    assert result.exit_code == 2


def test_cli_ask_check_missing_wiki_dir(tmp_path: Path) -> None:
    payload = tmp_path / "answer.json"
    payload.write_text(
        json.dumps({"answer": "x", "citations": [], "confidence": 0.0}),
        encoding="utf-8",
    )
    result = runner.invoke(
        app,
        ["ask-check", "--json", str(payload), "--wiki-dir", str(tmp_path / "nope")],
    )
    assert result.exit_code == 2
