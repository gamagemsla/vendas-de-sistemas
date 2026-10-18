"""Testes unitários para bootstrap (settings e logging)."""

import pytest

from vendas.bootstrap.logging import mask_sensitive_data
from vendas.bootstrap.settings import Settings, get_settings


class TestSettings:
    """Testes para validação de Settings."""

    def test_settings_fails_without_database_url(self, monkeypatch):
        """Valida se Settings falha quando DATABASE_URL não está presente."""
        # Remove DATABASE_URL do ambiente se existir
        monkeypatch.delenv("DATABASE_URL", raising=False)

        # Tenta criar Settings sem DATABASE_URL - deve falhar
        # Pass env_file=None to prevent loading from .env file
        with pytest.raises(Exception) as exc_info:
            Settings(_env_file=None)

        # Verifica que é um erro de validação do pydantic
        assert "DATABASE_URL" in str(exc_info.value)
        assert "Field required" in str(exc_info.value) or "missing" in str(exc_info.value).lower()

    def test_settings_works_with_database_url(self, monkeypatch):
        """Valida se Settings funciona quando DATABASE_URL está presente."""
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")

        settings = Settings()

        assert settings.DATABASE_URL == "postgresql://user:pass@localhost/db"
        assert settings.DRY_RUN is True
        assert settings.AUTOMATION_ENABLED is False

    def test_get_settings_returns_valid_instance(self, monkeypatch):
        """Valida se get_settings retorna instância válida quando DATABASE_URL está presente."""
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")

        settings = get_settings()

        assert isinstance(settings, Settings)
        assert settings.DATABASE_URL == "postgresql://user:pass@localhost/db"


class TestLogging:
    """Testes para mascaramento de dados sensíveis no logging."""

    def test_mask_phone_number(self):
        """Valida se o sistema de log mascara corretamente um número de telefone."""
        event_dict = {"phone": "+5511988887777", "message": "teste"}

        result = mask_sensitive_data(None, "info", event_dict)

        # Verifica que o telefone foi mascarado: +5511****7777
        assert result["phone"] == "+5511****7777"
        assert result["message"] == "teste"

    def test_mask_phone_number_various_formats(self):
        """Valida mascaramento de diferentes formatos de telefone."""
        test_cases = [
            ("+5511999999999", "+5511****9999"),
            ("+5511988887777", "+5511****7777"),
            ("+5521987654321", "+5521****4321"),
        ]

        for input_phone, expected in test_cases:
            event_dict = {"phone": input_phone}
            result = mask_sensitive_data(None, "info", event_dict)
            assert result["phone"] == expected, f"Falhou para {input_phone}"

    def test_mask_email(self):
        """Valida se o sistema de log mascara corretamente um e-mail."""
        event_dict = {"email": "usuario@exemplo.com", "message": "teste"}

        result = mask_sensitive_data(None, "info", event_dict)

        # Verifica que o e-mail foi mascarado: us***@exemplo.com
        assert result["email"] == "us***@exemplo.com"
        assert result["message"] == "teste"

    def test_no_mask_for_non_sensitive_keys(self):
        """Valida que chaves não sensíveis não são mascaradas."""
        event_dict = {"name": "João Silva", "city": "São Paulo", "message": "teste"}

        result = mask_sensitive_data(None, "info", event_dict)

        assert result["name"] == "João Silva"
        assert result["city"] == "São Paulo"
        assert result["message"] == "teste"

    def test_mask_case_insensitive(self):
        """Valida que o mascaramento é case-insensitive para as chaves."""
        event_dict = {
            "PHONE": "+5511988887777",
            "Phone": "+5521999998888",
            "EMAIL": "teste@email.com",
            "Email": "outro@email.com",
        }

        result = mask_sensitive_data(None, "info", event_dict)

        assert result["PHONE"] == "+5511****7777"
        assert result["Phone"] == "+5521****8888"
        assert result["EMAIL"] == "te***@email.com"
        assert result["Email"] == "ou***@email.com"
