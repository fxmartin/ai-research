"""Wiki materialization and indexing helpers."""

from ai_research.wiki.index_rebuild import IndexEntry, rebuild_index
from ai_research.wiki.materialize import MaterializeResult, materialize
from ai_research.wiki.stubs import create_stub, create_stubs_for_body, extract_wikilinks

__all__ = [
    "IndexEntry",
    "MaterializeResult",
    "create_stub",
    "create_stubs_for_body",
    "extract_wikilinks",
    "materialize",
    "rebuild_index",
]
