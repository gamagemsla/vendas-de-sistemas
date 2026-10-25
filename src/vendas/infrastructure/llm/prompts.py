"""Prompts versionados e construção do prompt para o agente Gemini."""

from __future__ import annotations

from typing import Any

from vendas.domain.ports import AgentContext, Message

PROMPT_VERSION = "1.0.0"

SYSTEM_PROMPT = (
    "Você é um assistente de prospecção B2B altamente qualificado. "
    "Responda apenas com base nas regras comerciais e dados fornecidos. "
    "Nunca prometa descontos ou prazos sem aprovação humana."
)


def _format_knowledge_base(kb: dict[str, Any]) -> str:
    """Formata a base de conhecimento para inclusão no prompt."""
    lines: list[str] = []
    services = kb.get("services", [])
    prices = kb.get("prices", [])
    faqs = kb.get("faqs", [])

    if services:
        lines.append("SERVIÇOS DISPONÍVEIS:")
        for svc in services:
            price_info = ""
            if svc.get("current_price_cents") is not None:
                price_info = f" - Preço: R$ {svc['current_price_cents'] / 100:.2f}"
            lines.append(f"- {svc['name']}: {svc.get('description', '')}{price_info}")

    if prices:
        lines.append("\nPREÇOS VIGENTES:")
        for pr in prices:
            lines.append(
                f"- Service ID {pr['service_id']}: R$ {pr['price_cents'] / 100:.2f} "
                f"(vigente de {pr['valid_from']} até {pr['valid_to'] or 'indeterminado'})"
            )

    if faqs:
        lines.append("\nPERGUNTAS FREQUENTES:")
        for faq in faqs:
            lines.append(f"- P: {faq['question']}\n  R: {faq['answer']}")

    return "\n".join(lines) if lines else "Nenhum dado de conhecimento disponível."


def _format_history(history: list[Message]) -> str:
    """Formata o histórico da conversa."""
    if not history:
        return "Sem histórico."
    lines = []
    for msg in history:
        role = "Lead" if msg.direction == "inbound" else "Assistente"
        lines.append(f"{role}: {msg.content}")
    return "\n".join(lines)


def build_gemini_prompt(context: AgentContext) -> str:
    """Constrói o prompt completo enviado ao modelo Gemini."""
    knowledge_text = _format_knowledge_base(context.knowledge_base)
    history_text = _format_history(list(context.conversation_history))

    lead = context.lead
    lead_name = getattr(lead, "name", "Desconhecido")
    lead_status = getattr(lead, "status", "UNKNOWN")

    prompt = (
        f"{SYSTEM_PROMPT}\n\n"
        f"--- BASE DE CONHECIMENTO ---\n{knowledge_text}\n\n"
        f"--- HISTÓRICO DA CONVERSA ---\n{history_text}\n\n"
        f"--- DADOS DO LEAD ---\nNome: {lead_name}\nStatus: {lead_status}\n"
        f"--- FIM DO CONTEXTO ---"
    )
    return prompt
