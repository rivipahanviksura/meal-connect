
FOOD_SAFETY_GUIDANCE = {
    "donation_creation": {
        "title": "Food Safety Notice",
        "message": (
            "Only list food that you reasonably consider "
            "suitable for safe consumption. Follow proper "
            "food-handling and storage practices. "
            "Meal Connect does not inspect, certify, "
            "or guarantee food safety."
        ),
    },
    "donation_details": {
        "title": "Food Safety Reminder",
        "message": (
            "Review the food description, allergen "
            "information, storage instructions, and "
            "pickup deadline before requesting a donation. "
            "Meal Connect does not guarantee food safety."
        ),
    },
    "pickup": {
        "title": "Safe Food Collection",
        "message": (
            "Follow the provided handling and storage "
            "instructions during collection. Do not "
            "collect food if its safety is in doubt. "
            "Meal Connect does not certify food safety."
        ),
    },
}


def get_food_safety_guidance(location: str) -> dict:
    guidance = FOOD_SAFETY_GUIDANCE.get(location)

    if guidance is None:
        raise ValueError("Unknown guidance location")

    return guidance
