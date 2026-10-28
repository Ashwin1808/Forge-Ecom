import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any

import httpx
from pydantic import BaseModel, ValidationError

from .metrics import OrderMetrics
from .schemas import CatalogProductListOut, CatalogProductOut

logger = logging.getLogger("order.inventory_client")

TARGET = "inventory"


class InventoryClientError(Exception):
    def __init__(
        self,
        kind: str,
        message: str,
        *,
        details: Any = None,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.details = details
        self.status_code = status_code


@dataclass(frozen=True)
class ReservedLine:
    product_id: uuid.UUID
    sku: str
    name: str
    quantity: int
    unit_price_cents: int
    currency: str


@dataclass(frozen=True)
class InventoryReservation:
    id: uuid.UUID
    status: str
    items: list[ReservedLine]


class _ReservationItemPayload(BaseModel):
    product_id: uuid.UUID
    sku: str
    name: str
    quantity: int
    unit_price_cents: int
    currency: str


class _ReservationPayload(BaseModel):
    id: uuid.UUID
    status: str
    items: list[_ReservationItemPayload]


class InventoryClient:
    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float,
        metrics: OrderMetrics,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url
        self.metrics = metrics
        self._client = client or httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(
                timeout_seconds,
                connect=min(timeout_seconds, 1.5),
                pool=min(timeout_seconds, 2.0),
            ),
            headers={"User-Agent": "forge-order-service/0.1.0"},
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def reserve(
        self,
        *,
        reservation_id: uuid.UUID,
        items: list[tuple[uuid.UUID, int]],
        request_id: str | None = None,
    ) -> InventoryReservation:
        body = {
            "reservation_id": str(reservation_id),
            "items": [
                {"product_id": str(product_id), "quantity": quantity}
                for product_id, quantity in items
            ],
        }
        headers = {"X-Request-ID": request_id} if request_id else {}
        started = time.perf_counter()
        try:
            response = await self._client.post(
                "/api/v1/inventory/reservations", json=body, headers=headers
            )
        except httpx.TimeoutException as exc:
            self._record("reserve", "timeout", started)
            logger.warning(
                "inventory_reservation_timeout",
                extra={"reservation_id": str(reservation_id)},
            )
            raise InventoryClientError(
                "timeout", "Inventory service timed out."
            ) from exc
        except httpx.RequestError as exc:
            self._record("reserve", "unavailable", started)
            logger.warning(
                "inventory_reservation_unavailable",
                extra={"reservation_id": str(reservation_id)},
            )
            raise InventoryClientError(
                "unavailable", "Inventory service is unavailable."
            ) from exc

        if response.status_code in {200, 201}:
            self._record("reserve", "success", started)
            try:
                payload = _ReservationPayload.model_validate(response.json())
            except (ValidationError, ValueError) as exc:
                logger.error(
                    "inventory_reservation_invalid_response",
                    extra={"reservation_id": str(reservation_id)},
                )
                raise InventoryClientError(
                    "protocol", "Inventory service returned an invalid response."
                ) from exc
            return InventoryReservation(
                id=payload.id,
                status=payload.status,
                items=[
                    ReservedLine(
                        product_id=item.product_id,
                        sku=item.sku,
                        name=item.name,
                        quantity=item.quantity,
                        unit_price_cents=item.unit_price_cents,
                        currency=item.currency,
                    )
                    for item in payload.items
                ],
            )

        error_code, details = self._parse_error(response)
        if response.status_code == 409 and error_code == "insufficient_stock":
            self._record("reserve", "insufficient_stock", started)
            raise InventoryClientError(
                "insufficient_stock",
                "Insufficient inventory for the requested items.",
                details=details,
                status_code=response.status_code,
            )
        if response.status_code == 404 and error_code == "unknown_product":
            self._record("reserve", "unknown_product", started)
            raise InventoryClientError(
                "unknown_product",
                "One or more products do not exist.",
                details=details,
                status_code=response.status_code,
            )

        self._record("reserve", "protocol", started)
        logger.error(
            "inventory_reservation_rejected",
            extra={
                "reservation_id": str(reservation_id),
                "upstream_status": response.status_code,
                "upstream_error_code": error_code,
            },
        )
        raise InventoryClientError(
            "protocol",
            "Inventory service rejected the reservation unexpectedly.",
            details=details,
            status_code=response.status_code,
        )

    async def list_products(
        self, *, page: int, page_size: int, request_id: str | None = None
    ) -> CatalogProductListOut:
        headers = {"X-Request-ID": request_id} if request_id else {}
        started = time.perf_counter()
        try:
            response = await self._client.get(
                "/api/v1/products",
                params={"page": page, "page_size": page_size},
                headers=headers,
            )
        except httpx.TimeoutException as exc:
            self._record("list_products", "timeout", started)
            raise InventoryClientError("timeout", "Inventory service timed out.") from exc
        except httpx.RequestError as exc:
            self._record("list_products", "unavailable", started)
            raise InventoryClientError(
                "unavailable", "Inventory service is unavailable."
            ) from exc

        if response.status_code != 200:
            self._record("list_products", "protocol", started)
            raise InventoryClientError(
                "unavailable", "Inventory service is unavailable.", status_code=response.status_code
            )
        try:
            products = CatalogProductListOut.model_validate(response.json())
        except (ValidationError, ValueError) as exc:
            self._record("list_products", "protocol", started)
            raise InventoryClientError(
                "protocol", "Inventory service returned an invalid response."
            ) from exc
        self._record("list_products", "success", started)
        return products

    async def get_product(
        self, product_id: uuid.UUID, *, request_id: str | None = None
    ) -> CatalogProductOut:
        headers = {"X-Request-ID": request_id} if request_id else {}
        started = time.perf_counter()
        try:
            response = await self._client.get(
                f"/api/v1/products/{product_id}", headers=headers
            )
        except httpx.TimeoutException as exc:
            self._record("get_product", "timeout", started)
            raise InventoryClientError("timeout", "Inventory service timed out.") from exc
        except httpx.RequestError as exc:
            self._record("get_product", "unavailable", started)
            raise InventoryClientError(
                "unavailable", "Inventory service is unavailable."
            ) from exc

        if response.status_code == 404:
            self._record("get_product", "not_found", started)
            raise InventoryClientError(
                "product_not_found", "Product not found.", status_code=404
            )
        if response.status_code != 200:
            self._record("get_product", "unavailable", started)
            raise InventoryClientError(
                "unavailable", "Inventory service is unavailable.", status_code=response.status_code
            )
        try:
            product = CatalogProductOut.model_validate(response.json())
        except (ValidationError, ValueError) as exc:
            self._record("get_product", "protocol", started)
            raise InventoryClientError(
                "protocol", "Inventory service returned an invalid response."
            ) from exc
        self._record("get_product", "success", started)
        return product

    @staticmethod
    def _parse_error(response: httpx.Response) -> tuple[str | None, Any]:
        try:
            payload = response.json()
        except ValueError:
            return None, None
        error = payload.get("error") if isinstance(payload, dict) else None
        if not isinstance(error, dict):
            return None, None
        return error.get("code"), error.get("details")

    def _record(self, operation: str, outcome: str, started: float) -> None:
        self.metrics.downstream_requests.labels(
            target=TARGET, operation=operation, outcome=outcome
        ).inc()
        self.metrics.downstream_latency.labels(
            target=TARGET, operation=operation
        ).observe(time.perf_counter() - started)
