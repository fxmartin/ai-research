"""Tests for the URL extractor (Story 01.2-002).

Network is mocked — no live HTTP is performed.
"""

from __future__ import annotations

import hashlib
import json
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from ai_research.cli import app
from ai_research.extract.url import (
    UrlExtractionError,
    extract_url,
)

runner = CliRunner()

SAMPLE_HTML = b"""<!doctype html>
<html><head><title>Sample Article</title></head>
<body>
  <nav>nav junk</nav>
  <article>
    <h1>Sample Article</h1>
    <p>HELLO_AI_RESEARCH_URL_MARKER this is the main content.</p>
    <p>Second paragraph with more text to satisfy trafilatura heuristics.</p>
  </article>
  <footer>footer junk</footer>
</body></html>
"""


class _FakeResponse:
    def __init__(self, content: bytes, headers: dict[str, str] | None = None, status: int = 200):
        self.content = content
        self.data = content
        self.headers = headers or {"Content-Type": "text/html; charset=utf-8"}
        self.status = status
        self.status_code = status
        self.url = "https://example.com/article"

    def read(self) -> bytes:
        return self.content


def _patch_fetch(response: _FakeResponse | None):
    """Patch the fetcher used inside extract_url.

    We patch our own internal `_fetch` helper so tests don't depend on
    trafilatura's exact download API (which has shifted across versions).
    """
    return patch("ai_research.extract.url._fetch", return_value=response)


def test_extract_url_returns_text_and_metadata() -> None:
    resp = _FakeResponse(SAMPLE_HTML)
    with _patch_fetch(resp):
        result = extract_url("https://example.com/article")

    assert "text" in result
    assert "metadata" in result
    assert "HELLO_AI_RESEARCH_URL_MARKER" in result["text"]

    meta = result["metadata"]
    assert meta["source_type"] == "url"
    assert meta["url"] == "https://example.com/article"
    assert "fetched_at" in meta and meta["fetched_at"].endswith("Z") or "T" in meta["fetched_at"]
    assert meta["title"] == "Sample Article" or "Sample" in (meta["title"] or "")
    # sha256 is of extracted markdown (text), per spec
    expected = hashlib.sha256(result["text"].encode("utf-8")).hexdigest()
    assert meta["sha256"] == expected
    assert len(meta["sha256"]) == 64


def test_extract_url_fetch_failure_raises() -> None:
    with _patch_fetch(None):
        with pytest.raises(UrlExtractionError):
            extract_url("https://example.com/does-not-exist")


def test_extract_url_empty_extraction_raises() -> None:
    """If trafilatura can't extract any content, we surface an error."""
    resp = _FakeResponse(b"<html><body></body></html>")
    with _patch_fetch(resp):
        with pytest.raises(UrlExtractionError):
            extract_url("https://example.com/empty")


def test_extract_url_pdf_content_type_delegates_to_pdf(tmp_path, monkeypatch) -> None:
    """A URL serving a PDF MIME type must delegate to the PDF extractor."""
    pdf_bytes = b"%PDF-1.4\nfake"
    resp = _FakeResponse(pdf_bytes, headers={"Content-Type": "application/pdf"})

    captured = {}

    def fake_extract_pdf(path):
        captured["path"] = path
        return {
            "text": "PDF_DELEGATED_MARKER",
            "metadata": {
                "source_type": "pdf",
                "pages": 1,
                "sha256": hashlib.sha256(pdf_bytes).hexdigest(),
                "path": str(path),
            },
        }

    monkeypatch.setattr("ai_research.extract.url.extract_pdf", fake_extract_pdf)
    with _patch_fetch(resp):
        result = extract_url("https://example.com/paper.pdf")

    assert "PDF_DELEGATED_MARKER" in result["text"]
    # Metadata is enriched with URL context even for delegated PDFs.
    assert result["metadata"]["url"] == "https://example.com/paper.pdf"
    assert result["metadata"]["source_type"] == "pdf"
    assert "path" in captured


def test_cli_extract_url_emits_json() -> None:
    resp = _FakeResponse(SAMPLE_HTML)
    with _patch_fetch(resp):
        result = runner.invoke(app, ["extract", "https://example.com/article"])
    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert "HELLO_AI_RESEARCH_URL_MARKER" in payload["text"]
    assert payload["metadata"]["source_type"] == "url"
    assert payload["metadata"]["url"] == "https://example.com/article"


def test_cli_extract_url_fetch_failure_nonzero() -> None:
    with _patch_fetch(None):
        result = runner.invoke(app, ["extract", "https://example.com/nope"])
    assert result.exit_code != 0
