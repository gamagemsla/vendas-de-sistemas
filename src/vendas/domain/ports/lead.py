from collections.abc import Sequence
from typing import Any, Protocol


class LeadQueryPort(Protocol):
    def list_leads(
        self,
        *,
        search: str | None = None,
        status: Sequence[str] | None = None,
        grade: Sequence[str] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]: ...

    def count_by_status(self) -> dict[str, int]: ...
