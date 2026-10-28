import asyncio
import os
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from order_service.client import (
    InventoryClientError,
    InventoryReservation,
    ReservedLine,
)
from order_service.config import Settings
from order_service.main import create_app
from order_service.models import Base
from order_service.schemas import CatalogProductListOut, CatalogProductOut

TEST_DATABASE_URL = os.getenv(
    "TEST_ORDERS_DATABASE_URL",
    "postgresql+psycopg://postgres@localhost:55433/forge_orders_test",
)


class FakeInventoryClient:
    def __init__(self) -> None:
        self.reserve_error: InventoryClientError | None = None
        self.list_error: InventoryClientError | None = None
        self.get_error: InventoryClientError | None = None
        self.reserve_delay = 0.0
        self.reserve_calls: list[dict] = []
        self.reserve_override_items: list[ReservedLine] | None = None
        self.release_error: InventoryClientError | None = None
        self.release_calls: list[dict] = []
        self.closed = False
        self.product_id = uuid.UUID("11111111-1111-4111-8111-111111111111")
        self.second_product_id = uuid.UUID("22222222-2222-4222-8222-222222222222")

    def _catalog_product(self, product_id: uuid.UUID, name: str, quantity: int):
        return CatalogProductOut(
            id=product_id,
            sku=f"SKU-{str(product_id)[:4]}",
            name=name,
            description="Fake catalog product",
            price_cents=1000,
            currency="USD",
            quantity_available=quantity,
            quantity_reserved=0,
            in_stock=quantity > 0,
            created_at=datetime.now(timezone.utc),
        )

    async def reserve(self, *, reservation_id, items, request_id=None):
        self.reserve_calls.append(
            {"reservation_id": reservation_id, "items": items, "request_id": request_id}
        )
        if self.reserve_delay:
            await asyncio.sleep(self.reserve_delay)
        if self.reserve_error is not None:
            raise self.reserve_error
        return InventoryReservation(
            id=reservation_id,
            status="RESERVED",
            items=self.reserve_override_items
            or [
                ReservedLine(
                    product_id=product_id,
                    sku=f"SKU-{str(product_id)[:4]}",
                    name=f"Fake product {str(product_id)[:8]}",
                    quantity=quantity,
                    unit_price_cents=1000,
                    currency="USD",
                )
                for product_id, quantity in items
            ],
        )

    async def release(self, *, reservation_id, request_id=None):
        self.release_calls.append(
            {"reservation_id": reservation_id, "request_id": request_id}
        )
        if self.release_error is not None:
            raise self.release_error
        return "RELEASED"

    async def list_products(self, *, page, page_size, request_id=None):
        if self.list_error is not None:
            raise self.list_error
        return CatalogProductListOut(
            items=[
                self._catalog_product(self.product_id, "Fake Keyboard", 10),
                self._catalog_product(self.second_product_id, "Fake Display", 0),
            ],
            page=page,
            page_size=page_size,
            total=2,
        )

    async def get_product(self, product_id, *, request_id=None):
        if self.get_error is not None:
            raise self.get_error
        if product_id == self.second_product_id:
            return self._catalog_product(self.second_product_id, "Fake Display", 0)
        return self._catalog_product(self.product_id, "Fake Keyboard", 10)

    async def aclose(self):
        self.closed = True


@pytest.fixture(scope="session")
def settings() -> Settings:
    return Settings(
        database_url=TEST_DATABASE_URL,
        environment="test",
        log_level="WARNING",
        rate_limit_per_minute=100_000,
        inventory_base_url="http://inventory-service:8000",
        checkout_expiry_enabled=False,
        db_pool_size=10,
        db_max_overflow=20,
    )


@pytest.fixture(scope="session", autouse=True)
def schema(settings):
    from order_service.database import Database

    database = Database(settings.database_url)
    Base.metadata.drop_all(database.engine)
    Base.metadata.create_all(database.engine)
    yield
    Base.metadata.drop_all(database.engine)
    database.dispose()


@pytest.fixture
def fake_inventory() -> FakeInventoryClient:
    return FakeInventoryClient()


@pytest.fixture
def app(settings, fake_inventory, schema):
    application = create_app(settings, inventory_client=fake_inventory)
    with application.state.db.engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE TABLE order_items, idempotency_records, orders "
                "RESTART IDENTITY CASCADE"
            )
        )
    yield application
    application.state.db.dispose()


@pytest.fixture
def client(app):
    return TestClient(app)
