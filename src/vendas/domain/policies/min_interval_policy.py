"""MinIntervalPolicy - Verifica intervalo mínimo entre envios consecutivos ao mesmo lead."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from vendas.domain.ports import Clock


class MinIntervalRepository(Protocol):
    """Port para obter timestamp do último envio ao lead/canal."""

    def get_last_sent_at(self, lead_id: str, channel: str) -> datetime | None:
        """Retorna datetime do último envio bem-sucedido ou None."""
        ...

    def set_last_sent_at(self, lead_id: str, channel: str, sent_at: datetime) -> None:
        """Registra timestamp de envio bem-sucedido."""
        ...


@dataclass(frozen=True, slots=True)
class MinIntervalResult:
    allowed: bool
    last_sent_at: datetime | None
    min_interval: timedelta
    next_allowed_at: datetime | None


class MinIntervalPolicy:
    """Política de intervalo mínimo entre envios consecutivos."""

    def __init__(
        self,
        repository: MinIntervalRepository,
        clock: Clock,
        min_interval_seconds: int = 60,
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._min_interval = timedelta(seconds=min_interval_seconds)

    def check(
        self,
        lead_id: str,
        channel: str = "whatsapp",
        reference_time: datetime | None = None,
    ) -> MinIntervalResult:
        now = reference_time or self._clock.now()
        last_sent = self._repository.get_last_sent_at(lead_id, channel)
        if last_sent is None:
            return MinIntervalResult(
                allowed=True,
                last_sent_at=None,
                min_interval=self._min_interval,
                next_allowed_at=None,
            )
        next_allowed = last_sent + self._min_interval
        allowed = now >= next_allowed
        return MinIntervalResult(
            allowed=allowed,
            last_sent_at=last_sent,
            min_interval=self._min_interval,
            next_allowed_at=next_allowed,
        )

    def is_allowed(
        self,
        lead_id: str,
        channel: str = "whatsapp",
        reference_time: datetime | None = None,
    ) -> bool:
        return self.check(lead_id, channel, reference_time).allowed

    def record_send(
        self,
        lead_id: str,
        channel: str = "whatsapp",
        reference_time: datetime | None = None,
    ) -> None:
        now = reference_time or self._clock.now()
        self._repository.set_last_sent_at(lead_id, channel, now)
