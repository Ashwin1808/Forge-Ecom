import re
import uuid

import pytest

pytestmark = pytest.mark.integration


def create_product(client, sku="KEY-001", quantity=10):
    response = client.post(
        "/api/v1/products",
        json={
            "sku": sku,
            "name": f"Product {sku}",
            "price_cents": 1299,
            "currency": "USD",
            "initial_quantity": quantity,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def reserve(client, reservation_id, items):
    return client.post(
        "/api/v1/inventory/reservations",
        json={
            "reservation_id": str(reservation_id),
            "items": [
                {"product_id": str(product_id), "quantity": quantity}
                for product_id, quantity in items
            ],
        },
    )


def stock(client, product_id):
    return client.get(f"/api/v1/products/{product_id}").json()


def test_successful_reservation_decrements_available_stock(client):
    product = create_product(client, quantity=10)
    reservation_id = uuid.uuid4()

    response = reserve(client, reservation_id, [(product["id"], 3)])
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "RESERVED"
    assert body["items"][0]["quantity"] == 3
    assert body["items"][0]["unit_price_cents"] == 1299

    updated = stock(client, product["id"])
    assert updated["quantity_available"] == 7
    assert updated["quantity_reserved"] == 3

    fetched = client.get(f"/api/v1/inventory/reservations/{reservation_id}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == str(reservation_id)


def test_duplicate_reservation_is_idempotent(client):
    product = create_product(client, quantity=10)
    reservation_id = uuid.uuid4()

    first = reserve(client, reservation_id, [(product["id"], 4)])
    second = reserve(client, reservation_id, [(product["id"], 4)])

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert stock(client, product["id"])["quantity_available"] == 6


def test_same_reservation_id_with_different_payload_conflicts(client):
    product = create_product(client, quantity=10)
    reservation_id = uuid.uuid4()

    assert reserve(client, reservation_id, [(product["id"], 1)]).status_code == 201
    conflict = reserve(client, reservation_id, [(product["id"], 2)])

    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "idempotency_conflict"
    assert stock(client, product["id"])["quantity_available"] == 9


def test_insufficient_stock_is_rejected_without_state_change(client):
    product = create_product(client, quantity=2)
    response = reserve(client, uuid.uuid4(), [(product["id"], 3)])

    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "insufficient_stock"
    assert error["details"]["shortages"][0]["available"] == 2
    updated = stock(client, product["id"])
    assert updated["quantity_available"] == 2
    assert updated["quantity_reserved"] == 0


def test_unknown_product_is_rejected(client):
    response = reserve(
        client,
        uuid.uuid4(),
        [(uuid.uuid4(), 1)],
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "unknown_product"


def test_multi_product_reservation_is_atomic(client):
    first = create_product(client, sku="AAA-001", quantity=5)
    second = create_product(client, sku="BBB-002", quantity=1)

    response = reserve(
        client,
        uuid.uuid4(),
        [(first["id"], 2), (second["id"], 3)],
    )
    assert response.status_code == 409
    assert stock(client, first["id"])["quantity_available"] == 5
    assert stock(client, second["id"])["quantity_available"] == 1


@pytest.mark.parametrize(
    "items_factory",
    [
        lambda pid: [{"product_id": pid, "quantity": 0}],
        lambda pid: [{"product_id": pid, "quantity": 1001}],
        lambda pid: [
            {"product_id": pid, "quantity": 1},
            {"product_id": pid, "quantity": 2},
        ],
        lambda pid: [],
    ],
)
def test_invalid_reservation_payloads_are_rejected(client, items_factory):
    product = create_product(client, quantity=10)
    response = client.post(
        "/api/v1/inventory/reservations",
        json={
            "reservation_id": str(uuid.uuid4()),
            "items": items_factory(product["id"]),
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_reservation_metrics_record_outcome(client):
    product = create_product(client, quantity=10)
    assert reserve(client, uuid.uuid4(), [(product["id"], 1)]).status_code == 201
    metrics = client.get("/metrics").text
    assert re.search(
        r'inventory_reservation_attempts_total\{outcome="success"\} [1-9]', metrics
    )
    assert re.search(r"inventory_units_reserved_total [1-9]", metrics)
