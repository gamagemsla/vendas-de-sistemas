import google.generativeai as genai
from pydantic import BaseModel, Field

from vendas.domain.ports import AgentContext, AgentDecision


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

    @property
    def agent_name(self) -> str:
        return "gemini"

    def decide(self, context: AgentContext) -> AgentDecision:
        """Executa a chamada ao Gemini com guardrails de schema e fallback seguro."""
        # Build system prompt
        system_prompt = (
            "Você é um assistente de prospecção B2B altamente qualificado. "
            "Responda apenas com base nas regras comerciais e dados fornecidos. "
            "Nunca prometa descontos ou prazos sem aprovação humana."
        )

        # Build knowledge base summary
        kb = context.knowledge_base or {}
        services = kb.get("services", [])
        prices = kb.get("prices", [])
        faqs = kb.get("faqs", [])

        kb_lines = []
        if services:
            kb_lines.append("SERVIÇOS DISPONÍVEIS:")
            for svc in services:
                price_info = ""
                if svc.get("current_price_cents") is not None:
                    price_info = f" - Preço: R$ {svc['current_price_cents'] / 100:.2f}"
                kb_lines.append(f"- {svc['name']}: {svc.get('description', '')}{price_info}")
        if prices:
            kb_lines.append("\nPREÇOS VIGENTES:")
            for pr in prices:
                kb_lines.append(
                    f"- Service ID {pr['service_id']}: R$ {pr['price_cents'] / 100:.2f} (vigente de {pr['valid_from']} até {pr['valid_to'] or 'indeterminado'})"
                )
        if faqs:
            kb_lines.append("\nPERGUNTAS FREQUENTES:")
            for faq in faqs:
                kb_lines.append(f"- P: {faq['question']}\n  R: {faq['answer']}")

        knowledge_text = (
            "\n".join(kb_lines) if kb_lines else "Nenhum dado de conhecimento disponível."
        )

        # Build conversation history
        history_lines = []
        for msg in context.conversation_history:
            # Message entity has direction ("inbound"/"outbound") and content
            role = "Lead" if msg.direction == "inbound" else "Assistente"
            history_lines.append(f"{role}: {msg.content}")
        history_text = "\n".join(history_lines) if history_lines else "Sem histórico."

        # Compose full prompt
        full_prompt = (
            f"{system_prompt}\n\n"
            f"--- BASE DE CONHECIMENTO ---\n{knowledge_text}\n\n"
            f"--- HISTÓRICO DA CONVERSA ---\n{history_text}\n\n"
            f"--- DADOS DO LEAD ---\nNome: {context.lead.name}\nStatus: {context.lead.status}\n"
            f"--- FIM DO CONTEXTO ---"
        )

        try:
            response = self._model.generate_content(full_prompt)
            dto = AgentDecisionDTO.model_validate_json(response.text)

            # Map DTO to domain AgentDecision
            action = "handoff" if dto.needs_handoff else "reply"
            return AgentDecision(
                action=action,
                response_text=dto.reply,
                confidence=dto.confidence,
                handoff_reason=dto.reason if dto.needs_handoff else None,
                metadata={"intent": dto.intent, "next_state": dto.next_state},
            )

        except Exception as e:  # noqa: BLE001
            # Degradação graciosa e segura: se o Gemini falhar, aciona o handoff humano imediatamente
            return AgentDecision(
                action="handoff",
                response_text="Entendo perfeitamente. Para lhe dar uma resposta exata e personalizada, vou transferir o seu atendimento para um especialista humano agora mesmo.",
                confidence=0.0,
                handoff_reason=f"Falha de segurança e indisponibilidade do LLM: {e!s}",
                metadata={"intent": "llm_error_fallback"},
            )
