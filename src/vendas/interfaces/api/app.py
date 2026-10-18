from __future__ import annotations

from fastapi import FastAPI

from vendas.interfaces.api.routes.catalog import router as catalog_router
from vendas.interfaces.api.routes.health import router as health_router


def create_app() -> FastAPI:
    app = FastAPI(title="Vendas API")
    app.include_router(health_router)
    app.include_router(catalog_router)
    return app


app = create_app()
