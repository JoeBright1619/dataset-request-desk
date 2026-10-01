from fastapi import APIRouter, FastAPI

from app.core.config import settings


app = FastAPI(title="Dataset Request Desk")

api_router = APIRouter(prefix="/api/v1")


@api_router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(api_router)


__all__ = ["app", "settings"]