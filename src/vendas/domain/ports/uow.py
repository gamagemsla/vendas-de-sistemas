from types import TracebackType
from typing import Any, Protocol, Self

from vendas.domain.ports import EnrollmentRepository
from vendas.domain.ports.catalog import CatalogRepository


class UnitOfWork(Protocol):
    leads: Any
    conversations: Any
    outbox: Any
    enrollments: EnrollmentRepository
    bookings: Any
    inbound_events: Any
    suppression: Any
    catalog: CatalogRepository
    session: Any

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...
