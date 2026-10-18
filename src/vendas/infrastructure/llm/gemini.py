import google.generativeai as genai
from pydantic import BaseModel, Field


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

    def __init__(self, api_key: str, model_name: str = "gemini-1.5-pro") -> None:
        genai.configure(api_key=api_key)
        self._model_name = model_name

        # Configura o modelo para impor obrigatoriamente um schema Pydantic na saída (Structured Outputs)
        self._model = genai.GenerativeModel(
            model_name=self._model_name,
            generation_config={
                "temperature": 0.2,
                "response_mime_type": "application/json",
                "response_schema": AgentDecisionDTO,
            },
        )

    def decide(self, system_prompt: str, conversation_context: str) -> AgentDecisionDTO:
        """Executa a chamada ao Gemini com guardrails de schema e fallback seguro."""
        try:
            full_prompt = (
                f"{system_prompt}\n\n"
                f"--- INÍCIO DOS DADOS DO LEAD E CONTEXTO ---\n"
                f"{conversation_context}\n"
                f"--- FIM DOS DADOS DO LEAD E CONTEXTO ---"
            )

            response = self._model.generate_content(full_prompt)

            # Validação e parsing via Pydantic do JSON retornado pelo provedor
            decision = AgentDecisionDTO.model_validate_json(response.text)
            return decision

        except Exception as e:  # noqa: BLE001
            # Degradação graciosa e segura: se o Gemini falhar, aciona o handoff humano imediatamente
            return AgentDecisionDTO(
                intent="llm_error_fallback",
                reply="Entendo perfeitamente. Para lhe dar uma resposta exata e personalizada, vou transferir o seu atendimento para um especialista humano agora mesmo.",
                next_state="HANDOFF",
                confidence=0.0,
                needs_handoff=True,
                reason=f"Falha de segurança e indisponibilidade do LLM: {e!s}",
            )
