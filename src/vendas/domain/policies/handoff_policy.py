"""HandoffPolicy - Verifica gatilhos de transferência para humano."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import ClassVar


class HandoffTrigger(str, Enum):
    REQUEST_HUMAN = "request_human"
    MENTIONS_PRICE = "mentions_price"
    MENTIONS_CONTRACT = "mentions_contract"
    HOSTILE_TONE = "hostile_tone"
    REPEATED_QUESTIONS = "repeated_questions"
    TECHNICAL_QUESTION = "technical_question"
    LEGAL_COMPLIANCE = "legal_compliance"


@dataclass(frozen=True, slots=True)
class HandoffResult:
    should_handoff: bool
    triggers: list[HandoffTrigger]
    confidence: float
    matched_patterns: list[str]
    original_text: str


class HandoffPolicy:
    REQUEST_HUMAN_PATTERNS: ClassVar[list[str]] = [
        r"\b(quero\s+falar\s+com\s+(um\s+)?(humano|pessoa|atendente|alguém|alguem))\b",
        r"\b(falar\s+com\s+(um\s+)?(humano|pessoa|atendente|alguém|alguem))\b",
        r"\b(transferir\s+para\s+(um\s+)?(humano|pessoa|atendente))\b",
        r"\b(atendente\s+humano)\b",
        r"\b(operador\s+humano)\b",
        r"\b(não\s+é\s+rob[oô]|nao\s+eh\s+robo)\b",
        r"\b(é\s+um\s+rob[oô]|eh\s+um\s+robo)\b",
        r"\b(chatbot|bot|rob[oô])\b.*\b(ruim|péssimo|horrível|inútil|inutil)\b",
    ]

    PRICE_PATTERNS: ClassVar[list[str]] = [
        r"\b(preço|preco|preços|precos|valor|valores|custo|custos|investimento)\b",
        r"\b(quanto\s+custa|qual\s+o\s+(preço|preco|valor|preços|precos|valor|valores))\b",
        r"\b(orçamento|orcamento)\b",
        r"\b(tabela\s+de\s+(preço|preco|preços|precos|valor|valores))\b",
        r"\b(desconto|promoção|promocao)\b",
        r"\b(pagamento|parcelar|parcelamento)\b",
        r"\b(roi|retorno\s+sobre\s+investimento)\b",
    ]

    CONTRACT_PATTERNS: ClassVar[list[str]] = [
        r"\b(contrato|proposta|proposta\s+comercial)\b",
        r"\b(fechar|fechamento|assinatura|assinar)\b",
        r"\b(termo|termos|condições|condicoes)\b",
        r"\b(cláusula|clausula|aditivo)\b",
        r"\b(renovação|renovacao|vigência|vigencia)\b",
        r"\b(mandar|enviar)\s+(a\s+)?(proposta|contrato)\b",
    ]

    HOSTILE_PATTERNS: ClassVar[list[str]] = [
        r"\b(idiota|imbecil|burro|estúpido|estupido|babaca)\b",
        r"\b(merda|porra|caralho|puta|fdp)\b",
        r"\b(lixo|porcaria|horrível|horrivel|péssimo|pessimo)\b",
        r"\b(vai\s+tomar|vá\s+tomar|foda-se|fodase)\b",
        r"\b(ridículo|ridiculo|absurdo|inaceitável|inaceitavel)\b",
        r"\b(processar|processo|advogado|procon|reclamação|reclamacao)\b",
        r"\b(cancelar\s+tudo|quero\s+meus\s+dados|lgpd|excluir\s+dados)\b",
    ]

    TECHNICAL_PATTERNS: ClassVar[list[str]] = [
        r"\b(api|integração|integracao|webhook|endpoint)\b",
        r"\b(arquitetura|infraestrutura|deploy|kubernetes|docker)\b",
        r"\b(segurança|seguranca|lgpd|compliance|auditoria)\b",
        r"\b(sla|disponibilidade|uptime|latência|latencia)\b",
        r"\b(migração|migracao|onboarding|implementação|implementacao)\b",
        r"\b(white\s*label|whitelabel|customizaçao|customização)\b",
    ]

    LEGAL_PATTERNS: ClassVar[list[str]] = [
        r"\b(contrato|jurídico|juridico|advogado|jurídico)\b",
        r"\b(cláusula|clausula|termo|aditivo|rescisão|rescisao)\b",
        r"\b(multa|indenização|indenizacao|danos|responsabilidade)\b",
        r"\b(foro|jurisdição|jurisdicao|lei|legislação|legislacao)\b",
        r"\b(anvisa|banco\s+central|cvm|susep|procon)\b",
    ]

    def __init__(
        self,
        request_human_patterns: list[str] | None = None,
        price_patterns: list[str] | None = None,
        contract_patterns: list[str] | None = None,
        hostile_patterns: list[str] | None = None,
        technical_patterns: list[str] | None = None,
        legal_patterns: list[str] | None = None,
        confidence_threshold: float = 0.7,
        repeated_questions_threshold: int = 3,
    ):
        self._request_human_patterns = [
            re.compile(p, re.IGNORECASE)
            for p in (request_human_patterns or self.REQUEST_HUMAN_PATTERNS)
        ]
        self._price_patterns = [
            re.compile(p, re.IGNORECASE) for p in (price_patterns or self.PRICE_PATTERNS)
        ]
        self._contract_patterns = [
            re.compile(p, re.IGNORECASE) for p in (contract_patterns or self.CONTRACT_PATTERNS)
        ]
        self._hostile_patterns = [
            re.compile(p, re.IGNORECASE) for p in (hostile_patterns or self.HOSTILE_PATTERNS)
        ]
        self._technical_patterns = [
            re.compile(p, re.IGNORECASE) for p in (technical_patterns or self.TECHNICAL_PATTERNS)
        ]
        self._legal_patterns = [
            re.compile(p, re.IGNORECASE) for p in (legal_patterns or self.LEGAL_PATTERNS)
        ]
        self._confidence_threshold = confidence_threshold
        self._repeated_questions_threshold = repeated_questions_threshold

    def _match_patterns(self, text: str, patterns: list[re.Pattern[str]]) -> list[str]:
        matched = []
        normalized = text.lower().strip()
        for pattern in patterns:
            match = pattern.search(normalized)
            if match:
                matched.append(match.group(0))
        return matched

    def check(
        self,
        text: str,
        repeated_questions_count: int = 0,
        conversation_history: list[str] | None = None,
    ) -> HandoffResult:
        if not text or not text.strip():
            return HandoffResult(
                should_handoff=False,
                triggers=[],
                confidence=0.0,
                matched_patterns=[],
                original_text=text,
            )

        triggers = []
        matched_patterns = []

        matched = self._match_patterns(text, self._request_human_patterns)
        if matched:
            triggers.append(HandoffTrigger.REQUEST_HUMAN)
            matched_patterns.extend(matched)

        matched = self._match_patterns(text, self._price_patterns)
        if matched:
            triggers.append(HandoffTrigger.MENTIONS_PRICE)
            matched_patterns.extend(matched)

        matched = self._match_patterns(text, self._contract_patterns)
        if matched:
            triggers.append(HandoffTrigger.MENTIONS_CONTRACT)
            matched_patterns.extend(matched)

        matched = self._match_patterns(text, self._hostile_patterns)
        if matched:
            triggers.append(HandoffTrigger.HOSTILE_TONE)
            matched_patterns.extend(matched)

        matched = self._match_patterns(text, self._technical_patterns)
        if matched:
            triggers.append(HandoffTrigger.TECHNICAL_QUESTION)
            matched_patterns.extend(matched)

        matched = self._match_patterns(text, self._legal_patterns)
        if matched:
            triggers.append(HandoffTrigger.LEGAL_COMPLIANCE)
            matched_patterns.extend(matched)

        if repeated_questions_count >= self._repeated_questions_threshold:
            triggers.append(HandoffTrigger.REPEATED_QUESTIONS)
            matched_patterns.append(f"repeated_questions:{repeated_questions_count}")

        trigger_confidences = {
            HandoffTrigger.REQUEST_HUMAN: 0.95,
            HandoffTrigger.MENTIONS_PRICE: 0.8,
            HandoffTrigger.MENTIONS_CONTRACT: 0.8,
            HandoffTrigger.HOSTILE_TONE: 0.9,
            HandoffTrigger.REPEATED_QUESTIONS: 0.75,
            HandoffTrigger.TECHNICAL_QUESTION: 0.7,
            HandoffTrigger.LEGAL_COMPLIANCE: 0.85,
        }

        if triggers:
            confidence = sum(trigger_confidences[t] for t in triggers) / len(triggers)
        else:
            confidence = 0.0

        should_handoff = confidence >= self._confidence_threshold and len(triggers) > 0

        return HandoffResult(
            should_handoff=should_handoff,
            triggers=triggers,
            confidence=confidence,
            matched_patterns=matched_patterns,
            original_text=text,
        )

    def should_handoff(self, text: str, repeated_questions_count: int = 0) -> bool:
        return self.check(text, repeated_questions_count).should_handoff
