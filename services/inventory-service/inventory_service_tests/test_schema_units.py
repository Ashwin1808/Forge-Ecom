import uuid

import pytest
from pydantic import ValidationError

from inventory_service.schemas import ReservationCreate, reservation_fingerprint

pytestmark = pytest.mark.unit


def test_fingerprint_is_stable_across_item_order():
    product_a = uuid.uuid4()
    product_b = uuid.uuid4()
    reservation_id = uuid.uuid4()
    first = ReservationCreate(
        reservation_id=reservation_id,
        items=[
            {"product_id": product_a, "quantity": 1},
            {"product_id": product_b, "quantity": 2},
        ],
    )
    second = ReservationCreate(
        reservation_id=reservation_id,
        items=[
            {"product_id": product_b, "quantity": 2},
            {"product_id": product_a, "quantity": 1},
        ],
    )
    assert reservation_fingerprint(first) == reservation_fingerprint(second)


def test_fingerprint_changes_with_quantity():
    product = uuid.uuid4()
    reservation_id = uuid.uuid4()
    first = ReservationCreate(
        reservation_id=reservation_id,
        items=[{"product_id": product, "quantity": 1}],
    )
    second = ReservationCreate(
        reservation_id=reservation_id,
        items=[{"product_id": product, "quantity": 2}],
    )
    assert reservation_fingerprint(first) != reservation_fingerprint(second)


def test_duplicate_products_are_rejected():
    product = uuid.uuid4()
    with pytest.raises(ValidationError):
        ReservationCreate(
            reservation_id=uuid.uuid4(),
            items=[
                {"product_id": product, "quantity": 1},
                {"product_id": product, "quantity": 2},
            ],
        )
