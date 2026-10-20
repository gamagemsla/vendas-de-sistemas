from __future__ import annotations

from collections.abc import Awaitable, Callable

import structlog
from fastapi import FastAPI, Request, Response

from vendas.bootstrap.settings import settings
from vendas.interfaces.api.routes.catalog import router as catalog_router
from vendas.interfaces.api.routes.health import router as health_router

logger = structlog.get_logger()


def create_app() -> FastAPI:
    app = FastAPI(title="Vendas API")

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
    return app


app = create_app()
