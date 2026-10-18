from collections.abc import Iterable
from typing import Any, Protocol


class LeadSource(Protocol):
    def search(self, query: dict[str, Any]) -> Iterable[dict[str, Any]]: ...
