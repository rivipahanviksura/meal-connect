from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.db.models.donation import DonationStatus


class DonationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=180)
    category: str = Field(min_length=1, max_length=100)
    description: str | None = None

    total_quantity: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    quantity_unit: str = Field(min_length=1, max_length=30)

    allergen_info: str | None = None
    storage_instructions: str | None = None

    prepared_at: datetime | None = None
    available_from: datetime
    pickup_deadline: datetime

    pickup_address: str = Field(min_length=1, max_length=255)
    pickup_city: str = Field(min_length=1, max_length=120)

    @model_validator(mode="after")
    def validate_deadline(self):
        if self.pickup_deadline <= self.available_from:
            raise ValueError(
                "Pickup deadline must be after available from."
            )

        if (
            self.prepared_at is not None
            and self.prepared_at > self.pickup_deadline
        ):
            raise ValueError(
                "Prepared time cannot be after pickup deadline."
            )

        return self


class DonationBrowseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    donation_id: int
    title: str
    category: str
    description: str | None
    total_quantity: Decimal
    allocated_quantity: Decimal
    quantity_unit: str
    allergen_info: str | None
    storage_instructions: str | None
    prepared_at: datetime | None
    available_from: datetime
    pickup_deadline: datetime
    pickup_address: str
    pickup_city: str
    status: DonationStatus
    created_at: datetime
