import os
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import text

from inventory_service.config import Settings as InventorySettings
from inventory_service.database import Database as InventoryDatabase
from inventory_service.main import create_app as create_inventory_app
from inventory_service.models import Base as InventoryBase
from order_service.client import InventoryClient
from order_service.config import Settings as OrderSettings
from order_service.database import Database as OrderDatabase
from order_service.main import create_app as create_order_app
from order_service.metrics import OrderMetrics
from order_service.models import Base as OrderBase

INVENTORY_DATABASE_URL = os.getenv(
    "TEST_INVENTORY_DATABASE_URL",
    "postgresql+psycopg://postgres@localhost:55433/forge_inventory_test",
)
ORDER_DATABASE_URL = os.getenv(
    "TEST_ORDERS_DATABASE_URL",
    "postgresql+psycopg://postgres@localhost:55433/forge_orders_test",
)


@pytest.fixture(scope="session")
def schemas():
    inventory_database = InventoryDatabase(INVENTORY_DATABASE_URL)
    order_database = OrderDatabase(ORDER_DATABASE_URL)
    InventoryBase.metadata.drop_all(inventory_database.engine)
    InventoryBase.metadata.create_all(inventory_database.engine)
    OrderBase.metadata.drop_all(order_database.engine)
    OrderBase.metadata.create_all(order_database.engine)
    yield
    InventoryBase.metadata.drop_all(inventory_database.engine)
    OrderBase.metadata.drop_all(order_database.engine)
    inventory_database.dispose()
    order_database.dispose()


@pytest.fixture
async def services(schemas):
    inventory_app = create_inventory_app(
        InventorySettings(
            database_url=INVENTORY_DATABASE_URL,
            environment="test",
            log_level="WARNING",
            rate_limit_per_minute=100_000,
            seed_on_start=False,
        )
    )
    with inventory_app.state.db.engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE TABLE inventory_reservation_items, inventory_reservations, "
                "inventory, products RESTART IDENTITY CASCADE"
            )
        )

    inventory_http = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=inventory_app),
        base_url="http://inventory-service",
    )
    inventory_client = InventoryClient(
        base_url="http://inventory-service",
        timeout_seconds=3.0,
        metrics=OrderMetrics(),
        client=inventory_http,
    )
    order_app = create_order_app(
        OrderSettings(
            database_url=ORDER_DATABASE_URL,
            environment="test",
            log_level="WARNING",
            rate_limit_per_minute=100_000,
            inventory_base_url="http://inventory-service",
        ),
        inventory_client=inventory_client,
    )
    with order_app.state.db.engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE TABLE order_items, idempotency_records, orders "
                "RESTART IDENTITY CASCADE"
            )
        )

    order_http = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=order_app),
        base_url="http://order-service",
    )

    yield SimpleNamespace(
        inventory_app=inventory_app,
        order_app=order_app,
        inventory_http=inventory_http,
        order_http=order_http,
        inventory_client=inventory_client,
    )

    await order_http.aclose()
    await inventory_http.aclose()
    order_app.state.db.dispose()
    inventory_app.state.db.dispose()


async def create_product(inventory_http, *, sku="INT-001", quantity=5, price=2500):
    response = await inventory_http.post(
        "/api/v1/products",
        json={
            "sku": sku,
            "name": f"Integration {sku}",
            "price_cents": price,
            "currency": "USD",
            "initial_quantity": quantity,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()
