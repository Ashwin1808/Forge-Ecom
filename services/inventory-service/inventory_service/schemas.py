import hashlib
import json
import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Sku = Annotated[str, Field(min_length=2, max_length=64, pattern=r"^[A-Z0-9][A-Z0-9-]*$")]


class ProductCreate(BaseModel):
    sku: Sku
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    price_cents: int = Field(gt=0, le=100_000_000)
    currency: str = Field(default="USD", pattern=r"^[A-Za-z]{3}$")
    initial_quantity: int = Field(default=0, ge=0, le=1_000_000)

    @field_validator("sku")
    @classmethod
    def normalize_sku(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.strip().upper()


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sku: str
    name: str
    description: str | None
    price_cents: int
    currency: str
    quantity_available: int
    quantity_reserved: int
    in_stock: bool
    created_at: datetime


class ProductListOut(BaseModel):
    items: list[ProductOut]
    page: int
    page_size: int
    total: int


class ReservationItemIn(BaseModel):
    product_id: uuid.UUID
    quantity: int = Field(gt=0, le=1000)


class ReservationCreate(BaseModel):
    reservation_id: uuid.UUID
    items: list[ReservationItemIn] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def reject_duplicate_products(self) -> "ReservationCreate":
        product_ids = [item.product_id for item in self.items]
        if len(product_ids) != len(set(product_ids)):
            raise ValueError("duplicate product_id values are not allowed")
        return self


class ReservationItemOut(BaseModel):
    product_id: uuid.UUID
    sku: str
    name: str
    quantity: int
    unit_price_cents: int
    currency: str


class ReservationOut(BaseModel):
    id: uuid.UUID
    status: str
    items: list[ReservationItemOut]
    created_at: datetime


class ShortageOut(BaseModel):
    product_id: uuid.UUID
    requested: int
    available: int


def reservation_fingerprint(payload: ReservationCreate) -> str:
    data = payload.model_dump(mode="json")
    data["items"] = sorted(data["items"], key=lambda item: item["product_id"])
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
