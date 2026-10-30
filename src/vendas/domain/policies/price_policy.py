"""PriceValidationPolicy - Valida preços mencionados na resposta da IA contra a Knowledge Base."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any


@dataclass(frozen=True, slots=True)
class PriceMismatch:
    """Representa um preço divergente encontrado."""

    mentioned: Decimal
    expected: Decimal
    context: str


@dataclass(frozen=True, slots=True)
class PriceValidationResult:
    """Resultado da validação de preços."""

    is_valid: bool
    mismatches: list[PriceMismatch]
    extracted_prices: list[Decimal]


class PriceValidationPolicy:
    """Política para validar valores monetários citados pela IA."""

    # Regex para capturar valores monetários em formatos brasileiros e internacionais
    _PRICE_REGEX = re.compile(
        r"""
        (?:R\$\s*)?                # prefixo opcional R$
        (?:\d{1,3}(?:\.\d{3})*     # milhares com ponto
        (?:,\d{2})?                # centavos com vírgula
        |\d+(?:,\d{2})?            # ou número simples com vírgula
        |\d+(?:\.\d{2})?)          # ou número com ponto decimal
        """,
        re.VERBOSE,
    )

    def __init__(self, tolerance: Decimal = Decimal("0.01")) -> None:
        self._tolerance = tolerance

    def _extract_prices(self, text: str) -> list[Decimal]:
        """Extrai todos os valores monetários do texto."""
        prices: list[Decimal] = []
        for match in self._PRICE_REGEX.finditer(text):
            raw = match.group(0).replace("R$", "").strip()
            # Normaliza para decimal: substitui ponto de milhar, vírgula decimal
            normalized = raw.replace(".", "").replace(",", ".")
            try:
                value = Decimal(normalized)
                if value > 0:
                    prices.append(value)
            except InvalidOperation:
                continue
        return prices

    def _get_kb_prices(self, kb_preview: dict[str, Any]) -> list[Decimal]:
        """Obtém preços esperados da base de conhecimento (preview)."""
        prices: list[Decimal] = []
        # O preview pode conter lista de serviços com preços
        services = kb_preview.get("services") or kb_preview.get("data") or []
        for svc in services:
            # Estrutura esperada: {"price": "123.45", ...} ou {"prices": [{"value": "..."}]}
            if isinstance(svc, dict):
                if "price" in svc:
                    try:
                        prices.append(Decimal(str(svc["price"]).replace(",", ".")))
                    except InvalidOperation:
                        pass
                if "prices" in svc and isinstance(svc["prices"], list):
                    for p in svc["prices"]:
                        if isinstance(p, dict) and "value" in p:
                            try:
                                prices.append(Decimal(str(p["value"]).replace(",", ".")))
                            except InvalidOperation:
                                pass
        return prices

    def validate(self, response_text: str, kb_preview: dict[str, Any]) -> PriceValidationResult:
        """Valida se os preços citados na resposta batem com a KB."""
        if not response_text:
            return PriceValidationResult(is_valid=True, mismatches=[], extracted_prices=[])

        mentioned = self._extract_prices(response_text)
        if not mentioned:
            return PriceValidationResult(is_valid=True, mismatches=[], extracted_prices=[])

        expected_prices = self._get_kb_prices(kb_preview)
        if not expected_prices:
            # Sem preços na KB para comparar -> não bloqueia
            return PriceValidationResult(is_valid=True, mismatches=[], extracted_prices=mentioned)

        mismatches: list[PriceMismatch] = []
        for m in mentioned:
            # Verifica se existe algum preço esperado próximo (dentro da tolerância)
            match_found = any(abs(m - e) <= self._tolerance for e in expected_prices)
            if not match_found:
                # Pega o esperado mais próximo para relatório
                closest = min(expected_prices, key=lambda e: abs(m - e))
                mismatches.append(
                    PriceMismatch(
                        mentioned=m,
                        expected=closest,
                        context=response_text[:200],
                    )
                )

        is_valid = len(mismatches) == 0
        return PriceValidationResult(
            is_valid=is_valid,
            mismatches=mismatches,
            extracted_prices=mentioned,
        )
