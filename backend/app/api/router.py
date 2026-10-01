from fastapi import APIRouter

from app.api.assignments import router as assignments_router
from app.api.auth import router as auth_router
from app.api.episodes import router as episodes_router
from app.api.requests import router as requests_router
from app.api.users import router as users_router

router = APIRouter()
router.include_router(assignments_router)
router.include_router(auth_router)
router.include_router(episodes_router)
router.include_router(requests_router)
router.include_router(users_router)
