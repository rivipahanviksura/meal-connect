
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DonationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(
        default=None, min_length=1, max_length=180
    )
    category: str | None = Field(
        default=None, min_length=1, max_length=100
    )
    description: str | None = None

    total_quantity: Decimal | None = Field(
        default=None, gt=0, max_digits=12, decimal_places=2
    )
    quantity_unit: str | None = Field(
        default=None, min_length=1, max_length=30
    )

    allergen_info: str | None = None
    storage_instructions: str | None = None

    prepared_at: datetime | None = None
    available_from: datetime | None = None
    pickup_deadline: datetime | None = None

    pickup_address: str | None = Field(
        default=None, min_length=1, max_length=255
    )
    pickup_city: str | None = Field(
        default=None, min_length=1, max_length=120
    )

    @model_validator(mode="after")
    def validate_update(self):
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided.")

        required_fields = {
            "title",
            "category",
            "total_quantity",
            "quantity_unit",
            "available_from",
            "pickup_deadline",
            "pickup_address",
            "pickup_city",
        }

        for field in required_fields:
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null.")

        return self


class DonationCancel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(
        default=None,
        max_length=500,
    )
