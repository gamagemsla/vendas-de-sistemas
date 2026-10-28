from collections.abc import Sequence
from typing import Any, Protocol


class OutboxQueryPort(Protocol):
    def list_outbox(
        self,
        *,
        status: Sequence[str] | None = None,
        channel: Sequence[str] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]: ...

    def count_by_status(self) -> dict[str, int]: ...
