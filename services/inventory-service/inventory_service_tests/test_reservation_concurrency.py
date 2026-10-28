import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import select

from inventory_service.models import Inventory, Reservation
from inventory_service.transactions import InsufficientStockError, reserve_stock

pytestmark = pytest.mark.integration


def create_product(client, sku="CON-001", quantity=5):
    response = client.post(
        "/api/v1/products",
        json={
            "sku": sku,
            "name": "Concurrency product",
            "price_cents": 500,
            "currency": "USD",
            "initial_quantity": quantity,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_concurrent_reservations_do_not_oversell(client, database):
    product = create_product(client, quantity=5)
    product_id = uuid.UUID(product["id"])

    def attempt(_index: int) -> str:
        try:
            reserve_stock(
                database.session_factory,
                reservation_id=uuid.uuid4(),
                request_hash=uuid.uuid4().hex,
                items=[(product_id, 1)],
            )
            return "reserved"
        except InsufficientStockError:
            return "rejected"

    with ThreadPoolExecutor(max_workers=12) as executor:
        results = list(executor.map(attempt, range(20)))

    assert results.count("reserved") == 5
    assert results.count("rejected") == 15

    with database.session() as session:
        inventory = session.get(Inventory, product_id)
        assert inventory is not None
        assert inventory.quantity_available == 0
        assert inventory.quantity_reserved == 5
        reservation_count = len(session.scalars(select(Reservation)).all())
        assert reservation_count == 5


def test_concurrent_duplicate_reservation_decrements_once(client, database):
    product = create_product(client, sku="CON-002", quantity=5)
    product_id = uuid.UUID(product["id"])
    reservation_id = uuid.uuid4()

    def attempt(_index: int) -> bool:
        return reserve_stock(
            database.session_factory,
            reservation_id=reservation_id,
            request_hash="same-payload-hash",
            items=[(product_id, 2)],
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(attempt, range(8)))

    assert results.count(True) == 1
    assert results.count(False) == 7

    with database.session() as session:
        inventory = session.get(Inventory, product_id)
        assert inventory is not None
        assert inventory.quantity_available == 3
        assert inventory.quantity_reserved == 2
        assert len(session.scalars(select(Reservation)).all()) == 1
