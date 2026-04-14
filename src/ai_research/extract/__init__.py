"""Extract adapters: turn source artifacts into `{text, metadata}` records.

Each adapter module exposes a pure function returning a dict with the
``text`` payload and a ``metadata`` dict. The unified dispatcher
(:func:`extract`, Story 01.2-004) composes these and routes by URL scheme
or file extension.
"""

from __future__ import annotations

from ai_research.extract.dispatch import UnsupportedSourceError, extract
from ai_research.extract.markdown import extract_markdown
from ai_research.extract.pdf import (
    PdfExtractionError,
    PdftotextNotFoundError,
    extract_pdf,
)
from ai_research.extract.url import UrlExtractionError, extract_url

__all__ = [
    "extract",
    "extract_markdown",
    "extract_pdf",
    "extract_url",
    "PdfExtractionError",
    "PdftotextNotFoundError",
    "UnsupportedSourceError",
    "UrlExtractionError",
]
