from fastapi import APIRouter

from core.models import HealthResponse

router = APIRouter(tags=["Health"])


@router.get("/health")
def health() -> HealthResponse:
    return HealthResponse(status="ok")
