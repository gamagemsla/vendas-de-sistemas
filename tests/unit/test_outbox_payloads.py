"""Testes para validação de payloads da Outbox."""

from __future__ import annotations

import pytest

from vendas.domain.entities.outbox_payloads import (
    InvalidOutboxPayloadError,
    validate_outbox_payload,
)


class TestOutboxPayloadValidation:
    """Testes de validação dos três event_types."""

    def test_send_ai_response_valid(self) -> None:
        payload = {"phone": "+5511999999999", "content": "Olá, tudo bem?"}
        result = validate_outbox_payload("SEND_AI_RESPONSE", payload)
        assert result == payload

    def test_send_ai_response_invalid_phone_empty(self) -> None:
        payload = {"phone": "", "content": "Oi"}
        with pytest.raises(InvalidOutboxPayloadError):
            validate_outbox_payload("SEND_AI_RESPONSE", payload)

    def test_send_ai_response_invalid_phone_format(self) -> None:
        payload = {"phone": "11999999999", "content": "Oi"}  # missing +
        with pytest.raises(InvalidOutboxPayloadError):
            validate_outbox_payload("SEND_AI_RESPONSE", payload)

    def test_send_ai_response_missing_content(self) -> None:
        payload = {"phone": "+5511999999999", "content": ""}
        with pytest.raises(InvalidOutboxPayloadError):
            validate_outbox_payload("SEND_AI_RESPONSE", payload)

    def test_send_cadence_message_valid(self) -> None:
        payload = {
            "lead_id": "123e4567-e89b-12d3-a456-426614174000",
            "phone": "+5511999999999",
            "step": 1,
            "content": "Mensagem de cadência",
        }
        result = validate_outbox_payload("SEND_CADENCE_MESSAGE", payload)
        assert result["lead_id"] == payload["lead_id"]
        assert result["step"] == 1

    def test_send_cadence_message_phone_none_not_allowed(self) -> None:
        payload = {
            "lead_id": "123e4567-e89b-12d3-a456-426614174000",
            "phone": None,
            "step": 1,
            "content": "Mensagem",
        }
        with pytest.raises(InvalidOutboxPayloadError):
            validate_outbox_payload("SEND_CADENCE_MESSAGE", payload)

    def test_send_cadence_message_step_zero_invalid(self) -> None:
        payload = {
            "lead_id": "123e4567-e89b-12d3-a456-426614174000",
            "phone": "+5511999999999",
            "step": 0,
            "content": "Mensagem",
        }
        with pytest.raises(InvalidOutboxPayloadError):
            validate_outbox_payload("SEND_CADENCE_MESSAGE", payload)

    def test_send_cadence_message_invalid_lead_id(self) -> None:
        payload = {
            "lead_id": "not-a-uuid",
            "phone": "+5511999999999",
            "step": 1,
            "content": "Mensagem",
        }
        with pytest.raises(InvalidOutboxPayloadError):
            validate_outbox_payload("SEND_CADENCE_MESSAGE", payload)

    def test_operator_takeover_valid(self) -> None:
        payload = {"phone": "+5511999999999", "content": "Mensagem do operador"}
        result = validate_outbox_payload("OPERATOR_TAKEOVER_MESSAGE", payload)
        assert result == payload

    def test_operator_takeover_invalid_phone(self) -> None:
        payload = {"phone": "invalid", "content": "Msg"}
        with pytest.raises(InvalidOutboxPayloadError):
            validate_outbox_payload("OPERATOR_TAKEOVER_MESSAGE", payload)

    def test_unknown_event_type(self) -> None:
        payload = {"phone": "+5511999999999", "content": "Oi"}
        with pytest.raises(InvalidOutboxPayloadError):
            validate_outbox_payload("UNKNOWN_EVENT", payload)
