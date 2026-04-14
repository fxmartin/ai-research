"""Extract adapters: turn source artifacts into `{text, metadata}` records.

Each adapter module exposes a pure function returning a dict with the
``text`` payload and a ``metadata`` dict. The unified dispatcher (Story
01.2-004) will compose these; for now only the markdown adapter is wired.
"""

from __future__ import annotations

from ai_research.extract.markdown import extract_markdown

__all__ = ["extract_markdown"]
