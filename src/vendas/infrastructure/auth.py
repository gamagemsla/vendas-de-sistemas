"""Adaptador de autenticação baseado em settings."""

from __future__ import annotations

import hmac
from typing import Final

from vendas.bootstrap.settings import settings
from vendas.domain.ports.auth import AuthContext, AuthPort, Role


class SettingsAuthAdapter(AuthPort):
    """Implementação de AuthPort que valida tokens contra settings."""

    _ADMIN_TOKEN: Final[str] = settings.API_ADMIN_TOKEN
    _OPERATOR_TOKEN: Final[str] = settings.API_OPERATOR_TOKEN

    def verify_token(self, token: str) -> AuthContext | None:
        if hmac.compare_digest(token, self._ADMIN_TOKEN):
            return AuthContext(user_id="admin", role=Role.ADMIN)
        if hmac.compare_digest(token, self._OPERATOR_TOKEN):
            return AuthContext(user_id="operator", role=Role.OPERATOR)
        return None
