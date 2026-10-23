"""Re-export do repositório canônico de Outbox (persistence)."""

from vendas.infrastructure.persistence.repositories import SQLAlchemyOutboxRepository

__all__ = ["SQLAlchemyOutboxRepository"]
