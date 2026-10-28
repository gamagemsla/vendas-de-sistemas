from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from vendas.domain.ports.lead import LeadQueryPort


class ListLeadsQuery:
    def __init__(self, query_port: LeadQueryPort) -> None:
        self._query_port = query_port

    def execute(
        self,
        *,
        search: str | None = None,
        status: Sequence[str] | None = None,
        grade: Sequence[str] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        return self._query_port.list_leads(
            search=search,
            status=status,
            grade=grade,
            limit=limit,
            offset=offset,
        )


class CountLeadsByStatusQuery:
    def __init__(self, query_port: LeadQueryPort) -> None:
        self._query_port = query_port

    def execute(self) -> dict[str, int]:
        return self._query_port.count_by_status()
