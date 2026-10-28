import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..client import InventoryClient, InventoryClientError
from ..config import Settings
from ..database import Database
from ..errors import ApiError
from ..metrics import OrderMetrics
from ..models import Order, OrderChannel, OrderStatus
from ..schemas import CheckoutCreate, OrderOut, checkout_fingerprint
from ..workflow import (
    IdempotencyMismatchError,
    IdempotencyRecordExistsError,
    ReservationMismatchError,
    create_pending_order,
    finalize_awaiting_payment,
    finalize_failed,
    load_order,
    lookup_idempotent_order,
)
from .orders import (
    FAILURE_DEFINITIONS,
    IDEMPOTENCY_KEY_PATTERN,
    failure_error,
    get_database,
    get_inventory,
    get_metrics,
    get_session,
    get_settings,
    order_to_out,
)

router = APIRouter(prefix="/api/v1/storefront", tags=["storefront"])
logger = logging.getLogger("order.storefront")


def replay_checkout(order: Order, metrics: OrderMetrics) -> OrderOut:
    if order.status == OrderStatus.PENDING.value:
        metrics.checkout_attempts.labels(outcome="in_progress").inc()
        raise ApiError(
            409,
            "checkout_in_progress",
            "This checkout is still being processed. Retry shortly.",
            details={"order_id": str(order.id)},
            headers={"Retry-After": "2"},
        )
    if order.status in {
        OrderStatus.AWAITING_PAYMENT.value,
        OrderStatus.CONFIRMED.value,
    }:
        metrics.checkout_attempts.labels(outcome="replay").inc()
        return order_to_out(order)
    if order.status == OrderStatus.EXPIRED.value:
        metrics.checkout_attempts.labels(outcome="expired").inc()
        raise ApiError(
            409,
            "checkout_expired",
            "This checkout reservation expired. Start a new checkout.",
            details={"order_id": str(order.id)},
        )
    metrics.checkout_attempts.labels(outcome="replay").inc()
    raise failure_error(
        order.id,
        order.failure_code or "checkout_failed",
        order.failure_message,
    )


@router.post("/checkout", response_model=OrderOut, status_code=201)
async def create_checkout(
    payload: CheckoutCreate,
    request: Request,
    idempotency_key: Annotated[
        str,
        Header(
            alias="Idempotency-Key",
            min_length=8,
            max_length=128,
            pattern=IDEMPOTENCY_KEY_PATTERN,
        ),
    ],
    settings: Annotated[Settings, Depends(get_settings)],
    metrics: Annotated[OrderMetrics, Depends(get_metrics)],
    inventory: Annotated[InventoryClient, Depends(get_inventory)],
) -> OrderOut:
    request_hash = checkout_fingerprint(payload)
    request_id = request.state.request_id
    database: Database = request.app.state.db

    try:
        existing = lookup_idempotent_order(
            database, key=idempotency_key, request_hash=request_hash
        )
    except IdempotencyMismatchError:
        metrics.checkout_attempts.labels(outcome="idempotency_conflict").inc()
        raise ApiError(
            409,
            "idempotency_conflict",
            "This Idempotency-Key was already used with a different checkout payload.",
        ) from None

    if existing is not None:
        return replay_checkout(existing, metrics)

    expires_at = datetime.now(timezone.utc) + timedelta(
        seconds=settings.checkout_reservation_ttl_seconds
    )
    try:
        order = create_pending_order(
            database,
            key=idempotency_key,
            request_hash=request_hash,
            payload=payload,
            currency=settings.store_currency,
            channel=OrderChannel.STOREFRONT.value,
            delivery_address=payload.delivery_address,
            reservation_expires_at=expires_at,
        )
    except IdempotencyRecordExistsError:
        try:
            existing = lookup_idempotent_order(
                database, key=idempotency_key, request_hash=request_hash
            )
        except IdempotencyMismatchError:
            metrics.checkout_attempts.labels(outcome="idempotency_conflict").inc()
            raise ApiError(
                409,
                "idempotency_conflict",
                "This Idempotency-Key was already used with a different checkout payload.",
            ) from None
        if existing is None:
            metrics.checkout_attempts.labels(outcome="error").inc()
            raise ApiError(500, "internal_error", "The checkout could not be created.")
        return replay_checkout(existing, metrics)

    items = [(item.product_id, item.quantity) for item in payload.items]
    try:
        reservation = await inventory.reserve(
            reservation_id=order.id, items=items, request_id=request_id
        )
    except InventoryClientError as exc:
        failure_code = f"inventory_{exc.kind}"
        failure_message = FAILURE_DEFINITIONS.get(
            failure_code, (500, "Inventory request failed.")
        )[1]
        finalize_failed(
            database,
            order_id=order.id,
            failure_code=failure_code,
            failure_message=failure_message,
            clear_reservation_expiry=exc.kind in {"insufficient_stock", "unknown_product"},
        )
        metrics.checkout_attempts.labels(outcome=exc.kind).inc()
        logger.warning(
            "checkout_inventory_failure",
            extra={
                "order_id": str(order.id),
                "failure_code": failure_code,
                "inventory_error": exc.kind,
            },
        )
        raise failure_error(order.id, failure_code) from None
    except Exception:
        finalize_failed(
            database,
            order_id=order.id,
            failure_code="internal_error",
            failure_message="The checkout could not be processed.",
        )
        metrics.checkout_attempts.labels(outcome="error").inc()
        raise

    try:
        finalize_awaiting_payment(
            database,
            order_id=order.id,
            reservation=reservation,
            reservation_ttl_seconds=settings.checkout_reservation_ttl_seconds,
        )
    except ReservationMismatchError:
        released = False
        try:
            await inventory.release(
                reservation_id=order.id, request_id=request_id
            )
            released = True
        except InventoryClientError as exc:
            logger.warning(
                "checkout_mismatch_release_failed",
                extra={"order_id": str(order.id), "inventory_error": exc.kind},
            )
        finalize_failed(
            database,
            order_id=order.id,
            failure_code="inventory_protocol",
            failure_message=FAILURE_DEFINITIONS["inventory_protocol"][1],
            clear_reservation_expiry=released,
        )
        metrics.checkout_attempts.labels(outcome="protocol").inc()
        logger.error(
            "checkout_reservation_mismatch",
            extra={"order_id": str(order.id)},
        )
        raise failure_error(order.id, "inventory_protocol") from None

    created = load_order(database, order.id)
    if created is None:
        metrics.checkout_attempts.labels(outcome="error").inc()
        raise ApiError(500, "internal_error", "The checkout could not be loaded.")
    metrics.checkout_attempts.labels(outcome="awaiting_payment").inc()
    logger.info(
        "checkout_awaiting_payment",
        extra={
            "order_id": str(created.id),
            "item_count": len(created.items),
            "total_cents": created.total_cents,
        },
    )
    return order_to_out(created)


@router.get("/orders/{order_id}", response_model=OrderOut)
def get_storefront_order(
    order_id: uuid.UUID,
    session: Annotated[Session, Depends(get_session)],
) -> OrderOut:
    order = session.execute(
        select(Order)
        .options(selectinload(Order.items))
        .where(
            Order.id == order_id,
            Order.channel == OrderChannel.STOREFRONT.value,
        )
    ).scalar_one_or_none()
    if order is None:
        raise ApiError(404, "order_not_found", "Order not found.")
    return order_to_out(order)
