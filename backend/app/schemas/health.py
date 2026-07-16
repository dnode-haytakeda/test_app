from pydantic import BaseModel


class HealthCheck(BaseModel):
    status: str
    version: str
    checks: dict[str, str] | None = None


class LivenessResponse(BaseModel):
    status: str
    