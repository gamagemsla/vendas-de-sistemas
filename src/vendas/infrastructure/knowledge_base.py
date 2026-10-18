from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy.orm import Session

from vendas.infrastructure.persistence.orm_models import CatalogPrice, CatalogService, FaqEntry


class SqlAlchemyKnowledgeBase:
    """Base de conhecimento materializada em SQLAlchemy com invalidação explícita de cache."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._cache: dict[Any, Any] = {}
        self._version = 0

    def invalidate(self) -> None:
        self._cache.clear()
        self._version += 1

    def _now(self, at: datetime | None = None) -> datetime:
        return at or datetime.now(UTC)

    def _active_prices(
        self, service_id: str | UUID | None = None, at: datetime | None = None
    ) -> list[dict[str, Any]]:
        cache_key: tuple[str, str, str] = (
            "prices",
            str(service_id),
            at.isoformat() if at else "all",
        )
        if cache_key not in self._cache:
            now = self._now(at)
            query = self._session.query(CatalogPrice).filter(CatalogPrice.active.is_(True))
            if service_id is not None:
                query = query.filter(CatalogPrice.service_id == UUID(str(service_id)))
            rows = (
                query.filter(
                    (CatalogPrice.valid_from <= now)
                    & ((CatalogPrice.valid_to.is_(None)) | (CatalogPrice.valid_to >= now))
                )
                .order_by(CatalogPrice.valid_from.asc())
                .all()
            )
            price_values: list[dict[str, Any]] = [
                {
                    "id": str(row.id),
                    "service_id": str(row.service_id),
                    "price_cents": row.price_cents,
                    "valid_from": row.valid_from,
                    "valid_to": row.valid_to,
                    "active": row.active,
                }
                for row in rows
            ]
            self._cache[cache_key] = price_values
        cached = self._cache.get(cache_key)
        if cached is None:
            return []
        return cast(list[dict[str, Any]], cached)

    def _active_services(self, at: datetime | None = None) -> list[dict[str, Any]]:
        cache_key: tuple[str, int, str] = (
            "services",
            self._version,
            at.isoformat() if at else "now",
        )
        if cache_key not in self._cache:
            now = self._now(at)
            rows = (
                self._session.query(CatalogService)
                .filter(CatalogService.active.is_(True))
                .order_by(CatalogService.name.asc())
                .all()
            )
            services: list[dict[str, Any]] = []
            for row in rows:
                current_price = self._active_prices(service_id=str(row.id), at=now)
                price_entry: dict[str, Any] | None = current_price[0] if current_price else None
                services.append(
                    {
                        "id": str(row.id),
                        "name": row.name,
                        "description": row.description,
                        "category": row.category,
                        "requires_human_approval": row.requires_human_approval,
                        "discount_allowed": row.discount_allowed,
                        "current_price_cents": price_entry["price_cents"] if price_entry else None,
                    }
                )
            self._cache[cache_key] = services
        cached = self._cache.get(cache_key)
        if cached is None:
            return []
        return cast(list[dict[str, Any]], cached)

    def _active_faqs(
        self, service_id: str | UUID | None = None, at: datetime | None = None
    ) -> list[dict[str, Any]]:
        cache_key: tuple[str, str, int, str] = (
            "faqs",
            str(service_id),
            self._version,
            at.isoformat() if at else "now",
        )
        if cache_key not in self._cache:
            query = self._session.query(FaqEntry).filter(FaqEntry.active.is_(True))
            if service_id is not None:
                query = query.filter(FaqEntry.service_id == UUID(str(service_id)))
            rows = query.order_by(FaqEntry.question.asc()).all()
            faq_values: list[dict[str, Any]] = [
                {
                    "id": str(row.id),
                    "service_id": str(row.service_id),
                    "question": row.question,
                    "answer": row.answer,
                    "active": row.active,
                }
                for row in rows
            ]
            self._cache[cache_key] = faq_values
        cached = self._cache.get(cache_key)
        if cached is None:
            return []
        return cast(list[dict[str, Any]], cached)

    def find_services(
        self, text: str | None = None, at: datetime | None = None
    ) -> list[dict[str, Any]]:
        services = self._active_services(at=at)
        if not text or not text.strip():
            return services
        needle = text.lower().strip()
        return [
            service
            for service in services
            if needle in service["name"].lower() or needle in (service["description"] or "").lower()
        ]

    def find_prices(
        self, service_id: str | None = None, at: datetime | None = None
    ) -> list[dict[str, Any]]:
        return self._active_prices(service_id=service_id, at=at)

    def find_faqs(
        self, question: str | None = None, service_id: str | None = None, at: datetime | None = None
    ) -> list[dict[str, Any]]:
        faqs = self._active_faqs(service_id=service_id, at=at)
        if not question or not question.strip():
            return faqs
        needle = question.lower().strip()
        return [
            faq
            for faq in faqs
            if needle in faq["question"].lower() or needle in faq["answer"].lower()
        ]

    def preview(self, text: str, at: datetime | None = None) -> dict[str, Any]:
        now = self._now(at)
        return {
            "at": now.isoformat(),
            "services": self.find_services(text, at=now),
            "faqs": self.find_faqs(text, at=now),
            "prices": self.find_prices(at=now),
        }
