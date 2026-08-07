from fastapi import APIRouter, status
from pydantic import BaseModel

router = APIRouter(prefix="/health", tags=["health"])


class HealthResponse(BaseModel):
    status: str


@router.get(
    "",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Liveness health check",
)
async def health_check() -> HealthResponse:
    return HealthResponse(status="ok")
