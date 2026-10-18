from types import TracebackType
from typing import Any, Protocol, Self
from vendas.domain.ports.catalog import CatalogRepository

class UnitOfWork(Protocol):
    leads: Any
    conversations: Any
    outbox: Any
    enrollments: Any
    bookings: Any
    inbound_events: Any
    suppression: Any
    catalog: CatalogRepository

    def __enter__(self) -> Self: ...

    def __exit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: Any) -> None:...
    

    def commit(self) -> None: ...

    def rollback(self) -> None: ...
