from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from vendas.application.commands.enrich_lead import EnrichLeadCommand
from vendas.application.commands.ingest_leads import IngestLeadsCommand
from vendas.application.commands.process_cadence_step import ProcessCadenceStepCommand
from vendas.application.queries.catalog import CatalogPreviewQuery, ListCatalogServicesQuery
from vendas.bootstrap.settings import settings
from vendas.domain.policies.eligibility_policy import EligibilityPolicy
from vendas.domain.policies.send_window_policy import SendWindowPolicy
from vendas.domain.ports import Clock, JobQueue
from vendas.domain.ports import UnitOfWork as UowProtocol
from vendas.domain.ports.auth import AuthPort
from vendas.domain.ports.catalog import CatalogRepository
from vendas.domain.ports.conversation_lock import ConversationLock
from vendas.domain.ports.knowledge_base import KnowledgeBasePort
from vendas.domain.ports.uow import UnitOfWork as UowProtocolForDispatcher
from vendas.infrastructure.auth import SettingsAuthAdapter
from vendas.infrastructure.channels.evolution_whatsapp import EvolutionWhatsAppChannel
from vendas.infrastructure.clock import SystemClock
from vendas.infrastructure.knowledge_base import SqlAlchemyKnowledgeBase
from vendas.infrastructure.persistence.catalog_repository import SqlAlchemyCatalogRepository
from vendas.infrastructure.persistence.conversation_query_factory import (
    SessionFactoryConversationQuery,
)
from vendas.infrastructure.persistence.dashboard_queries import SqlAlchemyDashboardQuery
from vendas.infrastructure.persistence.dashboard_query_factory import SessionFactoryDashboardQuery
from vendas.infrastructure.persistence.legal_basis import SQLAlchemyLegalBasisPort
from vendas.infrastructure.persistence.orm_models import (
    CatalogItemModel,
    ConversationModel,
    ConversationState,
    LeadModel,
)
from vendas.infrastructure.persistence.pg_conversation_lock import PgAdvisoryConversationLock
from vendas.infrastructure.persistence.suppression_port import SQLAlchemySuppressionPort
from vendas.infrastructure.persistence.unit_of_work import SQLAlchemyUnitOfWork
from vendas.infrastructure.providers.apify import ApifyLeadSource
from vendas.infrastructure.providers.firecrawl import FirecrawlLeadEnricher
from vendas.infrastructure.queue.dispatcher import OutboxDispatcher
from vendas.infrastructure.queue.job_queue import InMemoryJobQueue


class Container:
    """Bootstrap para composição de dependências e adaptação da infraestrutura."""

    def __init__(self) -> None:
        self.engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
        self.session_factory = sessionmaker(
            bind=self.engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )

        self.CatalogItemModel = CatalogItemModel
        self.ConversationModel = ConversationModel
        self.ConversationState = ConversationState
        self.LeadModel = LeadModel

        self.clock: Clock = SystemClock()
        self.auth_port: AuthPort = SettingsAuthAdapter()
        self.job_queue: JobQueue = InMemoryJobQueue()

        self.uow = SQLAlchemyUnitOfWork(self.session_factory, self.clock)
        self.catalog_repository_factory: Callable[[Session], CatalogRepository] = lambda session: (
            cast(CatalogRepository, SqlAlchemyCatalogRepository(session, self.clock))
        )
        self.knowledge_base_factory: Callable[[Session], KnowledgeBasePort] = lambda session: cast(
            KnowledgeBasePort, SqlAlchemyKnowledgeBase(session)
        )

        # Providers
        self.firecrawl_enricher = FirecrawlLeadEnricher(api_key=settings.FIRECRAWL_API_KEY)

    # --- factories / getters -------------------------------------------------

    def conversation_lock_factory(self, session: Session) -> ConversationLock:
        """Cria e retorna instância de ConversationLock para a sessão."""
        return cast(ConversationLock, PgAdvisoryConversationLock(session))

    def get_outbox_dispatcher(self) -> OutboxDispatcher:
        channel = EvolutionWhatsAppChannel(
            base_url=settings.EVOLUTION_API_URL,
            api_key=settings.EVOLUTION_API_KEY,
            instance_name="default",
        )
        return OutboxDispatcher(cast(UowProtocolForDispatcher, self.uow), channel)

    def get_process_cadence_step_command(self) -> ProcessCadenceStepCommand:
        send_window_policy = SendWindowPolicy(self.clock)
        from vendas.domain.ports import UnitOfWork as ProcessUowProtocol

        return ProcessCadenceStepCommand(
            uow=cast(ProcessUowProtocol, self.uow),
            clock=self.clock,
            send_window_policy=send_window_policy,
        )

    def get_ingest_leads_command(self) -> IngestLeadsCommand:
        lead_source = ApifyLeadSource(
            api_key=settings.APIFY_API_KEY,
            actor_id=settings.APIFY_ACTOR_ID,
        )
        return IngestLeadsCommand(
            uow=cast(UowProtocol, self.uow),
            lead_source=lead_source,
            clock=self.clock,
            job_queue=self.job_queue,
        )

    def get_enrich_lead_command(self) -> EnrichLeadCommand:
        suppression_port = SQLAlchemySuppressionPort()
        legal_basis_port = SQLAlchemyLegalBasisPort()
        eligibility_policy = EligibilityPolicy(
            suppression_port=suppression_port,
            legal_basis_port=legal_basis_port,
        )
        return EnrichLeadCommand(
            uow=cast(UowProtocol, self.uow),
            enricher=self.firecrawl_enricher,
            eligibility_policy=eligibility_policy,
            clock=self.clock,
        )

    # --- query helpers -------------------------------------------------------

    def get_overview_kpis_query(self) -> Any:
        return SessionFactoryDashboardQuery(self.session_factory)

    def get_handoff_conversations_query(self) -> Any:
        return SessionFactoryConversationQuery(self.session_factory)

    def get_conversation_history_query(self) -> Any:
        return SessionFactoryConversationQuery(self.session_factory)

    def get_catalog_preview_query(self) -> Any:
        kb = self.knowledge_base_factory(self.session_factory())
        return CatalogPreviewQuery(kb)

    def get_list_catalog_services_query(self) -> Any:
        kb = self.knowledge_base_factory(self.session_factory())
        return ListCatalogServicesQuery(kb)

    def make_dashboard_query(self, session: Session) -> Any:
        return SqlAlchemyDashboardQuery(session)

    def get_catalog_repository(self, session: Session) -> CatalogRepository:
        return cast(CatalogRepository, SqlAlchemyCatalogRepository(session, self.clock))

    def get_knowledge_base(self, session: Session) -> KnowledgeBasePort:
        return cast(KnowledgeBasePort, SqlAlchemyKnowledgeBase(session))


container = Container()
