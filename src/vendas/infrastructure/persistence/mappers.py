from uuid import UUID

from vendas.domain.entities.lead import Lead
from vendas.domain.entities.lead import LeadStatus as DomainLeadStatus
from vendas.domain.value_objects.cnpj import Cnpj
from vendas.domain.value_objects.email import Email
from vendas.domain.value_objects.phone import Phone
from vendas.infrastructure.persistence.orm_models import LeadModel
from vendas.infrastructure.persistence.orm_models import LeadStatus as OrmLeadStatus


class LeadMapper:
    @staticmethod
    def to_domain(model: LeadModel) -> Lead:
        return Lead(
            id=UUID(str(model.id)),
            name=model.name,
            phone=Phone(model.phone_e164),
            cnpj=Cnpj(model.cnpj) if model.cnpj else None,
            email=Email(model.email) if model.email else None,
            status=DomainLeadStatus(model.status.value),
        )

    @staticmethod
    def to_orm(entity: Lead) -> LeadModel:
        return LeadModel(
            id=entity.id,
            name=entity.name,
            phone_e164=str(entity.phone) if entity.phone else "",
            cnpj=str(entity.cnpj) if entity.cnpj else None,
            email=str(entity.email) if entity.email else None,
            status=OrmLeadStatus(entity.status.value),
        )
