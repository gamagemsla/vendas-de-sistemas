"""Clock port definition."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol
from zoneinfo import ZoneInfo


class Clock(Protocol):
    """Port para obtenção de tempo atual - permite fake em testes."""

    def now(self, tz: ZoneInfo | None = None) -> datetime:
        """Retorna o datetime atual no timezone especificado (UTC se None)."""
        ...
