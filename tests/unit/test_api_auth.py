"""Testes unitários de autenticação da API."""

from __future__ import annotations

from fastapi.testclient import TestClient

from vendas.interfaces.api.app import app

client = TestClient(app)


def test_missing_token_returns_401() -> None:
    response = client.post("/catalog/services", json={"name": "Test", "description": ""})
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"


def test_invalid_token_returns_401() -> None:
    headers = {"Authorization": "Bearer invalid-token"}
    response = client.post(
        "/catalog/services", json={"name": "Test", "description": ""}, headers=headers
    )
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"


def test_operator_cannot_access_admin_endpoint() -> None:
    headers = {"Authorization": "Bearer dev-operator-token"}
    response = client.post(
        "/catalog/services", json={"name": "Test", "description": ""}, headers=headers
    )
    assert response.status_code == 403


def test_admin_can_access_admin_endpoint() -> None:
    headers = {"Authorization": "Bearer dev-admin-token"}
    response = client.post(
        "/catalog/services", json={"name": "Test Service", "description": "desc"}, headers=headers
    )
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["status"] == "created"
