from datetime import UTC, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from vendas.domain.entities.lead import Lead
from vendas.domain.value_objects.cnpj import Cnpj
from vendas.domain.value_objects.phone import Phone


class InMemoryLeadRepository:
    def __init__(self) -> None:
        self.storage: dict[UUID, Lead] = {}

    def get(self, lead_id: UUID | str) -> Lead | None:
        if isinstance(lead_id, str):
            lead_id = UUID(lead_id)
        return self.storage.get(lead_id)

    def find_by_dedupe_key(self, cnpj: Cnpj | None, phone: Phone | None) -> Lead | None:
        for lead in self.storage.values():
            if cnpj and lead.cnpj and lead.cnpj == cnpj:
                return lead
            if phone and lead.phone and lead.phone == phone:
                return lead
        return None

    def add(self, lead: Lead) -> None:
        self.storage[lead.id] = lead

    def save(self, lead: Lead) -> None:
        self.storage[lead.id] = lead


class FakeClock:
    """Fake clock for tests - controllable time, always returns aware UTC datetime."""

    def __init__(self, initial_time: datetime | None = None) -> None:
        # Ensure initial_time is aware UTC
        if initial_time is None:
            self._time = datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC)
        else:
            if initial_time.tzinfo is None:
                self._time = initial_time.replace(tzinfo=UTC)
            else:
                self._time = initial_time.astimezone(UTC)

    def now(self, tz: ZoneInfo | None = None) -> datetime:
        return self._time

    def set_time(self, new_time: datetime) -> None:
        """Define o tempo manualmente para testes."""
        if new_time.tzinfo is None:
            self._time = new_time.replace(tzinfo=UTC)
        else:
            self._time = new_time.astimezone(UTC)

    def advance(self, seconds: int) -> None:
        """Avança o tempo em segundos."""
        self._time += timedelta(seconds=seconds)

    def advance_days(self, days: int) -> None:
        """Avança o tempo em dias."""
        self._time += timedelta(days=days)
