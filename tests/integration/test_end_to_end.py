import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from order_service.models import Order
from order_service.workflow import expire_due_orders

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


def checkout_body(product_id, quantity, *, line1="1 Market Street"):
    return {
        "customer": {"name": "Grace Hopper", "email": "grace@example.com"},
        "delivery_address": {
            "line1": line1,
            "line2": "Suite 200",
            "city": "San Francisco",
            "region": "CA",
            "postal_code": "94105",
            "country": "US",
        },
        "items": [{"product_id": product_id, "quantity": quantity}],
    }


async def test_storefront_checkout_reserves_real_inventory_and_expires(services):
    product = await create_product(services.inventory_http, sku="INT-STORE-1", quantity=3)
    created = await services.order_http.post(
        "/api/v1/storefront/checkout",
        json=checkout_body(product["id"], 2),
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )

    assert created.status_code == 201, created.text
    order = created.json()
    assert order["status"] == "AWAITING_PAYMENT"
    assert order["payment_status"] == "CREATED"
    assert order["channel"] == "STOREFRONT"
    assert order["total_cents"] == 5000
    assert order["reservation_expires_at"] is not None
    assert order["delivery_address"]["line1"] == "1 Market Street"

    stock = await services.order_http.get(f"/api/v1/products/{product['id']}")
    assert stock.json()["quantity_available"] == 1
    assert stock.json()["quantity_reserved"] == 2

    storefront_detail = await services.order_http.get(
        f"/api/v1/storefront/orders/{order['id']}"
    )
    assert storefront_detail.status_code == 200
    assert storefront_detail.json()["id"] == order["id"]

    with services.order_app.state.db.session() as session:
        with session.begin():
            stored = session.get(Order, uuid.UUID(order["id"]))
            assert stored is not None
            stored.reservation_expires_at = datetime.now(timezone.utc) - timedelta(
                seconds=1
            )

    expired = await expire_due_orders(
        services.order_app.state.db, services.inventory_client
    )
    assert expired == 1

    expired_detail = await services.order_http.get(
        f"/api/v1/storefront/orders/{order['id']}"
    )
    assert expired_detail.status_code == 200
    assert expired_detail.json()["status"] == "EXPIRED"
    assert expired_detail.json()["failure_code"] == "reservation_expired"

    restored = await services.order_http.get(f"/api/v1/products/{product['id']}")
    assert restored.json()["quantity_available"] == 3
    assert restored.json()["quantity_reserved"] == 0

    released_again = await services.inventory_http.post(
        f"/api/v1/inventory/reservations/{order['id']}/release"
    )
    assert released_again.status_code == 200
    assert released_again.json()["status"] == "RELEASED"

    unchanged = await services.order_http.get(f"/api/v1/products/{product['id']}")
    assert unchanged.json()["quantity_available"] == 3
    assert unchanged.json()["quantity_reserved"] == 0


async def test_storefront_checkout_insufficient_stock_persists_failed_order(services):
    product = await create_product(services.inventory_http, sku="INT-STORE-2", quantity=1)
    response = await services.order_http.post(
        "/api/v1/storefront/checkout",
        json=checkout_body(product["id"], 2),
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )

    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "inventory_insufficient_stock"
    order_id = error["details"]["order_id"]

    detail = await services.order_http.get(f"/api/v1/storefront/orders/{order_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["status"] == "FAILED"
    assert body["channel"] == "STOREFRONT"
    assert body["payment_status"] is None
    assert body["failure_code"] == "inventory_insufficient_stock"
    assert body["delivery_address"]["line1"] == "1 Market Street"

    stock = await services.order_http.get(f"/api/v1/products/{product['id']}")
    assert stock.json()["quantity_available"] == 1
    assert stock.json()["quantity_reserved"] == 0
