"""SystemClock implementation using UTC timezone."""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from vendas.domain.ports import Clock


class SystemClock(Clock):
    """Real clock returning current UTC datetime (aware)."""

    def now(self, tz: ZoneInfo | None = None) -> datetime:  # tz ignored, always UTC
        return datetime.now(UTC)
