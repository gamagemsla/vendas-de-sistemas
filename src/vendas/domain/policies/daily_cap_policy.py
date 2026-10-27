"""DailyCapPolicy - Verifica teto diário de envios por canal (single-tenant)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

from vendas.domain.ports import Clock


class DailyCapRepository(Protocol):
    """Port para contagem de envios diários por canal."""

    def count_today(self, channel: str, ref_date: date) -> int:
        """Retorna quantas mensagens foram enviadas hoje para o canal."""
        ...

    def increment(self, channel: str, ref_date: date) -> None:
        """Incrementa contador (chamado após envio bem-sucedido)."""
        ...


@dataclass(frozen=True, slots=True)
class DailyCapResult:
    allowed: bool
    current_count: int
    cap: int
    channel: str
    ref_date: date


class DailyCapPolicy:
    """Política de teto diário de envios (global por canal)."""

    def __init__(
        self,
        repository: DailyCapRepository,
        clock: Clock,
        cap: int = 1000,
    ) -> None:
        self._repository = repository
        self._clock = clock
        self._cap = cap

    def check(
        self, channel: str = "whatsapp", reference_time: datetime | None = None
    ) -> DailyCapResult:
        now = reference_time or self._clock.now()
        ref_date = now.date()
        current = self._repository.count_today(channel, ref_date)
        allowed = current < self._cap
        return DailyCapResult(
            allowed=allowed,
            current_count=current,
            cap=self._cap,
            channel=channel,
            ref_date=ref_date,
        )

    def is_allowed(self, channel: str = "whatsapp", reference_time: datetime | None = None) -> bool:
        return self.check(channel, reference_time).allowed

    def record_send(
        self, channel: str = "whatsapp", reference_time: datetime | None = None
    ) -> None:
        now = reference_time or self._clock.now()
        ref_date = now.date()
        self._repository.increment(channel, ref_date)
