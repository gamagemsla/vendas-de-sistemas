from typing import Any

from sqlalchemy.orm import Session

from vendas.infrastructure.persistence.orm_models import LeadModel


class SqlAlchemyDashboardQuery:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_overview_kpis(self) -> dict[str, Any]:
        query = self._session.query(LeadModel)
        total_leads = query.count()
        qualified_leads = query.filter(LeadModel.status == "QUALIFIED").count()
        opted_out_leads = query.filter(LeadModel.status == "OPTED_OUT").count()
        in_cadence = query.filter(LeadModel.status == "IN_CADENCE").count()
        conversion_rate = (qualified_leads / total_leads * 100) if total_leads > 0 else 0.0

        return {
            "total_leads": total_leads,
            "qualified_leads": qualified_leads,
            "opted_out_leads": opted_out_leads,
            "in_cadence": in_cadence,
            "conversion_rate": round(conversion_rate, 2),
        }
