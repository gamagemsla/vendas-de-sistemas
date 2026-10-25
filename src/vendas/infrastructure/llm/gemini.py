import google.generativeai as genai
from pydantic import BaseModel, Field

from vendas.domain.ports import AgentContext, AgentDecision, BudgetTracker
from vendas.infrastructure.llm.prompts import PROMPT_VERSION, build_gemini_prompt


class AgentDecisionDTO(BaseModel):
    """Schema Pydantic rígido para a tomada de decisão da IA (garantido por JSON Schema)."""

    intent: str = Field(
        ...,
        description="Intenção detectada do lead (ex: question, objection, schedule, price_inquiry, hostile)",
    )
    reply: str = Field(
        ...,
        description="Resposta comercial a ser enviada, derivada estritamente da base de conhecimento.",
    )
    next_state: str = Field(
        ...,
        description="Próximo estado sugerido para a conversa na máquina de estados.",
    )
    confidence: float = Field(
        ...,
        description="Nível de confiança da IA na resposta, variando de 0.0 a 1.0.",
    )
    needs_handoff: bool = Field(
        ...,
        description="True se a conversa precisar ser transferida para um operador humano.",
    )
    reason: str = Field(
        ...,
        description="Justificativa detalhada para a decisão tomada e para o eventual handoff.",
    )


class GeminiConversationAgent:
    """Adaptador de infraestrutura para o agente conversacional baseado no Google Gemini."""

    def __init__(
        self,
        api_key: str,
        model_name: str = "gemini-1.5-pro",
        budget_tracker: BudgetTracker | None = None,
    ) -> None:
        genai.configure(api_key=api_key)
        self._model_name = model_name
        self._budget_tracker = budget_tracker

        # Configura o modelo para impor obrigatoriamente um schema Pydantic na saída (Structured Outputs)
        self._model = genai.GenerativeModel(
            model_name=self._model_name,
            generation_config={
                "temperature": 0.2,
                "response_mime_type": "application/json",
                "response_schema": AgentDecisionDTO,
            },
        )

    @property
    def agent_name(self) -> str:
        return "gemini"

    def decide(self, context: AgentContext) -> AgentDecision:
        """Executa a chamada ao Gemini com guardrails de schema e fallback seguro."""
        if self._budget_tracker is not None:
            self._budget_tracker.check_and_consume(1)

        full_prompt = build_gemini_prompt(context)

        try:
            response = self._model.generate_content(full_prompt)
            dto = AgentDecisionDTO.model_validate_json(response.text)

            # Map DTO to domain AgentDecision
            action = "handoff" if dto.needs_handoff else "reply"
            metadata = {
                "intent": dto.intent,
                "next_state": dto.next_state,
                "prompt_version": PROMPT_VERSION,
            }
            return AgentDecision(
                action=action,
                response_text=dto.reply,
                confidence=dto.confidence,
                handoff_reason=dto.reason if dto.needs_handoff else None,
                metadata=metadata,
            )

        except Exception as e:  # noqa: BLE001
            # Degradação graciosa e segura: se o Gemini falhar, aciona o handoff humano imediatamente
            return AgentDecision(
                action="handoff",
                response_text=(
                    "Entendo perfeitamente. Para lhe dar uma resposta exata e personalizada, "
                    "vou transferir o seu atendimento para um especialista humano agora mesmo."
                ),
                confidence=0.0,
                handoff_reason=f"Falha de segurança e indisponibilidade do LLM: {e!s}",
                metadata={"intent": "llm_error_fallback", "prompt_version": PROMPT_VERSION},
            )
