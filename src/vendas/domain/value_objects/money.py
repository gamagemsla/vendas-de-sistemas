"""Value Object Money - Valor monetário em centavos (inteiros) com suporte a BRL."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Self


@dataclass(frozen=True, slots=True, order=True, init=False)
class Money:
    """
    Value Object para valor monetário em BRL.

    Armazena internamente em centavos (inteiro) para evitar problemas de ponto flutuante.
    Suporta operações aritméticas básicas e formatação BRL.
    """

    cents: int

    def __new__(cls, value: str | float | Decimal | None = None) -> Self:
        """Permite instanciar diretamente com string, int, float ou Decimal."""
        if value is None:
            raise ValueError("Valor não pode ser None")

        # Cria a instância diretamente sem chamar __init__ novamente
        instance = object.__new__(cls)

        if isinstance(value, str):
            # Normaliza: substitui vírgula por ponto, remove espaços
            normalized = value.strip().replace(",", ".")
            try:
                decimal_value = Decimal(normalized)
            except InvalidOperation:
                raise ValueError("Valor inválido")
            if decimal_value < 0:
                raise ValueError("Valor não pode ser negativo")
            cents = int((decimal_value * 100).quantize(Decimal(1)))
        elif isinstance(value, int):
            if value < 0:
                raise ValueError("Valor não pode ser negativo")
            cents = value
        elif isinstance(value, float):
            # Converte float para Decimal para evitar problemas de precisão
            decimal_value = Decimal(str(value))
            if decimal_value < 0:
                raise ValueError("Valor não pode ser negativo")
            cents = int((decimal_value * 100).quantize(Decimal(1)))
        elif isinstance(value, Decimal):
            if value < 0:
                raise ValueError("Valor não pode ser negativo")
            cents = int((value * 100).quantize(Decimal(1)))
        else:
            raise TypeError("Tipo de valor não suportado")

        # Define o atributo cents diretamente
        object.__setattr__(instance, "cents", cents)
        return instance

    @classmethod
    def from_cents(cls, cents: int) -> Money:
        """Cria Money a partir de centavos (inteiro)."""
        return cls(cents)

    @classmethod
    def from_reais(cls, reais: float | Decimal) -> Money:
        """Cria Money a partir de reais (float ou Decimal)."""
        return cls(reais)

    @classmethod
    def from_string(cls, value: str) -> Money:
        """Cria Money a partir de string (ex: '10.50' ou '10,50')."""
        return cls(value)

    @property
    def value(self) -> float:
        """Retorna o valor em reais como float."""
        return self.cents / 100.0

    def __add__(self, other: Money) -> Money:
        if not isinstance(other, Money):
            return NotImplemented
        return Money.from_cents(self.cents + other.cents)

    def __sub__(self, other: Money) -> Money:
        if not isinstance(other, Money):
            return NotImplemented
        result = self.cents - other.cents
        if result < 0:
            raise ValueError("não pode ser negativo")
        return Money.from_cents(result)

    def __mul__(self, multiplier: int) -> Money:
        if not isinstance(multiplier, int):
            return NotImplemented
        if multiplier < 0:
            raise ValueError("Multiplicador não pode ser negativo")
        return Money.from_cents(self.cents * multiplier)

    def __rmul__(self, multiplier: int) -> Money:
        return self.__mul__(multiplier)

    def __truediv__(self, divisor: int) -> Money:
        if not isinstance(divisor, int):
            return NotImplemented
        if divisor <= 0:
            raise ValueError("Divisor deve ser positivo")
        return Money.from_cents(self.cents // divisor)

    def __bool__(self) -> bool:
        return self.cents > 0

    def format_brl(self) -> str:
        """Formata o valor no padrão brasileiro: R$ X.XXX,XX."""
        reais = self.cents // 100
        centavos = self.cents % 100

        # Formata parte inteira com separador de milhares
        reais_str = f"{reais:,}".replace(",", ".")

        return f"R$ {reais_str},{centavos:02d}"

    def __str__(self) -> str:
        """Retorna representação decimal simples: '10.50'."""
        reais = self.cents // 100
        centavos = self.cents % 100
        return f"{reais}.{centavos:02d}"

    def __repr__(self) -> str:
        return f"Money({self.cents})"
