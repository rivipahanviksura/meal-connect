
from fastapi import APIRouter

from app.core.exception_handlers import APIException
from app.core.food_safety import (
    get_food_safety_guidance,
)

router = APIRouter(
    prefix="/food-safety",
    tags=["Food Safety"]
)


@router.get("/{location}")
def read_food_safety_guidance(location: str):
    try:
        return get_food_safety_guidance(location)
    except ValueError as exc:
        raise APIException(
            status_code=404,
            code="NOT_FOUND",
            message="Guidance not found",
        ) from exc
