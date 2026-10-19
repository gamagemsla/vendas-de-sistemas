from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class CatalogServiceEntity:
    id: UUID
    name: str
    description: str | None
    category: str | None
    requires_human_approval: bool
    discount_allowed: bool
    is_active: bool


@dataclass
class CatalogPriceEntity:
    id: UUID
    service_id: UUID
    price_cents: int
    valid_from: datetime
    valid_to: datetime | None


@dataclass
class FaqEntryEntity:
    id: UUID
    service_id: UUID
    question: str
    answer: str
    is_active: bool
