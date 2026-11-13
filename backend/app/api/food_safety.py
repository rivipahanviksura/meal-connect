
from fastapi import APIRouter, HTTPException

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
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail="Guidance not found"
        )
