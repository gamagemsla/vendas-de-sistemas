"""Schemas de validação de payload da Outbox (Domain)."""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class InvalidOutboxPayloadError(ValueError):
    """Erro levantado quando o payload da outbox não conforma ao schema do event_type."""


class SendAiResponsePayload(BaseModel):
    """Payload para evento SEND_AI_RESPONSE."""

    phone: str = Field(..., description="Telefone no formato E.164, ex: +5511999999999")
    content: str = Field(..., min_length=1, description="Conteúdo da mensagem")

    @field_validator("phone")
    @classmethod
    def _phone_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("phone não pode ser vazio")
        # Validação simples de formato E.164: começa com + e apenas dígitos depois
        if not v.startswith("+") or not v[1:].isdigit():
            raise ValueError("phone deve estar no formato E.164 (ex: +5511999999999)")
        return v

    @field_validator("content")
    @classmethod
    def _content_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("content não pode ser vazio")
        return v


class SendCadenceMessagePayload(BaseModel):
    """Payload para evento SEND_CADENCE_MESSAGE."""

    lead_id: str = Field(..., description="UUID do lead")
    phone: str = Field(..., description="Telefone no formato E.164")
    step: int = Field(..., ge=1, description="Número do passo da cadência (>=1)")
    content: str = Field(..., min_length=1, description="Conteúdo da mensagem")

    @field_validator("lead_id")
    @classmethod
    def _lead_id_valid_uuid(cls, v: str) -> str:
        try:
            UUID(v)
        except Exception as exc:
            raise ValueError("lead_id deve ser um UUID válido") from exc
        return v

    @field_validator("phone")
    @classmethod
    def _phone_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("phone não pode ser vazio")
        if not v.startswith("+") or not v[1:].isdigit():
            raise ValueError("phone deve estar no formato E.164 (ex: +5511999999999)")
        return v

    @field_validator("content")
    @classmethod
    def _content_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("content não pode ser vazio")
        return v


class SendCadenceEmailPayload(BaseModel):
    """Payload para evento SEND_CADENCE_EMAIL."""

    to_email: str = Field(..., description="E-mail do destinatário")
    subject: str = Field(..., min_length=1, description="Assunto do e-mail")
    html_content: str = Field(..., min_length=1, description="Conteúdo HTML do e-mail")
    text_content: str | None = Field(None, description="Conteúdo texto plano (opcional)")
    unsubscribe_link: str = Field(..., description="Link de descadastro")
    channel: Literal["email"] = "email"

    @field_validator("to_email")
    @classmethod
    def _email_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("to_email não pode ser vazio")
        # Validação básica de e-mail
        if "@" not in v:
            raise ValueError("to_email deve ser um e-mail válido")
        return v

    @field_validator("subject")
    @classmethod
    def _subject_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("subject não pode ser vazio")
        return v

    @field_validator("html_content")
    @classmethod
    def _html_content_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("html_content não pode ser vazio")
        return v

    @field_validator("unsubscribe_link")
    @classmethod
    def _unsubscribe_link_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("unsubscribe_link não pode ser vazio")
        return v


class OperatorTakeoverPayload(BaseModel):
    """Payload para evento OPERATOR_TAKEOVER_MESSAGE."""

    phone: str = Field(..., description="Telefone no formato E.164")
    content: str = Field(..., min_length=1, description="Conteúdo da mensagem")

    @field_validator("phone")
    @classmethod
    def _phone_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("phone não pode ser vazio")
        if not v.startswith("+") or not v[1:].isdigit():
            raise ValueError("phone deve estar no formato E.164 (ex: +5511999999999)")
        return v

    @field_validator("content")
    @classmethod
    def _content_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("content não pode ser vazio")
        return v


# Mapeamento de event_type para schema
_PAYLOAD_SCHEMAS: dict[str, type[BaseModel]] = {
    "SEND_AI_RESPONSE": SendAiResponsePayload,
    "SEND_CADENCE_MESSAGE": SendCadenceMessagePayload,
    "SEND_CADENCE_EMAIL": SendCadenceEmailPayload,
    "OPERATOR_TAKEOVER_MESSAGE": OperatorTakeoverPayload,
}


def validate_outbox_payload(event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    """
    Valida o payload conforme o event_type.

    Retorna o dict validado (serializado pelo Pydantic).
    Levanta InvalidOutboxPayloadError se event_type desconhecido ou payload inválido.
    """
    schema_cls = _PAYLOAD_SCHEMAS.get(event_type)
    if schema_cls is None:
        raise InvalidOutboxPayloadError(f"event_type desconhecido: {event_type}")

    try:
        validated = schema_cls.model_validate(payload)
    except Exception as exc:  # pydantic.ValidationError
        raise InvalidOutboxPayloadError(f"Payload inválido para {event_type}: {exc}") from exc

    # Retorna dict com tipos nativos (UUID -> str, etc.)
    return validated.model_dump(mode="python")
