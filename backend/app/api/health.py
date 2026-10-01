from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db.engine import engine

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
async def health_ready() -> JSONResponse:
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unavailable",
                "checks": {"database": "error"},
            },
        )

    return JSONResponse(
        status_code=200,
        content={
            "status": "ready",
            "checks": {"database": "ok"},
        },
    )
