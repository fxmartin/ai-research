"""URL extraction via `trafilatura`.

Fetches a remote document and returns a structured ``{text, metadata}``
payload. When the URL serves a PDF (per Content-Type sniff), we delegate
to the PDF extractor so callers see a single, uniform interface.

Hash semantics: for HTML sources, ``metadata.sha256`` is computed over
the *extracted markdown* text (per story spec). For PDF URLs, the PDF
extractor's hash (raw bytes) is preserved.

The network fetch is isolated behind a private ``_fetch`` helper so
tests can mock it deterministically without depending on trafilatura's
internal download API.
"""

from __future__ import annotations

import hashlib
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import trafilatura

from ai_research.extract.pdf import extract_pdf


class UrlExtractionError(RuntimeError):
    """Raised when a URL cannot be fetched or its content cannot be extracted."""


class _Resp:
    """Minimal response adapter that exposes ``content`` (bytes) and ``headers`` (dict).

    Used by ``_fetch`` to normalise the varying shapes returned by different
    trafilatura download APIs so the rest of the module sees a stable interface.
    """

    content: bytes
    headers: dict[str, str]


def _fetch(url: str) -> Any:
    """Download a URL and return a response-like object or None on failure.

    Uses trafilatura's downloader when available (it handles compression,
    encoding, and common failure modes). We wrap it in a tiny adapter so
    the call site and tests see a stable shape: an object exposing
    ``content`` (bytes) and ``headers`` (mapping).
    """
    try:
        # trafilatura >= 2.0 exposes fetch_response which returns a
        # urllib3-like response with .data and .headers.
        from trafilatura.downloads import fetch_response  # type: ignore[attr-defined]
    except ImportError:  # pragma: no cover — older trafilatura
        fetch_response = None

    if fetch_response is not None:
        try:
            resp = fetch_response(url, with_headers=True)
        except Exception:  # pragma: no cover — network defensive
            return None
        if resp is None:
            return None
        # Normalize to our shape
        content = getattr(resp, "data", None) or getattr(resp, "content", None) or b""
        headers = dict(getattr(resp, "headers", {}) or {})

        r = _Resp()
        r.content = content  # type: ignore[attr-defined]
        r.headers = headers  # type: ignore[attr-defined]
        return r

    # Fallback path: fetch_url returns raw HTML string only (no headers).
    html = trafilatura.fetch_url(url)
    if html is None:
        return None

    r = _Resp()
    r.content = html.encode("utf-8") if isinstance(html, str) else html  # type: ignore[attr-defined]
    r.headers = {"Content-Type": "text/html"}  # type: ignore[attr-defined]
    return r


def _is_pdf_response(resp: Any, url: str) -> bool:
    """MIME-sniff: treat as PDF if Content-Type says so or bytes start with %PDF."""
    headers = getattr(resp, "headers", {}) or {}
    ctype = ""
    for k, v in headers.items():
        if str(k).lower() == "content-type":
            ctype = str(v).lower()
            break
    if "application/pdf" in ctype:
        return True
    content = getattr(resp, "content", b"") or b""
    return content[:5] == b"%PDF-"


def extract_url(url: str) -> dict[str, Any]:
    """Fetch a URL and return ``{text, metadata}``.

    Args:
        url: An HTTP(S) URL.

    Returns:
        ``{"text": str, "metadata": {...}}``. For HTML sources,
        ``metadata`` includes ``url``, ``title``, ``fetched_at``,
        ``source_type="url"``, ``sha256`` (of extracted markdown).
        For PDF URLs, returns the PDF extractor payload with ``url``
        mixed into metadata.

    Raises:
        UrlExtractionError: The URL could not be fetched or no content
            could be extracted.
    """
    resp = _fetch(url)
    if resp is None:
        raise UrlExtractionError(f"Failed to fetch URL: {url}")

    fetched_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    # PDF delegation: download to a tmp file and reuse the PDF adapter.
    if _is_pdf_response(resp, url):
        content = getattr(resp, "content", b"") or b""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as fh:
            fh.write(content)
            tmp_path = Path(fh.name)
        try:
            result = extract_pdf(tmp_path)
        finally:
            try:
                tmp_path.unlink()
            except OSError:  # pragma: no cover — defensive
                pass
        # Enrich with URL context while preserving PDF metadata (incl. hash).
        result["metadata"]["url"] = url
        result["metadata"]["fetched_at"] = fetched_at
        return result

    # HTML path via trafilatura → markdown.
    html_bytes = getattr(resp, "content", b"") or b""
    html_str = (
        html_bytes.decode("utf-8", errors="replace")
        if isinstance(html_bytes, bytes)
        else str(html_bytes)
    )

    text = trafilatura.extract(
        html_str,
        output_format="markdown",
        include_links=True,
        include_formatting=True,
        with_metadata=False,
    )
    if not text or not text.strip():
        raise UrlExtractionError(f"No content extracted from URL: {url}")

    # Title extraction — cheap and best-effort.
    title: str | None = None
    try:
        meta = trafilatura.extract_metadata(html_str)
        if meta is not None:
            title = getattr(meta, "title", None)
    except Exception:  # pragma: no cover — defensive
        title = None

    sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()

    return {
        "text": text,
        "metadata": {
            "source_type": "url",
            "url": url,
            "title": title,
            "fetched_at": fetched_at,
            "sha256": sha256,
        },
    }
