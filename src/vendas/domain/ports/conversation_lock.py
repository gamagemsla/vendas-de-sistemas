from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Protocol
from uuid import UUID


class ConversationLock(Protocol):
    """Porta para obter lock exclusivo por lead/conversa."""

    def acquire(self, lead_id: UUID) -> AbstractContextManager[None]:
        """Retorna um context manager que mantém o lock até o fim do bloco."""
        ...
