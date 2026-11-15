from fastapi import APIRouter

from app.api.health import router as health_router
from app.api.auth import router as auth_router
from app.api.donations import router as donations_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(donations_router)
