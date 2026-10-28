import pytest

pytestmark = pytest.mark.integration


def create_product(client, sku="KEY-001", quantity=10, price=14900):
    response = client.post(
        "/api/v1/products",
        json={
            "sku": sku,
            "name": f"Product {sku}",
            "description": "Test product",
            "price_cents": price,
            "currency": "USD",
            "initial_quantity": quantity,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_create_product_with_inventory(client):
    product = create_product(client)
    assert product["sku"] == "KEY-001"
    assert product["quantity_available"] == 10
    assert product["quantity_reserved"] == 0
    assert product["in_stock"] is True
    assert product["price_cents"] == 14900


def test_product_is_persisted_and_retrievable(client):
    product = create_product(client, sku="MON-002", quantity=3)
    by_id = client.get(f"/api/v1/products/{product['id']}")
    assert by_id.status_code == 200
    assert by_id.json()["id"] == product["id"]

    listing = client.get("/api/v1/products")
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["sku"] == "MON-002"


def test_duplicate_sku_is_rejected(client):
    create_product(client, sku="HUB-004")
    response = client.post(
        "/api/v1/products",
        json={
            "sku": "HUB-004",
            "name": "Duplicate",
            "price_cents": 100,
            "initial_quantity": 1,
        },
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "product_sku_conflict"


def test_product_pagination_and_empty_state(client):
    empty = client.get("/api/v1/products").json()
    assert empty == {"items": [], "page": 1, "page_size": 20, "total": 0}

    for index in range(3):
        create_product(client, sku=f"SKU-{index:03d}", quantity=index)

    first = client.get("/api/v1/products", params={"page": 1, "page_size": 2}).json()
    second = client.get("/api/v1/products", params={"page": 2, "page_size": 2}).json()
    assert first["total"] == 3
    assert len(first["items"]) == 2
    assert len(second["items"]) == 1


def test_unknown_product_returns_404(client):
    response = client.get("/api/v1/products/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "product_not_found"


@pytest.mark.parametrize(
    "payload",
    [
        {"sku": "bad sku", "name": "Bad", "price_cents": 100},
        {"sku": "OK-1", "name": " ", "price_cents": 100},
        {"sku": "OK-2", "name": "Bad", "price_cents": 0},
        {"sku": "OK-3", "name": "Bad", "price_cents": 100, "initial_quantity": -1},
        {"sku": "OK-4", "name": "Bad", "price_cents": 100, "currency": "EURO"},
    ],
)
def test_invalid_product_payloads_are_rejected(client, payload):
    response = client.post("/api/v1/products", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_product_currency_must_match_store_currency(client):
    response = client.post(
        "/api/v1/products",
        json={
            "sku": "GBP-001",
            "name": "Pound product",
            "price_cents": 100,
            "currency": "GBP",
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unsupported_currency"
