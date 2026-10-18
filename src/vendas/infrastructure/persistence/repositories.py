from sqlalchemy.orm import Session

from vendas.domain.entities.lead import Lead
from vendas.domain.value_objects.cnpj import Cnpj
from vendas.domain.value_objects.phone import Phone
from vendas.infrastructure.persistence.mappers import LeadMapper
from vendas.infrastructure.persistence.orm_models import LeadModel


class SQLAlchemyLeadRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, lead_id: str) -> Lead | None:
        model = self._session.query(LeadModel).filter_by(id=lead_id).first()
        return LeadMapper.to_domain(model) if model else None

    def find_by_dedupe_key(self, cnpj: Cnpj | None, phone: Phone | None) -> Lead | None:
        query = self._session.query(LeadModel)
        if cnpj:
            model = query.filter_by(cnpj=str(cnpj)).first()
            if model:
                return LeadMapper.to_domain(model)
        if phone:
            model = query.filter_by(phone_e164=str(phone)).first()
            if model:
                return LeadMapper.to_domain(model)
        return None

    def add(self, lead: Lead) -> None:
        model = LeadMapper.to_orm(lead)
        self._session.add(model)

    def save(self, lead: Lead) -> None:
        model = LeadMapper.to_orm(lead)
        self._session.merge(model)
