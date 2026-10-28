import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from ..client import InventoryClient, InventoryClientError
from ..errors import ApiError
from ..schemas import CatalogProductListOut, CatalogProductOut

router = APIRouter(prefix="/api/v1/products", tags=["catalog"])


def get_inventory(request: Request) -> InventoryClient:
    return request.app.state.inventory_client


def catalog_error(exc: InventoryClientError) -> ApiError:
    if exc.kind == "product_not_found":
        return ApiError(404, "product_not_found", "Product not found.")
    if exc.kind == "timeout":
        return ApiError(
            504, "catalog_timeout", "Inventory service did not respond in time."
        )
    if exc.kind in {"unavailable", "protocol"}:
        return ApiError(
            503, "catalog_unavailable", "Product catalog is temporarily unavailable."
        )
    return ApiError(502, "catalog_error", "Product catalog request failed.")


@router.get("", response_model=CatalogProductListOut)
async def list_products(
    request: Request,
    inventory: Annotated[InventoryClient, Depends(get_inventory)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> CatalogProductListOut:
    try:
        return await inventory.list_products(
            page=page, page_size=page_size, request_id=request.state.request_id
        )
    except InventoryClientError as exc:
        raise catalog_error(exc) from None


@router.get("/{product_id}", response_model=CatalogProductOut)
async def get_product(
    product_id: uuid.UUID,
    request: Request,
    inventory: Annotated[InventoryClient, Depends(get_inventory)],
) -> CatalogProductOut:
    try:
        return await inventory.get_product(
            product_id, request_id=request.state.request_id
        )
    except InventoryClientError as exc:
        raise catalog_error(exc) from None
