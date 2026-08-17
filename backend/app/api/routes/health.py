from fastapi import APIRouter

router = APIRouter(prefix="/api/v1", tags=["Health"])


@router.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "healthy"}
