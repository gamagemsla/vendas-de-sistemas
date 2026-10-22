import re
from collections.abc import MutableMapping
from typing import Any, cast

import structlog

_SENSITIVE_KEY_PATTERNS = (
    "phone",
    "email",
    "token",
    "password",
    "key",
    "secret",
)


def _mask_value(value: str) -> str:
    """Aplica mascaramento a um valor string se parecer telefone ou e-mail."""
    # Telefone E.164: +5511999999999 -> +5511****9999
    if re.match(r"^\+\d{10,15}$", value):
        return re.sub(r"(\+\d{2}\d{2})\d{4,5}(\d{4})", r"\1****\2", value)
    # E-mail simples
    if "@" in value and not value.startswith("@"):
        parts = value.split("@")
        if len(parts) == 2:
            return f"{parts[0][:2]}***@{parts[1]}"
    # Genérico: mostra apenas primeiros 2 e últimos 2 caracteres
    if len(value) > 4:
        return f"{value[:2]}****{value[-2:]}"
    return "****"


def _recursive_mask(obj: Any, memo: set[int] | None = None) -> Any:
    """Percorre dicts e listas recursivamente mascarando chaves sensíveis com proteção contra loops."""
    if memo is None:
        memo = set()

    obj_id = id(obj)
    if obj_id in memo:
        return "<circular reference>"

    if isinstance(obj, dict):
        memo.add(obj_id)
        masked: dict[str, Any] = {}
        for k, v in obj.items():
            if isinstance(k, str) and any(p in k.lower() for p in _SENSITIVE_KEY_PATTERNS):
                if isinstance(v, str):
                    masked[k] = _mask_value(v)
                else:
                    masked[k] = _mask_value(str(v))
            else:
                masked[k] = _recursive_mask(v, memo)
        memo.remove(obj_id)
        return masked

    if isinstance(obj, list):
        memo.add(obj_id)
        result = [_recursive_mask(item, memo) for item in obj]
        memo.remove(obj_id)
        return result

    return obj


def mask_sensitive_data(
    logger: Any, method_name: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    """Mascara automaticamente dados sensíveis em qualquer log estruturado, incluindo aninhados."""
    return cast(MutableMapping[str, Any], _recursive_mask(event_dict))


import uuid


def set_correlation_id(correlation_id: str | None = None) -> str:
    """Define o correlation_id no contextvars do structlog.
    Se não informado, gera um UUID v4.
    Retorna o correlation_id utilizado.
    """
    cid = correlation_id or str(uuid.uuid4())
    structlog.contextvars.bind_contextvars(correlation_id=cid)
    return cid


def get_correlation_id() -> str | None:
    """Obtém o correlation_id atual do contextvars, se houver."""
    return structlog.contextvars.get_contextvars().get("correlation_id")


def clear_correlation_id() -> None:
    """Remove o correlation_id do contextvars."""
    structlog.contextvars.unbind_contextvars("correlation_id")


def configure_logging() -> None:
    """Configura o structlog para saída JSON com correlation ID e mascaramento."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            mask_sensitive_data,
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.PrintLoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO
        cache_logger_on_first_use=True,
    )
