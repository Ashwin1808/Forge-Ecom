import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from order_service.client import InventoryClientError, ReservedLine
from order_service.models import Order, OrderStatus
from order_service.workflow import expire_due_orders

pytestmark = pytest.mark.integration


def address(**overrides):
    value = {
        "line1": "1 Market Street",
        "line2": "Suite 200",
        "city": "San Francisco",
        "region": "CA",
        "postal_code": "94105",
        "country": "US",
    }
    value.update(overrides)
    return value


def checkout_payload(product_id=None, quantity=2, delivery_address=None):
    return {
        "customer": {"name": "Grace Hopper", "email": "Grace@Example.com"},
        "delivery_address": delivery_address or address(),
        "items": [
            {
                "product_id": str(product_id or uuid.uuid4()),
                "quantity": quantity,
            }
        ],
    }


def headers(key=None):
    return {"Idempotency-Key": key or str(uuid.uuid4())}


def make_expired(app, order_id):
    with app.state.db.session() as session:
        order = session.get(Order, uuid.UUID(order_id))
        assert order is not None
        order.reservation_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        session.commit()


def get_order(app, order_id):
    with app.state.db.session() as session:
        return session.get(Order, uuid.UUID(order_id))


def test_checkout_creates_awaiting_payment_order(client, app, fake_inventory):
    product_id = uuid.uuid4()
    response = client.post(
        "/api/v1/storefront/checkout",
        json=checkout_payload(product_id=product_id),
        headers=headers(),
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "AWAITING_PAYMENT"
    assert body["payment_status"] == "CREATED"
    assert body["channel"] == "STOREFRONT"
    assert body["customer"] == {
        "name": "Grace Hopper",
        "email": "grace@example.com",
    }
    assert body["delivery_address"] == address()
    assert body["total_cents"] == 2000
    assert body["reservation_expires_at"] is not None
    assert body["failure_code"] is None
    assert len(fake_inventory.reserve_calls) == 1
    assert fake_inventory.release_calls == []

    order = get_order(app, body["id"])
    assert order is not None
    assert order.status == OrderStatus.AWAITING_PAYMENT.value
    assert order.payment_status == "CREATED"
    assert order.channel == "STOREFRONT"
    assert order.delivery_line1 == "1 Market Street"
    assert order.total_cents == 2000

    fetched = client.get(f"/api/v1/storefront/orders/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == body["id"]

    ops_fetched = client.get(f"/api/v1/orders/{body['id']}")
    assert ops_fetched.status_code == 200
    assert ops_fetched.json()["channel"] == "STOREFRONT"


def test_checkout_replay_returns_same_order_without_new_reservation(
    client, app, fake_inventory
):
    product_id = uuid.uuid4()
    key = str(uuid.uuid4())
    body = checkout_payload(product_id=product_id)

    first = client.post(
        "/api/v1/storefront/checkout", json=body, headers=headers(key)
    )
    second = client.post(
        "/api/v1/storefront/checkout", json=body, headers=headers(key)
    )

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["id"] == second.json()["id"]
    assert len(fake_inventory.reserve_calls) == 1

    with app.state.db.session() as session:
        assert len(session.scalars(select(Order)).all()) == 1


def test_checkout_idempotency_key_with_changed_address_conflicts(
    client, fake_inventory
):
    key = str(uuid.uuid4())
    first = client.post(
        "/api/v1/storefront/checkout",
        json=checkout_payload(),
        headers=headers(key),
    )
    second = client.post(
        "/api/v1/storefront/checkout",
        json=checkout_payload(delivery_address=address(line1="2 Other Street")),
        headers=headers(key),
    )

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "idempotency_conflict"
    assert len(fake_inventory.reserve_calls) == 1


@pytest.mark.parametrize(
    "mutator",
    [
        lambda body: body["delivery_address"].update({"line1": "   "}),
        lambda body: body["delivery_address"].update({"city": ""}),
        lambda body: body["delivery_address"].update({"postal_code": ""}),
        lambda body: body["delivery_address"].update({"country": " "}),
        lambda body: body["delivery_address"].pop("country"),
        lambda body: body["customer"].update({"email": "not-an-email"}),
        lambda body: body.update({"items": []}),
        lambda body: body["items"].append(dict(body["items"][0])),
    ],
)
def test_checkout_validation_rejects_bad_payloads(
    client, fake_inventory, mutator
):
    body = checkout_payload()
    mutator(body)
    response = client.post(
        "/api/v1/storefront/checkout", json=body, headers=headers()
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert fake_inventory.reserve_calls == []


@pytest.mark.parametrize(
    ("kind", "expected_status", "expected_code", "expiry_cleared"),
    [
        ("insufficient_stock", 409, "inventory_insufficient_stock", True),
        ("unknown_product", 422, "inventory_unknown_product", True),
        ("timeout", 504, "inventory_timeout", False),
        ("unavailable", 503, "inventory_unavailable", False),
        ("protocol", 502, "inventory_protocol", False),
    ],
)
def test_checkout_inventory_failures_are_persisted(
    app, client, fake_inventory, kind, expected_status, expected_code, expiry_cleared
):
    fake_inventory.reserve_error = InventoryClientError(kind, "inventory failed")
    response = client.post(
        "/api/v1/storefront/checkout",
        json=checkout_payload(),
        headers=headers(),
    )

    assert response.status_code == expected_status
    error = response.json()["error"]
    assert error["code"] == expected_code
    order = get_order(app, error["details"]["order_id"])
    assert order is not None
    assert order.status == OrderStatus.FAILED.value
    assert order.payment_status is None
    assert order.failure_code == expected_code
    assert (order.reservation_expires_at is None) is expiry_cleared


def test_checkout_reservation_mismatch_releases_stock(
    app, client, fake_inventory
):
    product_id = uuid.uuid4()
    fake_inventory.reserve_override_items = [
        ReservedLine(
            product_id=product_id,
            sku="SKU-TEST",
            name="Mismatched product",
            quantity=3,
            unit_price_cents=1000,
            currency="USD",
        )
    ]
    response = client.post(
        "/api/v1/storefront/checkout",
        json=checkout_payload(product_id=product_id, quantity=2),
        headers=headers(),
    )

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "inventory_protocol"
    assert len(fake_inventory.release_calls) == 1
    order = get_order(app, response.json()["error"]["details"]["order_id"])
    assert order is not None
    assert order.status == OrderStatus.FAILED.value
    assert order.reservation_expires_at is None


def test_storefront_order_lookup_rejects_operations_orders(client):
    created = client.post(
        "/api/v1/orders",
        json={
            "customer": {"name": "Ops User", "email": "ops@example.com"},
            "items": [{"product_id": str(uuid.uuid4()), "quantity": 1}],
        },
        headers=headers(),
    )
    assert created.status_code == 201

    response = client.get(f"/api/v1/storefront/orders/{created.json()['id']}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "order_not_found"


def test_expired_checkout_releases_stock_and_marks_order_expired(
    app, client, fake_inventory
):
    created = client.post(
        "/api/v1/storefront/checkout",
        json=checkout_payload(),
        headers=headers(),
    )
    assert created.status_code == 201
    order_id = created.json()["id"]
    make_expired(app, order_id)

    expired = asyncio.run(expire_due_orders(app.state.db, fake_inventory))

    assert expired == 1
    assert len(fake_inventory.release_calls) == 1
    assert fake_inventory.release_calls[0]["reservation_id"] == uuid.UUID(order_id)
    order = get_order(app, order_id)
    assert order is not None
    assert order.status == OrderStatus.EXPIRED.value
    assert order.failure_code == "reservation_expired"

    replay = client.post(
        "/api/v1/storefront/checkout",
        json=checkout_payload(),
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert replay.status_code == 201


def test_expiry_release_failure_keeps_order_for_retry(app, client, fake_inventory):
    created = client.post(
        "/api/v1/storefront/checkout",
        json=checkout_payload(),
        headers=headers(),
    )
    order_id = created.json()["id"]
    make_expired(app, order_id)
    fake_inventory.release_error = InventoryClientError("timeout", "release timed out")

    expired = asyncio.run(expire_due_orders(app.state.db, fake_inventory))
    assert expired == 0
    order = get_order(app, order_id)
    assert order is not None
    assert order.status == OrderStatus.AWAITING_PAYMENT.value
    assert order.reservation_expires_at is not None

    fake_inventory.release_error = None
    expired = asyncio.run(expire_due_orders(app.state.db, fake_inventory))
    assert expired == 1
    order = get_order(app, order_id)
    assert order is not None
    assert order.status == OrderStatus.EXPIRED.value


def test_timeout_failed_checkout_is_cleaned_up_by_expiry_worker(
    app, client, fake_inventory
):
    fake_inventory.reserve_error = InventoryClientError("timeout", "reserve timed out")
    created = client.post(
        "/api/v1/storefront/checkout",
        json=checkout_payload(),
        headers=headers(),
    )
    assert created.status_code == 504
    order_id = created.json()["error"]["details"]["order_id"]
    order = get_order(app, order_id)
    assert order is not None
    assert order.status == OrderStatus.FAILED.value
    assert order.reservation_expires_at is not None
    make_expired(app, order_id)

    expired = asyncio.run(expire_due_orders(app.state.db, fake_inventory))
    assert expired == 0
    assert len(fake_inventory.release_calls) == 1
    order = get_order(app, order_id)
    assert order is not None
    assert order.status == OrderStatus.FAILED.value
    assert order.reservation_expires_at is None
