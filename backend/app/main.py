from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.errors import AppError


app = FastAPI(title="Dataset Request Desk")

api_router = APIRouter(prefix="/api/v1")


@api_router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


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


app.include_router(api_router)



__all__ = ["app", "settings"]