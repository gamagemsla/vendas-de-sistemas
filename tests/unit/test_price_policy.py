"""Testes unitários para PriceValidationPolicy."""

from decimal import Decimal

from vendas.domain.policies.price_policy import PriceValidationPolicy, PriceValidationResult


def test_price_policy_no_prices_in_response():
    policy = PriceValidationPolicy()
    kb = {"services": []}
    result = policy.validate("Olá, tudo bem?", kb)
    assert isinstance(result, PriceValidationResult)
    assert result.is_valid is True
    assert result.extracted_prices == []


def test_price_policy_matching_price():
    policy = PriceValidationPolicy()
    kb = {"services": [{"price": "100.00"}]}
    result = policy.validate("O valor é R$ 100,00", kb)
    assert result.is_valid is True
    assert Decimal("100.00") in result.extracted_prices


def test_price_policy_mismatch_price():
    policy = PriceValidationPolicy()
    kb = {"services": [{"price": "100.00"}]}
    result = policy.validate("O valor é R$ 200,00", kb)
    assert result.is_valid is False
    assert len(result.mismatches) == 1
    assert result.mismatches[0].mentioned == Decimal("200.00")
    assert result.mismatches[0].expected == Decimal("100.00")


def test_price_policy_multiple_prices_one_mismatch():
    policy = PriceValidationPolicy()
    kb = {"services": [{"price": "100.00"}, {"price": "150.00"}]}
    result = policy.validate("Preços: R$ 100,00 e R$ 300,00", kb)
    assert result.is_valid is False
    assert any(m.mentioned == Decimal("300.00") for m in result.mismatches)


def test_price_policy_tolerance():
    policy = PriceValidationPolicy(tolerance=Decimal("0.05"))
    kb = {"services": [{"price": "100.00"}]}
    # 100.02 dentro da tolerância
    result = policy.validate("Valor R$ 100,02", kb)
    assert result.is_valid is True
