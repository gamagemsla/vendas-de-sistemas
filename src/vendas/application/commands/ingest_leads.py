import asyncio
from typing import Any
from uuid import uuid4

from vendas.domain.entities.lead import Lead
from vendas.domain.ports import Clock, Job, JobQueue, UnitOfWork
from vendas.domain.ports.lead_source import LeadSource
from vendas.domain.value_objects.cnpj import Cnpj
from vendas.domain.value_objects.phone import Phone


class IngestLeadsCommand:
    """Caso de uso responsável por ingerir, normalizar e deduplicar leads em lote."""

    def __init__(
        self,
        uow: UnitOfWork,
        lead_source: LeadSource,
        clock: Clock,
        job_queue: JobQueue,
    ) -> None:
        self._uow = uow
        self._lead_source = lead_source
        self._clock = clock
        self._job_queue = job_queue

    def execute(self, search_query: dict[str, Any]) -> int:
        raw_leads = self._lead_source.search(search_query)
        ingested_count = 0

        with self._uow as uow:
            for raw in raw_leads:
                raw_cnpj = raw.get("cnpj")
                raw_phone = raw.get("phone")

                # Converte para Value Objects (dispara validação estrita)
                try:
                    cnpj_vo = Cnpj(raw_cnpj) if raw_cnpj else None
                    phone_vo = Phone(raw_phone) if raw_phone else None
                except ValueError:
                    # Ignora leads com dados estruturalmente inválidos na origem
                    continue

                # Telefone é obrigatório para prospecção via WhatsApp
                if not phone_vo:
                    continue

                # Deduplicação rígida por chave única (CNPJ ou Telefone)
                existing = uow.leads.find_by_dedupe_key(cnpj=cnpj_vo, phone=phone_vo)
                if existing:
                    # Lead já existe na base; não duplica.
                    continue

                # Cria o novo lead no estado inicial NEW
                now = self._clock.now()
                new_lead = Lead.create_new(
                    name=raw.get("name", "Empresa Desconhecida"),
                    cnpj=cnpj_vo,
                    phone=phone_vo,
                    email=raw.get("email"),
                    at=now,
                )

                uow.leads.add(new_lead)
                ingested_count += 1

                # Enfileira job de enriquecimento
                job = Job(
                    id=uuid4(),
                    name="enrich_lead",
                    payload={"lead_id": str(new_lead.id)},
                )
                asyncio.run(self._job_queue.enqueue(job))

            uow.commit()

        return ingested_count
