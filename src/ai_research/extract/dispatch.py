"""Unified extract dispatcher (Story 01.2-004).

Routes a single ``input`` string — a local filesystem path or an
``http(s)://`` URL — to the correct adapter (pdf / markdown / url) and
returns a canonical ``{text, metadata}`` record.

Slash commands and the CLI both call :func:`extract` so routing lives in
exactly one place. Keeping the registry here (rather than inside
``__init__.py``) avoids import-time side effects and keeps the package
entry point small.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ai_research.extract.markdown import SUPPORTED_SUFFIXES, extract_markdown
from ai_research.extract.pdf import extract_pdf
from ai_research.extract.url import extract_url

_URL_SCHEMES: tuple[str, ...] = ("http://", "https://")
_PDF_SUFFIX = ".pdf"


class UnsupportedSourceError(ValueError):
    """Raised when the dispatcher cannot map an input to an adapter."""


def extract(input: str) -> dict[str, Any]:  # noqa: A002 — public API name
    """Dispatch ``input`` to the correct extract adapter.

    Routing rules:

    * ``http://`` / ``https://`` → :func:`extract_url`
    * ``*.pdf``                  → :func:`extract_pdf`
    * ``*.md`` / ``*.markdown`` / ``*.txt`` → :func:`extract_markdown`
    * anything else              → :class:`UnsupportedSourceError`

    The returned dict is the adapter's native ``{text, metadata}`` record
    (typed as :class:`ExtractResult` by each adapter).
    """
    if input.startswith(_URL_SCHEMES):
        return extract_url(input)

    path = Path(input)
    suffix = path.suffix.lower()

    if suffix == _PDF_SUFFIX:
        return extract_pdf(path)
    if suffix in SUPPORTED_SUFFIXES:
        return extract_markdown(path)

    supported = ", ".join(sorted({_PDF_SUFFIX, *SUPPORTED_SUFFIXES}))
    raise UnsupportedSourceError(
        f"Unsupported source type {suffix!r}. Supported: {supported}, plus http(s):// URLs."
    )
