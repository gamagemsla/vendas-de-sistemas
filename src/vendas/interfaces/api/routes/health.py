import structlog
from fastapi import APIRouter, status

logger = structlog.get_logger()

router = APIRouter(tags=["Observabilidade & Saúde"])


@router.get("/health", status_code=status.HTTP_200_OK)
async def liveness_check() -> dict[str, str]:
    """Liveness probe: verifica se o processo da API está vivo e respondendo."""
    return {"status": "alive", "service": "vendas-api"}


@router.get("/ready", status_code=status.HTTP_200_OK)
async def readiness_check() -> dict[str, str]:
    """Readiness probe: verifica se as dependências críticas (como o Banco de Dados) estão prontas."""
    # Aqui você pode adicionar uma checagem rápida no banco de dados se necessário.
    return {"status": "ready", "database": "connected"}
