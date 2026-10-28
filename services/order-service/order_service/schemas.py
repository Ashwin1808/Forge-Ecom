import hashlib
import json
import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from .models import OrderChannel, OrderStatus, PaymentStatus


class CustomerIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name must not be blank")
        return value

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()


class OrderItemIn(BaseModel):
    product_id: uuid.UUID
    quantity: int = Field(gt=0, le=100)


class DeliveryAddressIn(BaseModel):
    line1: str = Field(min_length=1, max_length=200)
    line2: str | None = Field(default=None, max_length=200)
    city: str = Field(min_length=1, max_length=120)
    region: str | None = Field(default=None, max_length=120)
    postal_code: str = Field(min_length=1, max_length=32)
    country: str = Field(min_length=2, max_length=80)

    @field_validator("line1", "city", "postal_code", "country")
    @classmethod
    def normalize_required_address_fields(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("address field must not be blank")
        return value

    @field_validator("line2", "region")
    @classmethod
    def normalize_optional_address_fields(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class OrderCreate(BaseModel):
    customer: CustomerIn
    items: list[OrderItemIn] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def reject_duplicate_products(self) -> "OrderCreate":
        product_ids = [item.product_id for item in self.items]
        if len(product_ids) != len(set(product_ids)):
            raise ValueError("duplicate product_id values are not allowed")
        return self


class CheckoutCreate(BaseModel):
    customer: CustomerIn
    delivery_address: DeliveryAddressIn
    items: list[OrderItemIn] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def reject_duplicate_products(self) -> "CheckoutCreate":
        product_ids = [item.product_id for item in self.items]
        if len(product_ids) != len(set(product_ids)):
            raise ValueError("duplicate product_id values are not allowed")
        return self


class CustomerOut(BaseModel):
    name: str
    email: str


class DeliveryAddressOut(BaseModel):
    line1: str
    line2: str | None
    city: str
    region: str | None
    postal_code: str
    country: str


class OrderItemOut(BaseModel):
    product_id: uuid.UUID
    sku: str | None
    name: str | None
    quantity: int
    unit_price_cents: int | None
    currency: str | None
    line_total_cents: int | None


class OrderOut(BaseModel):
    id: uuid.UUID
    status: OrderStatus
    payment_status: PaymentStatus | None
    channel: OrderChannel
    customer: CustomerOut
    delivery_address: DeliveryAddressOut | None
    items: list[OrderItemOut]
    total_cents: int | None
    currency: str
    reservation_expires_at: datetime | None
    failure_code: str | None
    failure_message: str | None
    created_at: datetime
    updated_at: datetime


class OrderListOut(BaseModel):
    items: list[OrderOut]
    page: int
    page_size: int
    total: int


class OrderItemsOut(BaseModel):
    items: list[OrderItemOut]


class CatalogProductOut(BaseModel):
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


class CatalogProductListOut(BaseModel):
    items: list[CatalogProductOut]
    page: int
    page_size: int
    total: int


def order_fingerprint(payload: OrderCreate) -> str:
    data = payload.model_dump(mode="json")
    data["items"] = sorted(data["items"], key=lambda item: item["product_id"])
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def checkout_fingerprint(payload: CheckoutCreate) -> str:
    data = payload.model_dump(mode="json")
    data["items"] = sorted(data["items"], key=lambda item: item["product_id"])
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
