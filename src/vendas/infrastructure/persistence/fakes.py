from uuid import UUID

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
