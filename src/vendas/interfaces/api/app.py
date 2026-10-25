from __future__ import annotations

from collections.abc import Awaitable, Callable

import structlog
from fastapi import FastAPI, Request, Response

from vendas.bootstrap.container import container
from vendas.bootstrap.logging import clear_correlation_id, set_correlation_id
from vendas.bootstrap.settings import settings
from vendas.domain.ports.auth import AuthPort
from vendas.interfaces.api.routes.catalog import router as catalog_router
from vendas.interfaces.api.routes.health import router as health_router

logger = structlog.get_logger()


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

    # Middleware de Correlation ID (mais externo)
    app.middleware("http")(correlation_id_middleware)

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

    # Vincula porta de autenticação ao state da aplicação, se fornecida
    if auth_port is not None:
        app.state.auth_port = auth_port

    return app


app = create_app(auth_port=container.auth_port)
