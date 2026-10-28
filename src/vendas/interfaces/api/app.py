from __future__ import annotations

from collections.abc import Awaitable, Callable
from time import time
from typing import Final

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from vendas.bootstrap.container import container
from vendas.bootstrap.logging import clear_correlation_id, set_correlation_id
from vendas.bootstrap.settings import settings
from vendas.domain.ports.auth import AuthPort
from vendas.interfaces.api.deps import get_channel_state_port, get_clock, get_job_queue, get_uow
from vendas.interfaces.api.routes.catalog import router as catalog_router
from vendas.interfaces.api.routes.health import router as health_router
from vendas.interfaces.api.webhooks.whatsapp import router as whatsapp_webhook_router

logger = structlog.get_logger()

# In-memory rate limiting storage: IP -> list of request timestamps
_rate_limit_store: dict[str, list[float]] = {}
_RATE_LIMIT_LOCK: Final = object()  # Simple lock object for thread safety


async def rate_limit_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Middleware de rate limiting em memória por IP."""
    # Pular rate limiting para rotas de health/docs
    if request.url.path in ("/health", "/ready", "/metrics", "/docs", "/openapi.json"):
        return await call_next(request)

    client_ip = request.client.host if request.client else "unknown"
    current_time = time()
    window_start = current_time - settings.RATE_LIMIT_PERIOD_SECONDS

    # Limpar timestamps antigos e verificar limite
    if client_ip in _rate_limit_store:
        # Filtrar apenas timestamps dentro da janela
        _rate_limit_store[client_ip] = [
            ts for ts in _rate_limit_store[client_ip] if ts > window_start
        ]
        request_count = len(_rate_limit_store[client_ip])
    else:
        _rate_limit_store[client_ip] = []
        request_count = 0

    if request_count >= settings.RATE_LIMIT_MAX_CALLS:
        logger.warning(
            "rate_limit_exceeded",
            client_ip=client_ip,
            path=request.url.path,
            method=request.method,
            limit=settings.RATE_LIMIT_MAX_CALLS,
            period_seconds=settings.RATE_LIMIT_PERIOD_SECONDS,
        )
        return Response(
            content='{"detail":"Rate limit exceeded. Too many requests."}',
            status_code=429,
            media_type="application/json",
            headers={"Retry-After": str(settings.RATE_LIMIT_PERIOD_SECONDS)},
        )

    # Registrar esta requisição
    _rate_limit_store[client_ip].append(current_time)

    return await call_next(request)


async def correlation_id_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Middleware que garante correlation_id em todos os logs e no header de resposta."""
    incoming_cid = request.headers.get("X-Correlation-ID")
    cid = set_correlation_id(incoming_cid)
    response: Response | None = None
    try:
        response = await call_next(request)
        return response
    finally:
        # Guarda defensiva: response pode ser None se exceção ocorrer antes da criação
        if response is not None:
            response.headers["X-Correlation-ID"] = cid
        clear_correlation_id()


def create_app(auth_port: AuthPort | None = None) -> FastAPI:
    app = FastAPI(title="Vendas API")

    # CORS Middleware (deve ser um dos primeiros para adicionar headers a todas as respostas)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ALLOW_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Middleware de Correlation ID (mais externo)
    app.middleware("http")(correlation_id_middleware)

    # Middleware de Rate Limiting (após CORS, antes de kill_switch)
    app.middleware("http")(rate_limit_middleware)

    @app.middleware("http")
    async def kill_switch_guard(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Rotas de observabilidade e documentação sempre passam
        if request.url.path in ("/health", "/ready", "/metrics", "/docs", "/openapi.json"):
            return await call_next(request)

        # Permitir métodos de leitura (GET, HEAD, OPTIONS)
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return await call_next(request)

        # Bloquear métodos mutantes se KILL_SWITCH ativo
        if settings.KILL_SWITCH:
            logger.warning(
                "kill_switch_bloqueio_requisicao",
                path=request.url.path,
                method=request.method,
            )
            return Response(
                content='{"detail":"Sistema em pausa de seguranca (KILL_SWITCH ativo)"}',
                status_code=503,
                media_type="application/json",
                headers={"Retry-After": "30"},
            )

        return await call_next(request)

    app.include_router(health_router)
    app.include_router(catalog_router)
    app.include_router(whatsapp_webhook_router)

    # Vincula porta de autenticação ao state da aplicação, se fornecida
    if auth_port is not None:
        app.state.auth_port = auth_port

    # Override webhook dependencies with concrete implementations from container
    app.dependency_overrides[get_uow] = lambda: container.uow
    app.dependency_overrides[get_job_queue] = lambda: container.job_queue
    app.dependency_overrides[get_clock] = lambda: container.clock
    app.dependency_overrides[get_channel_state_port] = lambda: container.channel_state_port

    return app


app = create_app(auth_port=container.auth_port)
