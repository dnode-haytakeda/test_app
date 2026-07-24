import structlog
from fastapi import APIRouter
from sqlalchemy import text

from app.core.database import engine
from app.core.version import APP_VERSION
from app.schemas.health import HealthCheck, LivenessResponse

router = APIRouter(prefix="/health", tags=["health"])

logger = structlog.get_logger()


async def _check_database() -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        logger.error("Database health check failed", error=str(exc))
        return False
    return True


@router.get("/live", response_model=LivenessResponse)
async def liveness() -> LivenessResponse:
    return LivenessResponse(status="ok")


@router.get("", response_model=HealthCheck)
async def health() -> HealthCheck:
    db_ok = await _check_database()
    return HealthCheck(
        status="ok" if db_ok else "degraded",
        version=APP_VERSION,
        checks={"database": "ok" if db_ok else "degraded"},
    )