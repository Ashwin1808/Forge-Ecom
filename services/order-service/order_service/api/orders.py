import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..client import InventoryClient, InventoryClientError
from ..config import Settings
from ..database import Database
from ..errors import ApiError
from ..metrics import OrderMetrics
from ..models import Order, OrderChannel, OrderStatus, PaymentStatus
from ..schemas import (
    CustomerOut,
    DeliveryAddressOut,
    OrderCreate,
    OrderItemOut,
    OrderItemsOut,
    OrderListOut,
    OrderOut,
    order_fingerprint,
)
from ..workflow import (
    IdempotencyMismatchError,
    IdempotencyRecordExistsError,
    ReservationMismatchError,
    create_pending_order,
    finalize_confirmed,
    finalize_failed,
    load_order,
    lookup_idempotent_order,
)

router = APIRouter(prefix="/api/v1/orders", tags=["orders"])
logger = logging.getLogger("order.api")

IDEMPOTENCY_KEY_PATTERN = r"^[A-Za-z0-9._:-]{8,128}$"

FAILURE_DEFINITIONS: dict[str, tuple[int, str]] = {
    "inventory_insufficient_stock": (
        409,
        "One or more products do not have enough stock.",
    ),
    "inventory_unknown_product": (
        422,
        "One or more products do not exist or are no longer available.",
    ),
    "inventory_timeout": (
        504,
        "Inventory service did not respond in time. The order was not confirmed.",
    ),
    "inventory_unavailable": (
        503,
        "Inventory service is temporarily unavailable. The order was not confirmed.",
    ),
    "inventory_protocol": (
        502,
        "Inventory service returned an unexpected response. The order was not confirmed.",
    ),
    "internal_error": (
        500,
        "The order could not be processed.",
    ),
    "reservation_expired": (
        409,
        "The checkout reservation expired before payment was completed.",
    ),
}


def get_database(request: Request) -> Database:
    return request.app.state.db


def get_session(request: Request):
    database: Database = request.app.state.db
    with database.session() as session:
        yield session


def get_metrics(request: Request) -> OrderMetrics:
    return request.app.state.metrics


