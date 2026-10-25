"""Testes unitários de autenticação da API."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient

from vendas.domain.ports.auth import AuthContext, Role
from vendas.interfaces.api.app import app
from vendas.interfaces.api.deps import require_role

# Rota leve exclusiva para validar o middleware e as roles sem tocar em banco
_auth_test_router = APIRouter(prefix="/test-auth")

# Dependências extraídas para variáveis de módulo (Ruff B008)
admin_role_dep = Depends(require_role(Role.ADMIN))
operator_role_dep = Depends(require_role(Role.ADMIN, Role.OPERATOR))


@_auth_test_router.get("/admin-only")
def _admin_endpoint(user: AuthContext = admin_role_dep) -> dict[str, str]:
    return {"status": "ok", "user": user.user_id}


app.include_router(_auth_test_router)
client = TestClient(app)


def test_missing_token_returns_401() -> None:
    response = client.get("/test-auth/admin-only")
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"


def test_invalid_token_returns_401() -> None:
    headers = {"Authorization": "Bearer invalid-token"}
    response = client.get("/test-auth/admin-only", headers=headers)
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"


def test_operator_cannot_access_admin_endpoint() -> None:
    headers = {"Authorization": "Bearer dev-operator-token"}
    response = client.get("/test-auth/admin-only", headers=headers)
    assert response.status_code == 403


def test_admin_can_access_admin_endpoint() -> None:
    headers = {"Authorization": "Bearer dev-admin-token"}
    response = client.get("/test-auth/admin-only", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["user"] == "admin"
