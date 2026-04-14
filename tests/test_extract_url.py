"""Tests for the URL extractor (Story 01.2-002).

Network is mocked — no live HTTP is performed.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from ai_research.cli import app
from ai_research.extract.url import (
    UrlExtractionError,
    _fetch,
    _is_pdf_response,
    _Resp,
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


# ---------------------------------------------------------------------------
# extract_url — happy path and error paths
# ---------------------------------------------------------------------------


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


def test_extract_url_fetched_at_format() -> None:
    """fetched_at must be an ISO-8601 string ending with 'Z' (UTC)."""
    resp = _FakeResponse(SAMPLE_HTML)
    before = datetime.now(UTC)
    with _patch_fetch(resp):
        result = extract_url("https://example.com/article")
    after = datetime.now(UTC)

    fetched_at = result["metadata"]["fetched_at"]
    # Must end with Z (the UTC marker we substitute for +00:00)
    assert fetched_at.endswith("Z"), f"expected Z suffix, got: {fetched_at}"
    # Must be parseable as a UTC datetime
    parsed = datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
    assert before <= parsed <= after


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


def test_extract_url_title_none_when_metadata_missing() -> None:
    """extract_url sets title=None when trafilatura returns no metadata."""
    resp = _FakeResponse(SAMPLE_HTML)
    with _patch_fetch(resp):
        with patch("trafilatura.extract_metadata", return_value=None):
            result = extract_url("https://example.com/article")
    assert result["metadata"]["title"] is None


def test_extract_url_title_none_when_meta_has_no_title() -> None:
    """extract_url tolerates a metadata object that has no title attribute."""
    resp = _FakeResponse(SAMPLE_HTML)
    fake_meta = SimpleNamespace()  # no title attribute
    with _patch_fetch(resp):
        with patch("trafilatura.extract_metadata", return_value=fake_meta):
            result = extract_url("https://example.com/article")
    assert result["metadata"]["title"] is None


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


def test_extract_url_pdf_magic_bytes_delegates_to_pdf(monkeypatch) -> None:
    """A URL with PDF magic bytes (%PDF-) but no PDF content-type still delegates."""
    pdf_bytes = b"%PDF-1.5\nother content"
    # Content-Type is text/html but body starts with %PDF-
    resp = _FakeResponse(pdf_bytes, headers={"Content-Type": "text/html"})

    def fake_extract_pdf(path):
        return {
            "text": "PDF_MAGIC_MARKER",
            "metadata": {"source_type": "pdf", "pages": 1, "sha256": "abc", "path": str(path)},
        }

    monkeypatch.setattr("ai_research.extract.url.extract_pdf", fake_extract_pdf)
    with _patch_fetch(resp):
        result = extract_url("https://example.com/doc")

    assert "PDF_MAGIC_MARKER" in result["text"]
    assert result["metadata"]["fetched_at"].endswith("Z")


# ---------------------------------------------------------------------------
# _is_pdf_response — unit tests for the MIME-sniff helper
# ---------------------------------------------------------------------------


def test_is_pdf_response_content_type_match() -> None:
    resp = _FakeResponse(b"not-pdf-bytes", headers={"Content-Type": "application/pdf"})
    assert _is_pdf_response(resp, "https://example.com/x") is True


def test_is_pdf_response_magic_bytes() -> None:
    resp = _FakeResponse(b"%PDF-1.4 data", headers={"Content-Type": "text/html"})
    assert _is_pdf_response(resp, "https://example.com/x") is True


def test_is_pdf_response_false_for_html() -> None:
    resp = _FakeResponse(b"<html></html>", headers={"Content-Type": "text/html"})
    assert _is_pdf_response(resp, "https://example.com/x") is False


def test_is_pdf_response_empty_content() -> None:
    resp = _FakeResponse(b"", headers={"Content-Type": "text/html"})
    assert _is_pdf_response(resp, "https://example.com/x") is False


def test_is_pdf_response_case_insensitive_content_type() -> None:
    """Content-Type header key matching must be case-insensitive."""
    resp = _FakeResponse(b"data", headers={"CONTENT-TYPE": "application/pdf"})
    assert _is_pdf_response(resp, "https://example.com/x") is True


def test_is_pdf_response_no_headers() -> None:
    """If headers are missing entirely, fall back to magic bytes check."""
    r = _Resp()
    r.content = b"<html></html>"  # type: ignore[attr-defined]
    r.headers = {}  # type: ignore[attr-defined]
    assert _is_pdf_response(r, "https://example.com/x") is False


def test_is_pdf_response_skips_non_content_type_headers() -> None:
    """_is_pdf_response iterates all headers; non-Content-Type keys are skipped."""
    # First header is not content-type — exercises the loop-continue branch.
    headers = {"X-Request-Id": "abc123", "Content-Type": "application/pdf"}
    resp = _FakeResponse(b"data", headers=headers)
    assert _is_pdf_response(resp, "https://example.com/x") is True


# ---------------------------------------------------------------------------
# _fetch — unit tests exercising the trafilatura download adapters
# ---------------------------------------------------------------------------


def test_fetch_uses_fetch_response_when_available() -> None:
    """_fetch uses trafilatura.downloads.fetch_response (>= 2.0 path)."""
    fake_raw = MagicMock()
    fake_raw.data = SAMPLE_HTML
    fake_raw.headers = {"Content-Type": "text/html"}

    with patch("trafilatura.downloads.fetch_response", return_value=fake_raw):
        result = _fetch("https://example.com/article")

    assert result is not None
    assert result.content == SAMPLE_HTML
    assert result.headers["Content-Type"] == "text/html"


def test_fetch_returns_none_when_fetch_response_returns_none() -> None:
    """_fetch propagates a None from fetch_response as a None."""
    with patch("trafilatura.downloads.fetch_response", return_value=None):
        result = _fetch("https://example.com/gone")
    assert result is None


def test_fetch_normalises_resp_using_content_attr_fallback() -> None:
    """_fetch falls back to .content if .data is absent/falsy on the raw response."""
    fake_raw = MagicMock()
    fake_raw.data = b""  # falsy — should fall through to .content
    fake_raw.content = SAMPLE_HTML
    fake_raw.headers = {"Content-Type": "text/html"}

    with patch("trafilatura.downloads.fetch_response", return_value=fake_raw):
        result = _fetch("https://example.com/article")

    assert result is not None
    assert result.content == SAMPLE_HTML


def test_fetch_fallback_when_fetch_response_unavailable() -> None:
    """_fetch uses trafilatura.fetch_url when fetch_response import fails."""
    html_str = SAMPLE_HTML.decode("utf-8")

    # Direct approach: test the fallback by patching the import inside _fetch.
    with patch.dict("sys.modules", {"trafilatura.downloads": None}):
        with patch("trafilatura.fetch_url", return_value=html_str):
            result = _fetch("https://example.com/article")

    assert result is not None
    assert result.content == SAMPLE_HTML


def test_fetch_fallback_returns_none_when_fetch_url_returns_none() -> None:
    """_fetch fallback returns None when trafilatura.fetch_url returns None."""
    with patch.dict("sys.modules", {"trafilatura.downloads": None}):
        with patch("trafilatura.fetch_url", return_value=None):
            result = _fetch("https://example.com/gone")
    assert result is None


def test_fetch_fallback_handles_bytes_content() -> None:
    """_fetch fallback handles fetch_url returning bytes instead of str."""
    with patch.dict("sys.modules", {"trafilatura.downloads": None}):
        with patch("trafilatura.fetch_url", return_value=SAMPLE_HTML):
            result = _fetch("https://example.com/article")
    assert result is not None
    # bytes input should be passed through unchanged
    assert result.content == SAMPLE_HTML


# ---------------------------------------------------------------------------
# _Resp — module-level class exists with expected interface
# ---------------------------------------------------------------------------


def test_resp_class_is_module_level() -> None:
    """_Resp is defined once at module level — no duplicate inner-class definitions."""
    from ai_research.extract import url as url_module

    assert hasattr(url_module, "_Resp"), "_Resp must be a module-level class"
    # Instantiate and assign attributes as _fetch does
    r = _Resp()
    r.content = b"hello"  # type: ignore[attr-defined]
    r.headers = {"X-Test": "1"}  # type: ignore[attr-defined]
    assert r.content == b"hello"
    assert r.headers["X-Test"] == "1"


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------


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
