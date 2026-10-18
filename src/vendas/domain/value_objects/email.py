"""Value Object Email - Validação básica de formato de e-mail."""

import re
from dataclasses import dataclass

# Regex para validação de e-mail (mais estrita)
EMAIL_REGEX = re.compile(
    r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+"
    r"@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?"
    r"(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+$"
)


@dataclass(frozen=True, slots=True)
class Email:
    """
    Value Object para e-mail.

    Validação básica de formato e normalização para lowercase.
    """

    value: str

    def __post_init__(self) -> None:
        normalized = self._normalize(self.value)
        self._validate(normalized)
        object.__setattr__(self, "value", normalized)

    @staticmethod
    def _normalize(raw: str | None) -> str:
        """Normaliza o e-mail para lowercase."""
        if raw is None:
            raise ValueError("E-mail inválido")

        return raw.strip().lower()

    @staticmethod
    def _validate(normalized: str) -> None:
        """Valida o formato do e-mail."""
        if not normalized:
            raise ValueError("E-mail inválido")

        # Verifica se tem exatamente um @
        if normalized.count("@") != 1:
            raise ValueError("E-mail inválido")

        local, domain = normalized.split("@", 1)

        # Parte local não pode ser vazia
        if not local:
            raise ValueError("E-mail inválido")

        # Domínio não pode ser vazio
        if not domain:
            raise ValueError("E-mail inválido")

        # Parte local não pode começar ou terminar com ponto
        if local.startswith(".") or local.endswith("."):
            raise ValueError("E-mail inválido")

        # Parte local não pode ter pontos consecutivos
        if ".." in local:
            raise ValueError("E-mail inválido")

        # Domínio deve ter pelo menos um ponto (TLD)
        if "." not in domain:
            raise ValueError("E-mail inválido")

        # Domínio não pode começar ou terminar com ponto ou hífen
        if domain.startswith((".", "-")) or domain.endswith((".", "-")):
            raise ValueError("E-mail inválido")

        # Não pode ter pontos consecutivos no domínio
        if ".." in domain:
            raise ValueError("E-mail inválido")

        # Cada label do domínio não pode ter mais de 63 caracteres
        for label in domain.split("."):
            if not label or len(label) > 63:
                raise ValueError("E-mail inválido")

        # Validação final com regex
        if not EMAIL_REGEX.match(normalized):
            raise ValueError("E-mail inválido")

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"Email('{self.value}')"
