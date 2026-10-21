"""Port de autenticação da API."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class Role(str, Enum):
    """Papéis permitidos na API."""

    ADMIN = "admin"
    OPERATOR = "operator"


@dataclass(frozen=True, slots=True)
class AuthContext:
    """Contexto de autenticação validado."""

    user_id: str
    role: Role


class AuthPort(Protocol):
    """Porta para verificação de tokens de API."""

    def verify_token(self, token: str) -> AuthContext | None:
        """Retorna AuthContext se token válido, caso contrário None."""
        ...
