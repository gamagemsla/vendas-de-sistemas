"""Exceções de domínio para erros de provedores externos."""


class ProviderError(Exception):
    """Erro genérico de provedor externo."""


class ProviderUnavailable(ProviderError):
    """Provedor indisponível (erro de rede, timeout, 5xx)."""


class ProviderRateLimited(ProviderError):
    """Provedor retornou 429 (rate limit)."""


class BudgetExceededError(ProviderError):
    """Orçamento diário excedido para o provedor."""
