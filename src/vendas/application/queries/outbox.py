from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from vendas.domain.ports.outbox import OutboxQueryPort


class ListOutboxQueueQuery:
    def __init__(self, query_port: OutboxQueryPort) -> None:
        self._query_port = query_port

    def execute(
        self,
        *,
        status: Sequence[str] | None = None,
        channel: Sequence[str] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        return self._query_port.list_outbox(
            status=status,
            channel=channel,
            limit=limit,
            offset=offset,
        )


class CountOutboxByStatusQuery:
    def __init__(self, query_port: OutboxQueryPort) -> None:
        self._query_port = query_port

    def execute(self) -> dict[str, int]:
        return self._query_port.count_by_status()
