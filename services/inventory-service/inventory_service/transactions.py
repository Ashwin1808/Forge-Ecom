import logging
import uuid
from collections.abc import Sequence
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload, sessionmaker

from .models import Inventory, Product, Reservation, ReservationItem

logger = logging.getLogger("inventory.reservations")


class InsufficientStockError(Exception):
    def __init__(self, shortages: list[dict[str, object]]) -> None:
        super().__init__("insufficient stock")
        self.shortages = shortages


class UnknownProductsError(Exception):
    def __init__(self, product_ids: list[uuid.UUID]) -> None:
        super().__init__("unknown products")
        self.product_ids = product_ids


class ReservationConflictError(Exception):
    pass


def reserve_stock(
    session_factory: sessionmaker[Session],
    *,
    reservation_id: uuid.UUID,
    request_hash: str,
    items: Sequence[tuple[uuid.UUID, int]],
) -> bool:
    """Reserve stock atomically.

    Returns True when a new reservation was created, False for an idempotent replay.
    """
    requested = {product_id: quantity for product_id, quantity in items}
    product_ids = sorted(requested)

    with session_factory() as session:
        existing = session.get(Reservation, reservation_id)
        if existing is not None:
            if existing.request_hash != request_hash:
                raise ReservationConflictError
            return False

        reservation = Reservation(
            id=reservation_id,
            request_hash=request_hash,
            status="RESERVED",
        )
        session.add(reservation)
        try:
            session.flush()
        except IntegrityError:
            session.rollback()
            existing = session.get(Reservation, reservation_id)
            if existing is not None and existing.request_hash == request_hash:
                return False
            raise ReservationConflictError from None

        try:
            inventory_rows = (
                session.execute(
                    select(Inventory)
                    .where(Inventory.product_id.in_(product_ids))
                    .order_by(Inventory.product_id)
                    .with_for_update()
                )
                .scalars()
                .all()
            )
        except Exception:
            session.rollback()
            raise

        inventory_by_product = {row.product_id: row for row in inventory_rows}
        missing = [product_id for product_id in product_ids if product_id not in inventory_by_product]
        products = {
            product.id: product
            for product in session.execute(
                select(Product).where(Product.id.in_(product_ids))
            ).scalars()
        }
        missing.extend(
            product_id
            for product_id in product_ids
            if product_id in products and not products[product_id].active
        )
        if missing:
            session.rollback()
            raise UnknownProductsError(sorted(set(missing)))

        shortages: list[dict[str, object]] = []
        for product_id in product_ids:
            inventory = inventory_by_product[product_id]
            if inventory.quantity_available < requested[product_id]:
                shortages.append(
                    {
                        "product_id": str(product_id),
                        "requested": requested[product_id],
                        "available": inventory.quantity_available,
                    }
                )
        if shortages:
            session.rollback()
            raise InsufficientStockError(shortages)

        for product_id in product_ids:
            inventory = inventory_by_product[product_id]
            product = products[product_id]
            quantity = requested[product_id]
            inventory.quantity_available -= quantity
            inventory.quantity_reserved += quantity
            session.add(
                ReservationItem(
                    reservation_id=reservation_id,
                    product_id=product_id,
                    quantity=quantity,
                    unit_price_cents=product.price_cents,
                    currency=product.currency,
                )
            )

        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            raise
        return True


def release_stock(
    session_factory: sessionmaker[Session],
    *,
    reservation_id: uuid.UUID,
) -> tuple[bool, Reservation | None]:
    """Release a reservation and return stock to the available pool.

    Returns ``(True, reservation)`` when stock was released, ``(False, reservation)``
    when the reservation was already released, and ``(False, None)`` when it does not
    exist. Releasing is idempotent and safe to retry.
    """
    with session_factory() as session:
        with session.begin():
            reservation = session.execute(
                select(Reservation)
                .options(selectinload(Reservation.items))
                .where(Reservation.id == reservation_id)
                .with_for_update()
            ).scalar_one_or_none()
            if reservation is None:
                return False, None
            if reservation.status == "RELEASED":
                return False, reservation

            product_ids = sorted(item.product_id for item in reservation.items)
            inventory_rows = (
                session.execute(
                    select(Inventory)
                    .where(Inventory.product_id.in_(product_ids))
                    .order_by(Inventory.product_id)
                    .with_for_update()
                )
                .scalars()
                .all()
            )
            inventory_by_product = {row.product_id: row for row in inventory_rows}
            missing = [
                product_id
                for product_id in product_ids
                if product_id not in inventory_by_product
            ]
            if missing:
                raise RuntimeError("reservation references missing inventory rows")

            for item in reservation.items:
                inventory = inventory_by_product[item.product_id]
                inventory.quantity_available += item.quantity
                inventory.quantity_reserved -= item.quantity

            reservation.status = "RELEASED"
            reservation.released_at = datetime.now(timezone.utc)
            return True, reservation


def load_reservation(session: Session, reservation_id: uuid.UUID) -> Reservation | None:
    return session.execute(
        select(Reservation)
        .options(selectinload(Reservation.items).selectinload(ReservationItem.product))
        .where(Reservation.id == reservation_id)
    ).scalar_one_or_none()
