import asyncio
import uuid

import pytest
from sqlalchemy import func, select

from order_service.models import Order

from .conftest import create_product

pytestmark = pytest.mark.integration


def order_body(product_id, quantity):
    return {
        "customer": {"name": "Grace Hopper", "email": "grace@example.com"},
        "items": [{"product_id": product_id, "quantity": quantity}],
    }


async def test_order_service_reserves_real_inventory(services):
    product = await create_product(services.inventory_http, quantity=5)
    key = str(uuid.uuid4())

    response = await services.order_http.post(
        "/api/v1/orders",
        json=order_body(product["id"], 2),
        headers={"Idempotency-Key": key},
    )
    assert response.status_code == 201, response.text
    order = response.json()
    assert order["status"] == "CONFIRMED"
    assert order["total_cents"] == 5000
    assert order["items"][0]["name"] == "Integration INT-001"

    stock = await services.order_http.get(f"/api/v1/products/{product['id']}")
    assert stock.status_code == 200
    assert stock.json()["quantity_available"] == 3
    assert stock.json()["quantity_reserved"] == 2

    replay = await services.order_http.post(
        "/api/v1/orders",
        json=order_body(product["id"], 2),
        headers={"Idempotency-Key": key},
    )
    assert replay.status_code == 201
    assert replay.json()["id"] == order["id"]
    stock_after_replay = await services.order_http.get(
        f"/api/v1/products/{product['id']}"
    )
    assert stock_after_replay.json()["quantity_available"] == 3

    detail = await services.order_http.get(f"/api/v1/orders/{order['id']}")
    assert detail.status_code == 200
    assert detail.json()["items"][0]["sku"] == "INT-001"

    catalog = await services.order_http.get("/api/v1/products")
    assert catalog.status_code == 200
    assert catalog.json()["total"] == 1


async def test_insufficient_inventory_fails_order_without_overselling(services):
    product = await create_product(services.inventory_http, sku="INT-002", quantity=1)
    response = await services.order_http.post(
        "/api/v1/orders",
        json=order_body(product["id"], 2),
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )

    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "inventory_insufficient_stock"
    order_id = error["details"]["order_id"]

    detail = await services.order_http.get(f"/api/v1/orders/{order_id}")
    assert detail.status_code == 200
    assert detail.json()["status"] == "FAILED"
    assert detail.json()["failure_code"] == "inventory_insufficient_stock"

    stock = await services.order_http.get(f"/api/v1/products/{product['id']}")
    assert stock.json()["quantity_available"] == 1
    assert stock.json()["quantity_reserved"] == 0


async def test_unknown_product_fails_order(services):
    response = await services.order_http.post(
        "/api/v1/orders",
        json=order_body(str(uuid.uuid4()), 1),
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "inventory_unknown_product"


async def test_concurrent_orders_cannot_oversell(services):
    product = await create_product(services.inventory_http, sku="INT-003", quantity=1)

    async def place_order():
        return await services.order_http.post(
            "/api/v1/orders",
            json=order_body(product["id"], 1),
            headers={"Idempotency-Key": str(uuid.uuid4())},
        )

    responses = await asyncio.gather(place_order(), place_order())
    statuses = sorted(response.status_code for response in responses)
    assert statuses == [201, 409]

    stock = await services.order_http.get(f"/api/v1/products/{product['id']}")
    assert stock.json()["quantity_available"] == 0
    assert stock.json()["quantity_reserved"] == 1

    with services.order_app.state.db.session() as session:
        total = session.scalar(select(func.count()).select_from(Order))
        confirmed = session.scalar(
            select(func.count()).select_from(Order).where(Order.status == "CONFIRMED")
        )
        failed = session.scalar(
            select(func.count()).select_from(Order).where(Order.status == "FAILED")
        )
    assert (total, confirmed, failed) == (2, 1, 1)
