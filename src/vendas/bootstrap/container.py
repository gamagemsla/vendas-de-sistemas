from __future__ import annotations

import importlib
from collections.abc import Callable
from typing import Any, cast

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from vendas.application.commands.process_cadence_step import ProcessCadenceStepCommand
from vendas.bootstrap.settings import settings
from vendas.domain.ports import Clock
from vendas.domain.ports.auth import AuthPort
from vendas.domain.ports.catalog import CatalogRepository
from vendas.domain.ports.conversation_lock import ConversationLock
from vendas.domain.ports.knowledge_base import KnowledgeBasePort


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

        orm_models = importlib.import_module("vendas.infrastructure.persistence.orm_models")
        self.CatalogItemModel = orm_models.CatalogItemModel
        self.ConversationModel = orm_models.ConversationModel
        self.ConversationState = orm_models.ConversationState
        self.LeadModel = orm_models.LeadModel

        # Ports implementations - loaded dynamically via importlib
        clock_module = importlib.import_module("vendas.infrastructure.clock")
        self.clock: Clock = clock_module.SystemClock()

        auth_module = importlib.import_module("vendas.infrastructure.auth")
        self.auth_port: AuthPort = auth_module.SettingsAuthAdapter()

        unit_of_work_module = importlib.import_module(
            "vendas.infrastructure.persistence.unit_of_work"
        )
        self.uow = unit_of_work_module.SQLAlchemyUnitOfWork(self.session_factory, self.clock)
        self.catalog_repository_factory: Callable[[Session], CatalogRepository] = lambda session: (
            cast(
                CatalogRepository,
                importlib.import_module(
                    "vendas.infrastructure.persistence.catalog_repository"
                ).SqlAlchemyCatalogRepository(session, self.clock),
            )
        )
        self.knowledge_base_factory: Callable[[Session], KnowledgeBasePort] = lambda session: cast(
            KnowledgeBasePort,
            importlib.import_module("vendas.infrastructure.knowledge_base").SqlAlchemyKnowledgeBase(
                session
            ),
        )

    # --- factories / getters -------------------------------------------------

    def conversation_lock_factory(self, session: Session) -> ConversationLock:
        """Cria e retorna instância de ConversationLock para a sessão."""
        lock_module = importlib.import_module(
            "vendas.infrastructure.persistence.pg_conversation_lock"
        )
        return cast(ConversationLock, lock_module.PgAdvisoryConversationLock(session))

    def get_outbox_dispatcher(self) -> Any:
        dispatcher_module = importlib.import_module("vendas.infrastructure.queue.dispatcher")
        channel_module = importlib.import_module(
            "vendas.infrastructure.channels.evolution_whatsapp"
        )
        channel = channel_module.EvolutionWhatsAppChannel()
        return dispatcher_module.OutboxDispatcher(self.uow, channel)

    def get_process_cadence_step_command(self) -> ProcessCadenceStepCommand:
        cmd_module = importlib.import_module("vendas.application.commands.process_cadence_step")
        send_window_policy_module = importlib.import_module(
            "vendas.domain.policies.send_window_policy"
        )
        send_window_policy = send_window_policy_module.SendWindowPolicy(self.clock)
        return cast(
            ProcessCadenceStepCommand,
            cmd_module.ProcessCadenceStepCommand(
                uow=self.uow, clock=self.clock, send_window_policy=send_window_policy
            ),
        )

    # --- query helpers -------------------------------------------------------

    def get_overview_kpis_query(self) -> Any:
        query_module = importlib.import_module(
            "vendas.infrastructure.persistence.dashboard_query_factory"
        )
        return query_module.SessionFactoryDashboardQuery(self.session_factory)

    def get_handoff_conversations_query(self) -> Any:
        query_module = importlib.import_module(
            "vendas.infrastructure.persistence.conversation_query_factory"
        )
        return query_module.SessionFactoryConversationQuery(self.session_factory)

    def get_conversation_history_query(self) -> Any:
        query_module = importlib.import_module(
            "vendas.infrastructure.persistence.conversation_query_factory"
        )
        return query_module.SessionFactoryConversationQuery(self.session_factory)

    def get_catalog_preview_query(self) -> Any:
        kb_module = importlib.import_module("vendas.application.queries.catalog")
        kb = self.knowledge_base_factory(self.session_factory())
        return kb_module.CatalogPreviewQuery(kb)

    def get_list_catalog_services_query(self) -> Any:
        kb_module = importlib.import_module("vendas.application.queries.catalog")
        kb = self.knowledge_base_factory(self.session_factory())
        return kb_module.ListCatalogServicesQuery(kb)

    def make_dashboard_query(self, session: Session) -> Any:
        dashboard_query_module = importlib.import_module(
            "vendas.infrastructure.persistence.dashboard_queries"
        )
        return dashboard_query_module.SqlAlchemyDashboardQuery(session)

    def get_catalog_repository(self, session: Session) -> CatalogRepository:
        repo_module = importlib.import_module(
            "vendas.infrastructure.persistence.catalog_repository"
        )
        return cast(CatalogRepository, repo_module.SqlAlchemyCatalogRepository(session, self.clock))

    def get_knowledge_base(self, session: Session) -> KnowledgeBasePort:
        kb_module = importlib.import_module("vendas.infrastructure.knowledge_base")
        return cast(KnowledgeBasePort, kb_module.SqlAlchemyKnowledgeBase(session))


container = Container()
