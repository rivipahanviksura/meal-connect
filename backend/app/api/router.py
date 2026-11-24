from fastapi import APIRouter

from app.api.health import router as health_router
from app.api.auth import router as auth_router
from app.api.dependencies import get_active_user
from app.api.donations import router as donations_router
from app.api.organization_application import create_organization_application_router
from app.api.donation_edit_cancel import router as donation_edit_cancel_router
from app.api.food_safety import router as food_safety_router
from app.api.admin_organization_applications import (
    router as admin_organization_applications_router,
)

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(
    create_organization_application_router(get_active_user)
)
api_router.include_router(food_safety_router)
api_router.include_router(donations_router)
api_router.include_router(donation_edit_cancel_router)
api_router.include_router(admin_organization_applications_router)
