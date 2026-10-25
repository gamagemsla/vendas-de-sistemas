from __future__ import annotations

import structlog

from vendas.domain.errors import ProviderError
from vendas.domain.policies.eligibility_policy import EligibilityPolicy
from vendas.domain.ports import Clock, LeadEnricher, UnitOfWork

logger = structlog.get_logger(__name__)


class EnrichLeadCommand:
    """Caso de uso para enriquecer um lead via Firecrawl e avaliar sua elegibilidade."""

    def __init__(
        self,
        uow: UnitOfWork,
        enricher: LeadEnricher,
        eligibility_policy: EligibilityPolicy,
        clock: Clock,
    ) -> None:
        self._uow = uow
        self._enricher = enricher
        self._eligibility_policy = eligibility_policy
        self._clock = clock

    def execute(self, lead_id: str) -> None:
        now = self._clock.now()
        with self._uow as uow:
            lead = uow.leads.get(lead_id)
            if not lead:
                return

            # Se o lead tiver um site cadastrado, tenta enriquecer
            website = getattr(lead, "website", None)
            if website:
                try:
                    enrichment_data = self._enricher.enrich(website)
                except ProviderError as exc:
                    # Falha parcial: loga e continua sem enriquecer
                    logger.warning(
                        "enriquecimento_falhou_parcialmente",
                        lead_id=lead_id,
                        enricher=self._enricher.enricher_name,
                        error=str(exc),
                    )
                    enrichment_data = None

                # Atualiza metadados do lead com o resultado do enriquecimento
                if enrichment_data:
                    lead.enrich_data(enrichment_data, at=now)

            # Valida políticas de elegibilidade (supressão, consentimento/base legal, etc.)
            if lead.phone is not None:
                is_eligible = self._eligibility_policy.is_eligible(
                    lead_id=lead.id,
                    phone=lead.phone,
                    email=str(lead.email) if lead.email else None,
                    status=lead.status.value if lead.status else None,
                )
                if is_eligible:
                    lead.mark_as_eligible(at=now)
                else:
                    lead.disqualify(
                        reason="Falha na política de elegibilidade ou supressão", at=now
                    )

            uow.leads.save(lead)
            uow.commit()
