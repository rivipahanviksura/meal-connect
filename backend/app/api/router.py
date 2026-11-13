
from fastapi import APIRouter

from app.api.health import router as health_router

from app.api import food_safety

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(health_router)


api_router.include_router(food_safety.router)