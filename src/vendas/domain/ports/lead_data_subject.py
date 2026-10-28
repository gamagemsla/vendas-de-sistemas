"""Port para direitos do titular de dados (LGPD/GDPR)."""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class LeadDataExport:
    """Dados exportados de um lead para atendimento ao direito de acesso."""

    lead_id: UUID
    phone: str
    email: str | None
    name: str | None
    cnpj: str | None
    status: str
    created_at: datetime
    updated_at: datetime
    inbound_events: list[dict[str, object]]
    outbox_messages: list[dict[str, object]]
    cadence_enrollments: list[dict[str, object]]
    conversation_history: list[dict[str, object]]
    suppression_records: list[dict[str, object]]


class LeadDataSubjectPort(Protocol):
    """Port para operações de direitos do titular (LGPD Art. 18)."""

    @abstractmethod
    async def export(self, lead_id: UUID) -> LeadDataExport:
        """Exporta todos os dados pessoais do lead (direito de acesso)."""
        ...

    @abstractmethod
    async def anonymize(self, lead_id: UUID) -> None:
        """Anonimiza dados pessoais do lead mantendo integridade referencial (direito ao esquecimento parcial)."""
        ...

    @abstractmethod
    async def delete(self, lead_id: UUID) -> None:
        """Exclui permanentemente todos os dados do lead (direito à exclusão)."""
        ...
