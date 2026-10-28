import logging
import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from .client import InventoryReservation
from .database import Database
from .models import IdempotencyRecord, Order, OrderItem, OrderStatus
from .schemas import OrderCreate

logger = logging.getLogger("order.workflow")


class IdempotencyMismatchError(Exception):
    pass


class IdempotencyRecordExistsError(Exception):
    pass


class OrderNotFoundError(Exception):
    pass


class ReservationMismatchError(Exception):
    pass


def lookup_idempotent_order(
    database: Database, *, key: str, request_hash: str
) -> Order | None:
    with database.session() as session:
        record = session.get(IdempotencyRecord, key)
        if record is None:
            return None
        if record.request_hash != request_hash:
            raise IdempotencyMismatchError
        order = session.execute(
            select(Order)
            .options(selectinload(Order.items))
            .where(Order.id == record.order_id)
        ).scalar_one_or_none()
        if order is None:
            raise RuntimeError("idempotency record references a missing order")
        return order


def create_pending_order(
    database: Database,
    *,
    key: str,
    request_hash: str,
    payload: OrderCreate,
    currency: str,
) -> Order:
    order = Order(
        id=uuid.uuid4(),
        status=OrderStatus.PENDING.value,
        customer_name=payload.customer.name,
        customer_email=str(payload.customer.email),
        currency=currency,
        items=[
            OrderItem(product_id=item.product_id, quantity=item.quantity)
            for item in payload.items
        ],
    )
    record = IdempotencyRecord(
        key=key,
        request_hash=request_hash,
        order_id=order.id,
    )
    with database.session() as session:
        session.add(order)
        session.add(record)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            raise IdempotencyRecordExistsError from None
    return order


def load_order(database: Database, order_id: uuid.UUID) -> Order | None:
    with database.session() as session:
        return session.execute(
            select(Order)
            .options(selectinload(Order.items))
            .where(Order.id == order_id)
        ).scalar_one_or_none()


def finalize_confirmed(
    database: Database,
    *,
    order_id: uuid.UUID,
    reservation: InventoryReservation,
) -> str:
    with database.session() as session:
        with session.begin():
            order = session.execute(
                select(Order)
                .options(selectinload(Order.items))
                .where(Order.id == order_id)
                .with_for_update()
            ).scalar_one_or_none()
            if order is None:
                raise OrderNotFoundError
            if order.status != OrderStatus.PENDING.value:
                return order.status

            reserved: dict[uuid.UUID, object] = {}
            for line in reservation.items:
                if line.product_id in reserved:
                    raise ReservationMismatchError("duplicate product in reservation")
                reserved[line.product_id] = line

            requested = {item.product_id: item.quantity for item in order.items}
            if set(reserved) != set(requested):
                raise ReservationMismatchError("reservation products do not match order")
            for product_id, quantity in requested.items():
                if reserved[product_id].quantity != quantity:
                    raise ReservationMismatchError("reservation quantities do not match order")

            currencies = {line.currency for line in reservation.items}
            if len(currencies) != 1:
                raise ReservationMismatchError("reservation uses multiple currencies")
            currency = currencies.pop()

            total = 0
            for item in order.items:
                line = reserved[item.product_id]
                line_total = line.unit_price_cents * item.quantity
                item.sku = line.sku
                item.product_name = line.name
                item.unit_price_cents = line.unit_price_cents
                item.currency = line.currency
                item.line_total_cents = line_total
                total += line_total

            order.currency = currency
            order.total_cents = total
            order.status = OrderStatus.CONFIRMED.value
            order.failure_code = None
            order.failure_message = None
            return OrderStatus.CONFIRMED.value


def finalize_failed(
    database: Database,
    *,
    order_id: uuid.UUID,
    failure_code: str,
    failure_message: str,
) -> None:
    with database.session() as session:
        with session.begin():
            order = session.execute(
                select(Order).where(Order.id == order_id).with_for_update()
            ).scalar_one_or_none()
            if order is None or order.status != OrderStatus.PENDING.value:
                return
            order.status = OrderStatus.FAILED.value
            order.failure_code = failure_code
            order.failure_message = failure_message[:500]
            logger.info(
                "order_failed",
                extra={"order_id": str(order_id), "failure_code": failure_code},
            )
