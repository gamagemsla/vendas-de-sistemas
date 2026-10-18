import re
from collections.abc import MutableMapping
from typing import Any

import structlog


def mask_sensitive_data(
    logger: Any, method_name: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    """Mascara automaticamente telefones e e-mails em qualquer log estruturado."""
    for key, value in event_dict.items():
        if isinstance(value, str):
            if "phone" in key.lower():
                # Ex: +5511999999999 vira +5511****9999
                event_dict[key] = re.sub(r"(\+\d{2}\d{2})\d{4,5}(\d{4})", r"\1****\2", value)
            elif "email" in key.lower():
                parts = value.split("@")
                if len(parts) == 2:
                    event_dict[key] = f"{parts[0][:2]}***@{parts[1]}"
    return event_dict


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
