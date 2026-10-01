import logging

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.api.health import router as health_router
from app.core.config import settings
from app.core.errors import AppError

logger = logging.getLogger(__name__)

app = FastAPI(title="Dataset Request Desk")


@app.on_event("startup")
async def startup_event() -> None:
    """Run startup tasks: seed users."""
    from app.db.session import SessionFactory
    from app.services.seed_service import seed_users

    logger.info("Running startup tasks...")

    try:
        async with SessionFactory() as session:
            result = await seed_users(session)
            logger.info(
                f"Seed users: {result['created']} created, "
                f"{result['existing']} existing"
            )
    except Exception as e:
        logger.error(f"Startup seed failed: {e}", exc_info=True)
        # Don't prevent startup - seed can be run manually


api_router = APIRouter(prefix="/api/v1")


@app.exception_handler(AppError)
async def app_error_handler(
    request: Request,
    exc: AppError,
) -> JSONResponse:
    error = {
        "code": exc.code,
        "message": exc.message,
    }

    if exc.field is not None:
        error["field"] = exc.field

    return JSONResponse(
        status_code=exc.http_status,
        content={"error": error},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    first_error = exc.errors()[0]

    field = None
    location = first_error.get("loc", ())

    if location:
        field = str(location[-1])

    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                **({"field": field} if field is not None else {}),
            }
        },
    )


app.include_router(health_router)
app.include_router(api_router)


__all__ = ["app", "settings"]
