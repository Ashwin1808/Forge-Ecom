import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ..database import Database
from ..errors import ApiError
from ..metrics import InventoryMetrics
from ..models import Reservation
from ..schemas import ReservationCreate, ReservationItemOut, ReservationOut, reservation_fingerprint
from ..transactions import (
    InsufficientStockError,
    ReservationConflictError,
    UnknownProductsError,
    load_reservation,
    reserve_stock,
)

router = APIRouter(prefix="/api/v1/inventory/reservations", tags=["inventory"])
logger = logging.getLogger("inventory.reservations")


def get_database(request: Request) -> Database:
    return request.app.state.db


def get_session(request: Request):
    database: Database = request.app.state.db
    with database.session() as session:
        yield session


def get_metrics(request: Request) -> InventoryMetrics:
    return request.app.state.metrics


def reservation_to_out(reservation: Reservation) -> ReservationOut:
    return ReservationOut(
        id=reservation.id,
        status=reservation.status,
        created_at=reservation.created_at,
        items=[
            ReservationItemOut(
                product_id=item.product_id,
                sku=item.product.sku,
                name=item.product.name,
                quantity=item.quantity,
                unit_price_cents=item.unit_price_cents,
                currency=item.currency,
            )
            for item in reservation.items
        ],
    )


@router.post("", status_code=201)
def create_reservation(
    payload: ReservationCreate,
    session: Annotated[Session, Depends(get_session)],
    database: Annotated[Database, Depends(get_database)],
    metrics: Annotated[InventoryMetrics, Depends(get_metrics)],
) -> JSONResponse:
    fingerprint = reservation_fingerprint(payload)
    items = [(item.product_id, item.quantity) for item in payload.items]
    try:
        created = reserve_stock(
            database.session_factory,
            reservation_id=payload.reservation_id,
            request_hash=fingerprint,
            items=items,
        )
    except InsufficientStockError as exc:
        metrics.reservation_attempts.labels(outcome="insufficient_stock").inc()
        raise ApiError(
            409,
            "insufficient_stock",
            "One or more products do not have enough stock.",
            details={"shortages": exc.shortages},
        ) from None
    except UnknownProductsError as exc:
        metrics.reservation_attempts.labels(outcome="unknown_product").inc()
        raise ApiError(
            404,
            "unknown_product",
            "One or more products do not exist or are inactive.",
            details={"product_ids": [str(product_id) for product_id in exc.product_ids]},
        ) from None
    except ReservationConflictError:
        metrics.reservation_attempts.labels(outcome="idempotency_conflict").inc()
        raise ApiError(
            409,
            "idempotency_conflict",
            "This reservation ID was already used with a different payload.",
        ) from None

    session.expire_all()
    reservation = load_reservation(session, payload.reservation_id)
    if reservation is None:
        metrics.reservation_attempts.labels(outcome="error").inc()
        raise ApiError(500, "internal_error", "Reservation could not be loaded.")

    metrics.reservation_attempts.labels(outcome="success" if created else "replay").inc()
    if created:
        metrics.units_reserved.inc(sum(item.quantity for item in payload.items))
    logger.info(
        "reservation_%s",
        "created" if created else "replayed",
        extra={
            "reservation_id": str(reservation.id),
            "item_count": len(reservation.items),
            "units": sum(item.quantity for item in reservation.items),
        },
    )
    body = reservation_to_out(reservation).model_dump(mode="json")
    return JSONResponse(status_code=201 if created else 200, content=body)


@router.get("/{reservation_id}", response_model=ReservationOut)
def get_reservation(
    reservation_id: uuid.UUID,
    session: Annotated[Session, Depends(get_session)],
) -> ReservationOut:
    reservation = load_reservation(session, reservation_id)
    if reservation is None:
        raise ApiError(404, "reservation_not_found", "Reservation not found.")
    return reservation_to_out(reservation)
