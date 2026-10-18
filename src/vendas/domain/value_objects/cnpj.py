"""Value Object Cnpj - CNPJ brasileiro com validação de dígitos verificadores."""

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Cnpj:
    """
    Value Object para CNPJ brasileiro.

    Valida os dígitos verificadores matematicamente.
    Armazena apenas dígitos (14 caracteres).
    """

    value: str

    def __post_init__(self) -> None:
        normalized = self._normalize(self.value)
        self._validate(normalized)
        object.__setattr__(self, "value", normalized)

    @staticmethod
    def _normalize(raw: str | None) -> str:
        """Remove formatação e retorna apenas dígitos."""
        if raw is None:
            raise ValueError("CNPJ não pode ser None")

        # Remove tudo que não é dígito
        digits = re.sub(r"\D", "", raw.strip())

        if len(digits) != 14:
            raise ValueError("CNPJ deve ter 14 dígitos")

        return digits

    @staticmethod
    def _validate(digits: str) -> None:
        """Valida os dígitos verificadores do CNPJ."""
        # Rejeita CNPJs com todos os dígitos iguais
        if len(set(digits)) == 1:
            raise ValueError("CNPJ inválido")

        # Calcula primeiro dígito verificador
        weights1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        sum1 = sum(int(digits[i]) * weights1[i] for i in range(12))
        remainder1 = sum1 % 11
        dv1 = 0 if remainder1 < 2 else 11 - remainder1

        if int(digits[12]) != dv1:
            raise ValueError("CNPJ inválido")

        # Calcula segundo dígito verificador
        weights2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        sum2 = sum(int(digits[i]) * weights2[i] for i in range(13))
        remainder2 = sum2 % 11
        dv2 = 0 if remainder2 < 2 else 11 - remainder2

        if int(digits[13]) != dv2:
            raise ValueError("CNPJ inválido")

    @property
    def formatted(self) -> str:
        """Retorna o CNPJ formatado: XX.XXX.XXX/XXXX-XX."""
        v = self.value
        return f"{v[:2]}.{v[2:5]}.{v[5:8]}/{v[8:12]}-{v[12:]}"

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"Cnpj('{self.value}')"
