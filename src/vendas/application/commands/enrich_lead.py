from vendas.domain.policies.eligibility_policy import EligibilityPolicy
from vendas.domain.ports import LeadEnricher, UnitOfWork


class EnrichLeadCommand:
    """Caso de uso para enriquecer um lead via Firecrawl e avaliar sua elegibilidade."""

    def __init__(
        self,
        uow: UnitOfWork,
        enricher: LeadEnricher,
        eligibility_policy: EligibilityPolicy,
    ) -> None:
        self._uow = uow
        self._enricher = enricher
        self._eligibility_policy = eligibility_policy

    def execute(self, lead_id: str) -> None:
        with self._uow as uow:
            lead = uow.leads.get(lead_id)
            if not lead:
                return

            # Se o lead tiver um site cadastrado, tenta enriquecer
            website = getattr(lead, "website", None)
            if website:
                enrichment_data = self._enricher.enrich(website)
                # Atualiza metadados do lead com o resultado do enriquecimento
                if enrichment_data:
                    lead.enrich_data(enrichment_data)

            # Valida políticas de elegibilidade (supressão, consentimento/base legal, etc.)
            if lead.phone is not None:
                is_eligible = self._eligibility_policy.is_eligible(
                    lead_id=lead.id,
                    phone=lead.phone,
                    email=str(lead.email) if lead.email else None,
                    status=lead.status.value if lead.status else None,
                )
                if is_eligible:
                    lead.mark_as_eligible()
                else:
                    lead.disqualify(reason="Falha na política de elegibilidade ou supressão")

            uow.leads.save(lead)
            uow.commit()