def get_inventory(request: Request) -> InventoryClient:
    return request.app.state.inventory_client


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def order_to_out(order: Order) -> OrderOut:
    delivery_address = None
    if order.delivery_line1 is not None:
        delivery_address = DeliveryAddressOut(
            line1=order.delivery_line1,
            line2=order.delivery_line2,
            city=order.delivery_city or "",
            region=order.delivery_region,
            postal_code=order.delivery_postal_code or "",
            country=order.delivery_country or "",
        )
    return OrderOut(
        id=order.id,
        status=OrderStatus(order.status),
        payment_status=(
            PaymentStatus(order.payment_status) if order.payment_status else None
        ),
        channel=OrderChannel(order.channel),
        customer=CustomerOut(name=order.customer_name, email=order.customer_email),
        delivery_address=delivery_address,
        items=[
            OrderItemOut(
                product_id=item.product_id,
                sku=item.sku,
                name=item.product_name,
                quantity=item.quantity,
                unit_price_cents=item.unit_price_cents,
                currency=item.currency,
                line_total_cents=item.line_total_cents,
            )
            for item in order.items
        ],
        total_cents=order.total_cents,
        currency=order.currency,
        reservation_expires_at=order.reservation_expires_at,
        failure_code=order.failure_code,
        failure_message=order.failure_message,
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


def failure_error(order_id: uuid.UUID, failure_code: str, message: str | None = None) -> ApiError:
    status_code, default_message = FAILURE_DEFINITIONS.get(
        failure_code, (409, "The order could not be confirmed.")
    )
    return ApiError(
        status_code,
        failure_code,
        message or default_message,
        details={"order_id": str(order_id)},
    )


def replay_order(order: Order, metrics: OrderMetrics) -> OrderOut:
    if order.status == OrderStatus.PENDING.value:
        metrics.order_attempts.labels(outcome="in_progress").inc()
        raise ApiError(
            409,
            "order_in_progress",
            "This order is still being processed. Retry shortly.",
            details={"order_id": str(order.id)},
            headers={"Retry-After": "2"},
        )
    if order.status in {
        OrderStatus.CONFIRMED.value,
        OrderStatus.AWAITING_PAYMENT.value,
    }:
        metrics.order_attempts.labels(outcome="replay").inc()
        return order_to_out(order)
    metrics.order_attempts.labels(outcome="replay").inc()
    raise failure_error(
        order.id,
        order.failure_code or "order_failed",
        order.failure_message,
    )


@router.post("", response_model=OrderOut, status_code=201)
async def create_order(
    payload: OrderCreate,
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
    request_hash = order_fingerprint(payload)
    request_id = request.state.request_id

    try:
        existing = lookup_idempotent_order(
            request.app.state.db, key=idempotency_key, request_hash=request_hash
        )
    except IdempotencyMismatchError:
        metrics.order_attempts.labels(outcome="idempotency_conflict").inc()
        raise ApiError(
            409,
            "idempotency_conflict",
            "This Idempotency-Key was already used with a different order payload.",
        ) from None

    if existing is not None:
        return replay_order(existing, metrics)

    database: Database = request.app.state.db
    try:
        order = create_pending_order(
            database,
            key=idempotency_key,
            request_hash=request_hash,
            payload=payload,
            currency=settings.store_currency,
        )
    except IdempotencyRecordExistsError:
        try:
            existing = lookup_idempotent_order(
                database, key=idempotency_key, request_hash=request_hash
            )
        except IdempotencyMismatchError:
            metrics.order_attempts.labels(outcome="idempotency_conflict").inc()
            raise ApiError(
                409,
                "idempotency_conflict",
                "This Idempotency-Key was already used with a different order payload.",
            ) from None
        if existing is None:
            metrics.order_attempts.labels(outcome="error").inc()
            raise ApiError(500, "internal_error", "The order could not be created.")
        return replay_order(existing, metrics)

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
        )
        metrics.order_attempts.labels(outcome=exc.kind).inc()
        logger.warning(
            "order_inventory_failure",
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
            failure_message="The order could not be processed.",
        )
        metrics.order_attempts.labels(outcome="error").inc()
        raise

    try:
        finalize_confirmed(database, order_id=order.id, reservation=reservation)
    except ReservationMismatchError:
        finalize_failed(
            database,
            order_id=order.id,
            failure_code="inventory_protocol",
            failure_message=FAILURE_DEFINITIONS["inventory_protocol"][1],
        )
        metrics.order_attempts.labels(outcome="protocol").inc()
        logger.error(
            "order_reservation_mismatch",
            extra={"order_id": str(order.id)},
        )
        raise failure_error(order.id, "inventory_protocol") from None

    confirmed = load_order(database, order.id)
    if confirmed is None:
        metrics.order_attempts.labels(outcome="error").inc()
        raise ApiError(500, "internal_error", "The order could not be loaded.")
    metrics.order_attempts.labels(outcome="confirmed").inc()
    logger.info(
        "order_confirmed",
        extra={
            "order_id": str(order.id),
            "item_count": len(confirmed.items),
            "total_cents": confirmed.total_cents,
        },
    )
    return order_to_out(confirmed)


@router.get("", response_model=OrderListOut)
def list_orders(
    session: Annotated[Session, Depends(get_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    status: Annotated[OrderStatus | None, Query()] = None,
) -> OrderListOut:
    filters = []
    if status is not None:
        filters.append(Order.status == status.value)

    total = session.scalar(select(func.count()).select_from(Order).where(*filters)) or 0
    orders = (
        session.execute(
            select(Order)
            .options(selectinload(Order.items))
            .where(*filters)
            .order_by(Order.created_at.desc(), Order.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    return OrderListOut(
        items=[order_to_out(order) for order in orders],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/{order_id}", response_model=OrderOut)
def get_order(
    order_id: uuid.UUID,
    session: Annotated[Session, Depends(get_session)],
) -> OrderOut:
    order = session.execute(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.id == order_id)
    ).scalar_one_or_none()
    if order is None:
        raise ApiError(404, "order_not_found", "Order not found.")
    return order_to_out(order)


@router.get("/{order_id}/items", response_model=OrderItemsOut)
def get_order_items(
    order_id: uuid.UUID,
    session: Annotated[Session, Depends(get_session)],
) -> OrderItemsOut:
    order = session.execute(
        select(Order)
        .options(selectinload(Order.items))
        .where(Order.id == order_id)
    ).scalar_one_or_none()
    if order is None:
        raise ApiError(404, "order_not_found", "Order not found.")
    return OrderItemsOut(items=order_to_out(order).items)
