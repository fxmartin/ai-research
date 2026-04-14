"""Tests for the unified extract dispatcher (Story 01.2-004)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from ai_research.extract import extract
from ai_research.extract.markdown import SUPPORTED_SUFFIXES


def test_dispatch_pdf_routes_to_pdf_adapter(tmp_path: Path) -> None:
    """Inputs with .pdf suffix must be dispatched to extract_pdf."""
    fake = {"text": "pdf-text", "metadata": {"source_type": "pdf"}}
    src = tmp_path / "paper.pdf"
    src.write_bytes(b"%PDF-1.4 fake")
    with patch("ai_research.extract.dispatch.extract_pdf", return_value=fake) as mock:
        result = extract(str(src))
    mock.assert_called_once_with(src)
    assert result is fake


def test_dispatch_http_url_routes_to_url_adapter() -> None:
    """http:// URLs must be dispatched to extract_url."""
    fake = {"text": "url-text", "metadata": {"source_type": "url"}}
    with patch("ai_research.extract.dispatch.extract_url", return_value=fake) as mock:
        result = extract("http://example.com/article")
    mock.assert_called_once_with("http://example.com/article")
    assert result is fake


def test_dispatch_https_url_routes_to_url_adapter() -> None:
    """https:// URLs must be dispatched to extract_url."""
    fake = {"text": "url-text", "metadata": {"source_type": "url"}}
    with patch("ai_research.extract.dispatch.extract_url", return_value=fake) as mock:
        result = extract("https://example.com/article")
    mock.assert_called_once_with("https://example.com/article")
    assert result is fake


@pytest.mark.parametrize("suffix", sorted(SUPPORTED_SUFFIXES))
def test_dispatch_markdown_suffixes_route_to_markdown(tmp_path: Path, suffix: str) -> None:
    """Each markdown/text suffix must be dispatched to extract_markdown."""
    fake = {"text": "md-text", "metadata": {"source_type": "markdown"}}
    src = tmp_path / f"note{suffix}"
    src.write_text("hello")
    with patch("ai_research.extract.dispatch.extract_markdown", return_value=fake) as mock:
        result = extract(str(src))
    mock.assert_called_once_with(src)
    assert result is fake


def test_dispatch_uppercase_suffix_is_normalized(tmp_path: Path) -> None:
    """Suffix matching must be case-insensitive."""
    fake = {"text": "pdf-text", "metadata": {"source_type": "pdf"}}
    src = tmp_path / "paper.PDF"
    src.write_bytes(b"%PDF-1.4 fake")
    with patch("ai_research.extract.dispatch.extract_pdf", return_value=fake):
        result = extract(str(src))
    assert result is fake


def test_dispatch_unknown_suffix_raises_unsupported(tmp_path: Path) -> None:
    """An unknown suffix must raise UnsupportedSourceError listing supported types."""
    from ai_research.extract import UnsupportedSourceError

    src = tmp_path / "data.xyz"
    src.write_text("nope")
    with pytest.raises(UnsupportedSourceError) as excinfo:
        extract(str(src))
    msg = str(excinfo.value)
    assert ".xyz" in msg
    assert ".pdf" in msg
    assert ".md" in msg


def test_dispatch_no_suffix_raises_unsupported(tmp_path: Path) -> None:
    """A path without any suffix must raise UnsupportedSourceError."""
    from ai_research.extract import UnsupportedSourceError

    src = tmp_path / "README"
    src.write_text("nope")
    with pytest.raises(UnsupportedSourceError):
        extract(str(src))
