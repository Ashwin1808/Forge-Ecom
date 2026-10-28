import uuid

import pytest
from fastapi.testclient import TestClient

from order_service.config import Settings
from order_service.main import create_app
from order_service.schemas import CatalogProductListOut

pytestmark = pytest.mark.integration


class StubInventoryClient:
    async def list_products(self, *, page, page_size, request_id=None):
        return CatalogProductListOut(items=[], page=page, page_size=page_size, total=0)

    async def get_product(self, product_id, *, request_id=None):
        raise RuntimeError("not used")

    async def reserve(self, **kwargs):
        raise RuntimeError("not used")

    async def aclose(self):
        return None


def build_app(**overrides):
    defaults = {
        "database_url": "postgresql+psycopg://postgres@localhost:55433/forge_orders_test",
        "environment": "test",
        "log_level": "WARNING",
        "cors_origins": "http://localhost:5173",
        "rate_limit_per_minute": 100_000,
    }
    defaults.update(overrides)
    return create_app(Settings(**defaults), inventory_client=StubInventoryClient())


def test_oversized_request_is_rejected_before_parsing():
    app = build_app(max_request_bytes=2048)
    client = TestClient(app)
    response = client.post(
        "/api/v1/orders",
        content=b"{" + b"a" * 5000 + b"}",
        headers={
            "Content-Type": "application/json",
            "Idempotency-Key": str(uuid.uuid4()),
        },
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "request_too_large"


def test_rate_limit_returns_429_and_retry_after():
    app = build_app(rate_limit_per_minute=2)
    client = TestClient(app)
    assert client.get("/api/v1/products").status_code == 200
    assert client.get("/api/v1/products").status_code == 200
    limited = client.get("/api/v1/products")
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "rate_limited"
    assert int(limited.headers["Retry-After"]) >= 1


def test_cors_preflight_only_allows_configured_origin():
    app = build_app()
    client = TestClient(app)
    allowed = client.options(
        "/api/v1/orders",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "idempotency-key,content-type",
        },
    )
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"

    denied = client.get(
        "/health", headers={"Origin": "https://evil.example"}
    )
    assert "access-control-allow-origin" not in denied.headers


def test_validation_errors_do_not_echo_input_values():
    app = build_app()
    client = TestClient(app)
    marker = "secret-marker-value"
    response = client.post(
        "/api/v1/orders",
        json={
            "customer": {"name": marker * 20, "email": f"{marker}-invalid"},
            "items": [{"product_id": str(uuid.uuid4()), "quantity": 1}],
        },
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert response.status_code == 422
    assert marker not in response.text
    assert response.json()["error"]["code"] == "validation_error"


def test_security_headers_are_present():
    app = build_app()
    client = TestClient(app)
    response = client.get("/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["Cache-Control"] == "no-store"


def test_storefront_checkout_requires_idempotency_key():
    app = build_app()
    client = TestClient(app)
    response = client.post(
        "/api/v1/storefront/checkout",
        json={
            "customer": {"name": "Grace Hopper", "email": "grace@example.com"},
            "delivery_address": {
                "line1": "1 Market Street",
                "city": "San Francisco",
                "postal_code": "94105",
                "country": "US",
            },
            "items": [{"product_id": str(uuid.uuid4()), "quantity": 1}],
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_storefront_oversized_request_is_rejected_before_parsing():
    app = build_app(max_request_bytes=2048)
    client = TestClient(app)
    response = client.post(
        "/api/v1/storefront/checkout",
        content=b"{" + b"a" * 5000 + b"}",
        headers={
            "Content-Type": "application/json",
            "Idempotency-Key": str(uuid.uuid4()),
        },
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "request_too_large"


def test_storefront_validation_errors_do_not_echo_input_values():
    app = build_app()
    client = TestClient(app)
    marker = "storefront-secret-marker"
    response = client.post(
        "/api/v1/storefront/checkout",
        json={
            "customer": {"name": "Grace Hopper", "email": f"{marker}-invalid"},
            "delivery_address": {
                "line1": marker * 20,
                "city": "San Francisco",
                "postal_code": "94105",
                "country": "US",
            },
            "items": [{"product_id": str(uuid.uuid4()), "quantity": 1}],
        },
        headers={"Idempotency-Key": str(uuid.uuid4())},
    )
    assert response.status_code == 422
    assert marker not in response.text
    assert response.json()["error"]["code"] == "validation_error"
