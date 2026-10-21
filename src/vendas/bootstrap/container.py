from __future__ import annotations

import importlib
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from vendas.bootstrap.settings import settings
from vendas.domain.ports import Clock
from vendas.domain.ports.auth import AuthPort
from vendas.domain.ports.catalog import CatalogRepository
from vendas.domain.ports.knowledge_base import KnowledgeBasePort
from vendas.infrastructure.clock import SystemClock
from vendas.infrastructure.knowledge_base import SqlAlchemyKnowledgeBase
from vendas.infrastructure.persistence.catalog_repository import SqlAlchemyCatalogRepository


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

        # Ports implementations
        self.clock: Clock = SystemClock()
        from vendas.infrastructure.auth import SettingsAuthAdapter

        self.auth_port: AuthPort = SettingsAuthAdapter()

        unit_of_work_module = importlib.import_module(
            "vendas.infrastructure.persistence.unit_of_work"
        )
        self.uow = unit_of_work_module.SQLAlchemyUnitOfWork(self.session_factory, self.clock)
        self.catalog_repository_factory = lambda session: SqlAlchemyCatalogRepository(
            session, self.clock
        )
        self.knowledge_base_factory = lambda session: SqlAlchemyKnowledgeBase(session)

    def make_dashboard_query(self, session: Session) -> Any:
        dashboard_query_module = importlib.import_module(
            "vendas.infrastructure.persistence.dashboard_queries"
        )
        return dashboard_query_module.SqlAlchemyDashboardQuery(session)

    def get_catalog_repository(self, session: Session) -> CatalogRepository:
        return SqlAlchemyCatalogRepository(session, self.clock)

    def get_knowledge_base(self, session: Session) -> KnowledgeBasePort:
        return SqlAlchemyKnowledgeBase(session)


container = Container()
