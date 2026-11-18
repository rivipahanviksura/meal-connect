"""Update/cancellation request contracts; keep existing donation schemas intact."""
from datetime import datetime
from decimal import Decimal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class DonationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str | None = Field(default=None, min_length=1, max_length=180)
    category: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    total_quantity: Decimal | None = Field(
        default=None, gt=0, max_digits=12, decimal_places=2
    )
    quantity_unit: str | None = Field(default=None, min_length=1, max_length=30)
    allergen_info: str | None = None
    storage_instructions: str | None = None
    prepared_at: AwareDatetime | None = None
    available_from: AwareDatetime | None = None
    pickup_deadline: AwareDatetime | None = None
    pickup_address: str | None = Field(default=None, min_length=1, max_length=255)
    pickup_city: str | None = Field(default=None, min_length=1, max_length=120)

    @model_validator(mode="after")
    def validate_patch(self):
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided.")
        required = {
            "title", "category", "total_quantity", "quantity_unit",
            "available_from", "pickup_deadline", "pickup_address", "pickup_city",
        }
        for name in required:
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null.")
        return self


class DonationCancel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    reason: str | None = Field(default=None, min_length=1, max_length=500)
