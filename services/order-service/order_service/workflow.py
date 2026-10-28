import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from .client import InventoryClient, InventoryClientError, InventoryReservation
from .database import Database
from .models import IdempotencyRecord, Order, OrderItem, OrderStatus, PaymentStatus
from .schemas import CheckoutCreate, DeliveryAddressIn, OrderCreate

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
    payload: OrderCreate | CheckoutCreate,
    currency: str,
    channel: str = "OPS",
    delivery_address: DeliveryAddressIn | None = None,
    reservation_expires_at: datetime | None = None,
) -> Order:
    order = Order(
        id=uuid.uuid4(),
        status=OrderStatus.PENDING.value,
        channel=channel,
        customer_name=payload.customer.name,
        customer_email=str(payload.customer.email),
        delivery_line1=delivery_address.line1 if delivery_address else None,
        delivery_line2=delivery_address.line2 if delivery_address else None,
        delivery_city=delivery_address.city if delivery_address else None,
        delivery_region=delivery_address.region if delivery_address else None,
        delivery_postal_code=(
            delivery_address.postal_code if delivery_address else None
        ),
        delivery_country=delivery_address.country if delivery_address else None,
        currency=currency,
        reservation_expires_at=reservation_expires_at,
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


def _apply_reservation(order: Order, reservation: InventoryReservation) -> int:
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
    return total


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

            _apply_reservation(order, reservation)
            order.status = OrderStatus.CONFIRMED.value
            order.failure_code = None
            order.failure_message = None
            return OrderStatus.CONFIRMED.value


def finalize_awaiting_payment(
    database: Database,
    *,
    order_id: uuid.UUID,
    reservation: InventoryReservation,
    reservation_ttl_seconds: int,
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

            _apply_reservation(order, reservation)
            order.status = OrderStatus.AWAITING_PAYMENT.value
            order.payment_status = PaymentStatus.CREATED.value
            order.reservation_expires_at = datetime.now(timezone.utc) + timedelta(
                seconds=reservation_ttl_seconds
            )
            order.failure_code = None
            order.failure_message = None
            return OrderStatus.AWAITING_PAYMENT.value


def finalize_failed(
    database: Database,
    *,
    order_id: uuid.UUID,
    failure_code: str,
    failure_message: str,
    clear_reservation_expiry: bool = False,
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
            if clear_reservation_expiry:
                order.reservation_expires_at = None
            logger.info(
                "order_failed",
                extra={"order_id": str(order_id), "failure_code": failure_code},
            )


async def expire_order(
    database: Database,
    inventory: InventoryClient,
    *,
    order_id: uuid.UUID,
    now: datetime | None = None,
) -> str | None:
    now = now or datetime.now(timezone.utc)
    order = load_order(database, order_id)
    if order is None or order.reservation_expires_at is None:
        return None
    if order.reservation_expires_at > now:
        return None
    if order.status not in {
        OrderStatus.PENDING.value,
        OrderStatus.AWAITING_PAYMENT.value,
        OrderStatus.FAILED.value,
    }:
        return None

    try:
        await inventory.release(reservation_id=order.id, request_id="expiry-worker")
    except InventoryClientError as exc:
        if exc.kind != "not_found":
            raise

    with database.session() as session:
        with session.begin():
            locked = session.execute(
                select(Order).where(Order.id == order_id).with_for_update()
            ).scalar_one_or_none()
            if locked is None or locked.reservation_expires_at is None:
                return None
            if locked.reservation_expires_at > now:
                return None
            if locked.status == OrderStatus.FAILED.value:
                locked.reservation_expires_at = None
                return locked.status
            if locked.status not in {
                OrderStatus.PENDING.value,
                OrderStatus.AWAITING_PAYMENT.value,
            }:
                return locked.status
            locked.status = OrderStatus.EXPIRED.value
            locked.failure_code = "reservation_expired"
            locked.failure_message = (
                "The checkout reservation expired before payment was completed."
            )
            logger.info("order_expired", extra={"order_id": str(order_id)})
            return OrderStatus.EXPIRED.value


async def expire_due_orders(
    database: Database,
    inventory: InventoryClient,
    *,
    now: datetime | None = None,
    batch_size: int = 50,
) -> int:
    now = now or datetime.now(timezone.utc)
    with database.session() as session:
        order_ids = session.scalars(
            select(Order.id)
            .where(
                Order.reservation_expires_at.is_not(None),
                Order.reservation_expires_at <= now,
                or_(
                    Order.status.in_(
                        (
                            OrderStatus.PENDING.value,
                            OrderStatus.AWAITING_PAYMENT.value,
                        )
                    ),
                    Order.status == OrderStatus.FAILED.value,
                ),
            )
            .order_by(Order.reservation_expires_at)
            .limit(batch_size)
        ).all()

    expired = 0
    for order_id in order_ids:
        try:
            status = await expire_order(database, inventory, order_id=order_id, now=now)
        except InventoryClientError as exc:
            logger.warning(
                "order_expiry_release_failed",
                extra={"order_id": str(order_id), "inventory_error": exc.kind},
            )
            continue
        except Exception:
            logger.exception("order_expiry_failed", extra={"order_id": str(order_id)})
            continue
        if status == OrderStatus.EXPIRED.value:
            expired += 1
    return expired
