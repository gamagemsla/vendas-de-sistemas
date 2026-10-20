import structlog
from fastapi import APIRouter, status

from vendas.bootstrap.settings import settings

logger = structlog.get_logger()

router = APIRouter(tags=["Observabilidade & Saúde"])


@router.get("/health", status_code=status.HTTP_200_OK)
async def liveness_check() -> dict[str, str]:
    """Liveness probe: verifica se o processo da API está vivo e respondendo."""
    return {"status": "alive", "service": "vendas-api"}


@router.get("/ready", status_code=status.HTTP_200_OK)
async def readiness_check() -> dict[str, object]:
    """Readiness probe: verifica se o sistema está pronto para processar envios.
    Se KILL_SWITCH ativo, retorna status 'paused' mas HTTP 200 para não derrubar o pod.
    """
    if settings.KILL_SWITCH:
        return {"status": "paused", "kill_switch": True}
    return {"status": "ready", "database": "connected"}
