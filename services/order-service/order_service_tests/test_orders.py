import asyncio
import uuid

import httpx
import pytest
from sqlalchemy import func, select

from order_service.client import InventoryClientError
from order_service.models import IdempotencyRecord, Order, OrderItem, OrderStatus

pytestmark = pytest.mark.integration


def payload(product_id=None, quantity=2, name="Ada Lovelace", email="Ada@Example.com"):
    return {
        "customer": {"name": name, "email": email},
        "items": [
            {
                "product_id": str(product_id or uuid.uuid4()),
                "quantity": quantity,
            }
        ],
    }


def headers(key=None):
    return {"Idempotency-Key": key or str(uuid.uuid4())}


def count_orders(app, status=None) -> int:
    with app.state.db.session() as session:
        statement = select(func.count()).select_from(Order)
        if status is not None:
            statement = statement.where(Order.status == status)
        return session.scalar(statement) or 0


def test_create_order_success_and_persistence(app, client):
    product_id = uuid.uuid4()
    key = str(uuid.uuid4())
    response = client.post(
        "/api/v1/orders", json=payload(product_id=product_id), headers=headers(key)
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "CONFIRMED"
    assert body["customer"] == {"name": "Ada Lovelace", "email": "ada@example.com"}
    assert body["total_cents"] == 2000
    assert body["items"][0]["product_id"] == str(product_id)
    assert body["items"][0]["quantity"] == 2
    assert body["items"][0]["unit_price_cents"] == 1000
    assert body["items"][0]["line_total_cents"] == 2000
    assert response.headers["X-Request-ID"]

    fetched = client.get(f"/api/v1/orders/{body['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == body["id"]

    with app.state.db.session() as session:
        order = session.get(Order, uuid.UUID(body["id"]))
        assert order is not None
        assert order.status == OrderStatus.CONFIRMED.value
        items = session.scalars(
            select(OrderItem).where(OrderItem.order_id == order.id)
        ).all()
        assert len(items) == 1
        record = session.get(IdempotencyRecord, key)
        assert record is not None
        assert record.order_id == order.id


@pytest.mark.parametrize(
    "mutator",
    [
        lambda body: body["customer"].update({"email": "not-an-email"}),
        lambda body: body["customer"].update({"name": "   "}),
        lambda body: body.update({"items": []}),
        lambda body: body["items"][0].update({"quantity": 0}),
        lambda body: body["items"].append(dict(body["items"][0])),
        lambda body: body["items"][0].update({"quantity": 101}),
    ],
)
def test_invalid_order_payloads_are_rejected(client, fake_inventory, mutator):
    body = payload()
    mutator(body)
    response = client.post("/api/v1/orders", json=body, headers=headers())
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert fake_inventory.reserve_calls == []


@pytest.mark.parametrize("key", [None, "short", "bad key with spaces"])
def test_idempotency_key_is_required_and_validated(client, fake_inventory, key):
    request_headers = {} if key is None else {"Idempotency-Key": key}
    response = client.post("/api/v1/orders", json=payload(), headers=request_headers)
    assert response.status_code == 422
    assert fake_inventory.reserve_calls == []


@pytest.mark.parametrize(
    ("kind", "expected_status", "expected_code"),
    [
        ("unknown_product", 422, "inventory_unknown_product"),
        ("insufficient_stock", 409, "inventory_insufficient_stock"),
        ("timeout", 504, "inventory_timeout"),
        ("unavailable", 503, "inventory_unavailable"),
        ("protocol", 502, "inventory_protocol"),
    ],
)
def test_inventory_failures_are_persisted_as_failed_orders(
    app, client, fake_inventory, kind, expected_status, expected_code
):
    fake_inventory.reserve_error = InventoryClientError(kind, "inventory failed")
    key = str(uuid.uuid4())
    response = client.post("/api/v1/orders", json=payload(), headers=headers(key))

    assert response.status_code == expected_status
    error = response.json()["error"]
    assert error["code"] == expected_code
    order_id = error["details"]["order_id"]

    fetched = client.get(f"/api/v1/orders/{order_id}")
    assert fetched.status_code == 200
    order = fetched.json()
    assert order["status"] == "FAILED"
    assert order["failure_code"] == expected_code
    assert order["failure_message"]
    assert order["total_cents"] is None
    assert count_orders(app) == 1
    assert len(fake_inventory.reserve_calls) == 1


def test_duplicate_idempotency_key_replays_without_duplicate_order(
    app, client, fake_inventory
):
    product_id = uuid.uuid4()
    key = str(uuid.uuid4())
    body = payload(product_id=product_id)

    first = client.post("/api/v1/orders", json=body, headers=headers(key))
    second = client.post("/api/v1/orders", json=body, headers=headers(key))

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert count_orders(app) == 1
    assert len(fake_inventory.reserve_calls) == 1


def test_same_idempotency_key_with_different_payload_conflicts(
    app, client, fake_inventory
):
    key = str(uuid.uuid4())
    first = client.post("/api/v1/orders", json=payload(quantity=1), headers=headers(key))
    second = client.post("/api/v1/orders", json=payload(quantity=2), headers=headers(key))

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "idempotency_conflict"
    assert count_orders(app) == 1
    assert len(fake_inventory.reserve_calls) == 1


def test_failed_order_replay_does_not_retry_inventory(app, client, fake_inventory):
    fake_inventory.reserve_error = InventoryClientError(
        "insufficient_stock", "not enough"
    )
    key = str(uuid.uuid4())
    body = payload()

    first = client.post("/api/v1/orders", json=body, headers=headers(key))
    second = client.post("/api/v1/orders", json=body, headers=headers(key))

    assert first.status_code == 409
    assert second.status_code == 409
    assert first.json()["error"]["details"]["order_id"] == second.json()["error"]["details"]["order_id"]
    assert len(fake_inventory.reserve_calls) == 1
    assert count_orders(app, OrderStatus.FAILED.value) == 1


def test_concurrent_duplicate_order_requests_create_one_order(app, fake_inventory):
    fake_inventory.reserve_delay = 0.15
    key = str(uuid.uuid4())
    body = payload()
    app.state.inventory_client.reserve_delay = 0.15

    async def run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://order-service"
        ) as async_client:
            return await asyncio.gather(
                async_client.post("/api/v1/orders", json=body, headers=headers(key)),
                async_client.post("/api/v1/orders", json=body, headers=headers(key)),
            )

    responses = asyncio.run(run())
    statuses = sorted(response.status_code for response in responses)
    assert statuses in ([201, 409], [201, 201])
    assert count_orders(app) == 1
    assert len(fake_inventory.reserve_calls) == 1

    order_id = None
    for response in responses:
        if response.status_code == 201:
            order_id = response.json()["id"]
        else:
            assert response.json()["error"]["code"] == "order_in_progress"
            order_id = response.json()["error"]["details"]["order_id"]
    assert order_id is not None


def test_order_listing_pagination_and_status_filter(app, client, fake_inventory):
    for _ in range(2):
        response = client.post("/api/v1/orders", json=payload(), headers=headers())
        assert response.status_code == 201

    fake_inventory.reserve_error = InventoryClientError("insufficient_stock", "nope")
    failed = client.post("/api/v1/orders", json=payload(), headers=headers())
    assert failed.status_code == 409

    all_orders = client.get("/api/v1/orders", params={"page_size": 2}).json()
    assert all_orders["total"] == 3
    assert len(all_orders["items"]) == 2

    second_page = client.get(
        "/api/v1/orders", params={"page": 2, "page_size": 2}
    ).json()
    assert len(second_page["items"]) == 1

    confirmed = client.get(
        "/api/v1/orders", params={"status": "CONFIRMED"}
    ).json()
    assert confirmed["total"] == 2
    assert all(order["status"] == "CONFIRMED" for order in confirmed["items"])

    failed_orders = client.get(
        "/api/v1/orders", params={"status": "FAILED"}
    ).json()
    assert failed_orders["total"] == 1
    assert failed_orders["items"][0]["failure_code"] == "inventory_insufficient_stock"


def test_order_items_and_missing_order(client):
    created = client.post(
        "/api/v1/orders", json=payload(), headers=headers()
    ).json()

    items = client.get(f"/api/v1/orders/{created['id']}/items")
    assert items.status_code == 200
    assert len(items.json()["items"]) == 1

    missing = client.get("/api/v1/orders/00000000-0000-0000-0000-000000000000")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "order_not_found"


def test_order_creation_metrics(client):
    assert client.post(
        "/api/v1/orders", json=payload(), headers=headers()
    ).status_code == 201
    metrics = client.get("/metrics").text
    assert 'order_creation_attempts_total{outcome="confirmed"}' in metrics
