"""Testes unitários para GeminiConversationAgent (mock em memória, sem rede)."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest
from google.genai import errors

from vendas.domain.ports import AgentContext, AgentDecision, Message
from vendas.infrastructure.llm.gemini import GeminiConversationAgent

# ---------------------------------------------------------------------------
# Fakes / Helpers
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FakeLead:
    id: str = "00000000-0000-0000-0000-000000000001"
    name: str = "Lead Teste"
    status: str = "ELIGIBLE"
    phone: str | None = None
    cnpj: str | None = None


def make_context(
    *,
    history: list[Message] | None = None,
    knowledge_base: dict | None = None,
) -> AgentContext:
    """Constrói um AgentContext mínimo para testes."""
    lead = FakeLead()
    return AgentContext(
        lead=lead,  # type: ignore[arg-type]
        conversation_history=history or [],
        current_step=0,
        cadence_step_template=None,
        lead_enriched_data=None,
        knowledge_base=knowledge_base or {},
    )


class FakeBudgetTracker:
    """Tracker de orçamento que registra chamadas para verificação."""

    def __init__(self) -> None:
        self.consumed = 0
        self.blocked = False

    def check_and_consume(self, amount: int) -> None:
        if self.blocked:
            raise RuntimeError("Budget exceeded")
        self.consumed += amount


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------


def test_decide_returns_structured_decision_on_success() -> None:
    """Decisão estruturada com retorno JSON válido parseado com sucesso."""
    tracker = FakeBudgetTracker()

    # Mock da resposta do modelo
    mock_response = MagicMock()
    mock_response.text = (
        '{"intent": "question", "reply": "Olá, como posso ajudar?", '
        '"next_state": "awaiting_reply", "confidence": 0.9, '
        '"needs_handoff": false, "reason": ""}'
    )

    with patch("vendas.infrastructure.llm.gemini.genai.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        mock_client_class.return_value = mock_client

        agent = GeminiConversationAgent(api_key="fake-key", budget_tracker=tracker)
        ctx = make_context()
        decision = agent.decide(ctx)

        # Verificações
        assert isinstance(decision, AgentDecision)
        assert decision.action == "reply"
        assert decision.response_text == "Olá, como posso ajudar?"
        assert decision.confidence == 0.9
        assert decision.handoff_reason is None
        assert decision.metadata["intent"] == "question"
        assert tracker.consumed == 1
        mock_client.models.generate_content.assert_called_once()


def test_decide_fallback_on_api_error() -> None:
    """Fallback seguro quando a chamada ao modelo lança errors.APIError."""
    tracker = FakeBudgetTracker()

    with patch("vendas.infrastructure.llm.gemini.genai.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = errors.APIError("quota exceeded", {})
        mock_client_class.return_value = mock_client

        agent = GeminiConversationAgent(api_key="fake-key", budget_tracker=tracker)
        ctx = make_context()
        decision = agent.decide(ctx)

        assert decision.action == "handoff"
        assert decision.confidence == 0.0
        assert "quota exceeded" in decision.handoff_reason
        assert decision.metadata["intent"] == "llm_error_fallback"
        assert tracker.consumed == 1


def test_decide_fallback_on_generic_exception() -> None:
    """Fallback seguro quando ocorre exceção genérica inesperada."""
    tracker = FakeBudgetTracker()

    with patch("vendas.infrastructure.llm.gemini.genai.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = RuntimeError("network down")
        mock_client_class.return_value = mock_client

        agent = GeminiConversationAgent(api_key="fake-key", budget_tracker=tracker)
        ctx = make_context()
        decision = agent.decide(ctx)

        assert decision.action == "handoff"
        assert decision.confidence == 0.0
        assert "network down" in decision.handoff_reason
        assert tracker.consumed == 1


def test_decide_budget_tracker_blocks_when_exceeded() -> None:
    """Bloqueio preventivo e débito de orçamento via BudgetTracker."""
    tracker = FakeBudgetTracker()
    tracker.blocked = True

    with patch("vendas.infrastructure.llm.gemini.genai.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        agent = GeminiConversationAgent(api_key="fake-key", budget_tracker=tracker)
        ctx = make_context()

        with pytest.raises(RuntimeError, match="Budget exceeded"):
            agent.decide(ctx)

        # Nenhuma chamada ao modelo deve ocorrer
        mock_client.models.generate_content.assert_not_called()
        assert tracker.consumed == 0
