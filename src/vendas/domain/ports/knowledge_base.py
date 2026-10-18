from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol


class KnowledgeBasePort(Protocol):
    def preview(self, text: str, at: datetime | None = None) -> dict[str, Any]:
        ...

    def find_services(self, text: str | None = None, at: datetime | None = None) -> list[dict[str, Any]]:
        ...

    def list_services(self) -> list[dict[str, Any]]:
        ...

    def find_prices(self, service_id: str, at: datetime | None = None) -> list[dict[str, Any]]:
        ...