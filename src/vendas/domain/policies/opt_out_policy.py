import enum
from dataclasses import dataclass
from typing import Any, ClassVar


class OptOutIntent(str, enum.Enum):
    EXPLICIT_STOP = "explicit_stop"
    NO_INTEREST = "no_interest"
    UNSUBSCRIBE = "unsubscribe"
    GENERIC_OPT_OUT = "generic_opt_out"
    NONE = "none"


@dataclass
class OptOutResult:
    intent: OptOutIntent
    confidence: float = 0.0
    matched_pattern: str | None = None
    original_text: str | None = None
    reason: str | None = None

    @property
    def is_opt_out(self) -> bool:
        """Retorna True se a intenção é de opt-out (não NONE)."""
        return self.intent != OptOutIntent.NONE


class OptOutPolicy:
    """Política pura de domínio para detecção de intenções de saída (opt-out) e supressão."""

    # Padrões para EXPLICIT_STOP (confidence 0.95)
    EXPLICIT_STOP_PATTERNS: ClassVar[tuple[str, ...]] = (
        "sair",
        "parar",
        "pare",
        "cancelar",
    )

    # Padrões para NO_INTEREST (confidence 0.9)
    NO_INTEREST_PATTERNS: ClassVar[tuple[str, ...]] = (
        "não tenho interesse",
        "nao tenho interesse",
        "sem interesse",
        "não me interessa",
        "nao me interessa",
        "não quero saber",
        "nao quero saber",
        "não preciso",
        "nao preciso",
        "já tenho",
        "ja tenho",
        "não vou comprar",
        "nao vou comprar",
    )

    # Padrões para UNSUBSCRIBE (confidence 0.9) - mais específicos, verificados antes
    UNSUBSCRIBE_PATTERNS: ClassVar[tuple[str, ...]] = (
        "descadastrar",
        "remover da lista",
        "não quero receber mais",
        "nao quero receber mais",
        "parar de receber",
        "cancelar cadastro",
    )

    # Padrões para GENERIC_OPT_OUT (confidence 0.7)
    GENERIC_OPT_OUT_PATTERNS: ClassVar[tuple[str, ...]] = (
        "não quero",
        "nao quero",
    )

    # Falsos positivos - devem retornar NONE
    FALSE_POSITIVES: ClassVar[tuple[str, ...]] = (
        "não quero parar",
        "nao quero parar",
        "não quero sair",
        "nao quero sair",
        "quero continuar",
        "não me tire",
        "nao me tire",
        "mantenha-me",
        "mantenha me",
        "mantenha meu",
        "continua mandando",
    )

    def detect(self, text: str | None) -> OptOutResult:
        """Analisa o texto buscando intenções de opt-out, considerando falsos positivos."""
        if not text or not text.strip():
            return OptOutResult(
                intent=OptOutIntent.NONE,
                confidence=0.0,
                original_text=text,
            )

        text_lower = text.lower().strip()

        # Tratamento de falsos positivos (ex: "não quero parar" significa continuar)
        for fp in self.FALSE_POSITIVES:
            if fp in text_lower:
                return OptOutResult(
                    intent=OptOutIntent.NONE,
                    confidence=0.0,
                    matched_pattern="false_positive",
                    original_text=text,
                    reason="False positive detected",
                )

        # Verifica UNSUBSCRIBE primeiro (padrões mais específicos)
        for pattern in self.UNSUBSCRIBE_PATTERNS:
            if pattern in text_lower:
                return OptOutResult(
                    intent=OptOutIntent.UNSUBSCRIBE,
                    confidence=0.9,
                    matched_pattern=pattern,
                    original_text=text,
                    reason=f"Unsubscribe pattern matched: {pattern}",
                )

        # Verifica NO_INTEREST
        for pattern in self.NO_INTEREST_PATTERNS:
            if pattern in text_lower:
                return OptOutResult(
                    intent=OptOutIntent.NO_INTEREST,
                    confidence=0.9,
                    matched_pattern=pattern,
                    original_text=text,
                    reason=f"No interest pattern matched: {pattern}",
                )

        # Verifica EXPLICIT_STOP
        for pattern in self.EXPLICIT_STOP_PATTERNS:
            if pattern in text_lower:
                return OptOutResult(
                    intent=OptOutIntent.EXPLICIT_STOP,
                    confidence=0.95,
                    matched_pattern=pattern,
                    original_text=text,
                    reason=f"Explicit stop keyword matched: {pattern}",
                )

        # Verifica GENERIC_OPT_OUT (menor prioridade)
        for pattern in self.GENERIC_OPT_OUT_PATTERNS:
            if pattern in text_lower:
                return OptOutResult(
                    intent=OptOutIntent.GENERIC_OPT_OUT,
                    confidence=0.7,
                    matched_pattern=pattern,
                    original_text=text,
                    reason=f"Generic opt-out pattern matched: {pattern}",
                )

        return OptOutResult(
            intent=OptOutIntent.NONE,
            confidence=0.0,
            original_text=text,
        )

    def is_opt_out(self, text: str | None) -> bool:
        """Retorna True se o texto representa um pedido claro de opt-out."""
        result = self.detect(text)
        return result.is_opt_out

    @staticmethod
    def detects_opt_out(text: str | None) -> bool:
        """Método estático de compatibilidade para os comandos de aplicação."""
        policy = OptOutPolicy()
        return policy.is_opt_out(text)

    @staticmethod
    def is_suppressed(lead: Any) -> bool:
        """Verifica se o lead está com status terminal de opt-out."""
        return getattr(lead, "status", None) == "OPTED_OUT"
