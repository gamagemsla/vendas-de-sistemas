from __future__ import annotations

from datetime import datetime
from typing import Any

from vendas.domain.ports.knowledge_base import KnowledgeBasePort


class CatalogPreviewQuery:
    def __init__(self, knowledge_base: KnowledgeBasePort) -> None:
        self._knowledge_base = knowledge_base

    def execute(self, text: str, at: datetime | None = None) -> dict[str, Any]:
        return self._knowledge_base.preview(text, at=at)


class ListCatalogServicesQuery:
    def __init__(self, knowledge_base: KnowledgeBasePort) -> None:
        self._knowledge_base = knowledge_base

    def execute(self, text: str | None = None, at: datetime | None = None) -> list[dict[str, Any]]:
        return self._knowledge_base.find_services(text=text, at=at)