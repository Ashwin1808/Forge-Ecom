import uuid

import pytest

from order_service.client import InventoryClientError

pytestmark = pytest.mark.integration


def test_catalog_is_proxied_through_order_service(client):
    response = client.get("/api/v1/products", params={"page_size": 10})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert {item["name"] for item in body["items"]} == {"Fake Keyboard", "Fake Display"}

    product_id = body["items"][0]["id"]
    detail = client.get(f"/api/v1/products/{product_id}")
    assert detail.status_code == 200
    assert detail.json()["id"] == product_id


def test_catalog_timeout_maps_to_504(client, fake_inventory):
    fake_inventory.list_error = InventoryClientError("timeout", "timed out")
    response = client.get("/api/v1/products")
    assert response.status_code == 504
    assert response.json()["error"]["code"] == "catalog_timeout"


def test_catalog_unavailable_maps_to_503(client, fake_inventory):
    fake_inventory.list_error = InventoryClientError("unavailable", "down")
    response = client.get("/api/v1/products")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "catalog_unavailable"


def test_unknown_catalog_product_maps_to_404(client, fake_inventory):
    fake_inventory.get_error = InventoryClientError("product_not_found", "missing")
    response = client.get(f"/api/v1/products/{uuid.uuid4()}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "product_not_found"
