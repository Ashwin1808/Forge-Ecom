import uuid

import httpx
import pytest

from order_service.client import InventoryClient, InventoryClientError
from order_service.metrics import OrderMetrics

pytestmark = pytest.mark.unit


def make_client(handler, metrics=None) -> tuple[InventoryClient, httpx.AsyncClient]:
    async_client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://inventory-service",
    )
    client = InventoryClient(
        base_url="http://inventory-service",
        timeout_seconds=1.0,
        metrics=metrics or OrderMetrics(),
        client=async_client,
    )
    return client, async_client


async def test_reserve_parses_success_and_forwards_request_id():
    reservation_id = uuid.uuid4()
    product_id = uuid.uuid4()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-request-id"] == "trace-12345678"
        return httpx.Response(
            201,
            json={
                "id": str(reservation_id),
                "status": "RESERVED",
                "items": [
                    {
                        "product_id": str(product_id),
                        "sku": "KEY-001",
                        "name": "Keyboard",
                        "quantity": 2,
                        "unit_price_cents": 1000,
                        "currency": "USD",
                    }
                ],
            },
        )

    metrics = OrderMetrics()
    client, async_client = make_client(handler, metrics)
    try:
        result = await client.reserve(
            reservation_id=reservation_id,
            items=[(product_id, 2)],
            request_id="trace-12345678",
        )
    finally:
        await async_client.aclose()

    assert result.id == reservation_id
    assert result.items[0].unit_price_cents == 1000
    from prometheus_client import generate_latest

    assert 'downstream_requests_total{operation="reserve",outcome="success",target="inventory"} 1.0' in generate_latest(
        metrics.registry
    ).decode()


async def test_reserve_maps_insufficient_stock():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            409,
            json={
                "error": {
                    "code": "insufficient_stock",
                    "message": "not enough",
                    "details": {"shortages": []},
                },
                "request_id": "abc",
            },
        )

    client, async_client = make_client(handler)
    try:
        with pytest.raises(InventoryClientError) as raised:
            await client.reserve(reservation_id=uuid.uuid4(), items=[(uuid.uuid4(), 1)])
    finally:
        await async_client.aclose()
    assert raised.value.kind == "insufficient_stock"


async def test_reserve_maps_timeout():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    client, async_client = make_client(handler)
    try:
        with pytest.raises(InventoryClientError) as raised:
            await client.reserve(reservation_id=uuid.uuid4(), items=[(uuid.uuid4(), 1)])
    finally:
        await async_client.aclose()
    assert raised.value.kind == "timeout"


async def test_reserve_maps_malformed_response_to_protocol_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(201, json={"unexpected": "payload"})

    client, async_client = make_client(handler)
    try:
        with pytest.raises(InventoryClientError) as raised:
            await client.reserve(reservation_id=uuid.uuid4(), items=[(uuid.uuid4(), 1)])
    finally:
        await async_client.aclose()
    assert raised.value.kind == "protocol"


async def test_catalog_maps_not_found():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": {"code": "product_not_found"}})

    client, async_client = make_client(handler)
    try:
        with pytest.raises(InventoryClientError) as raised:
            await client.get_product(uuid.uuid4())
    finally:
        await async_client.aclose()
    assert raised.value.kind == "product_not_found"
