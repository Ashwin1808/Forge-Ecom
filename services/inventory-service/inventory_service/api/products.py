import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import Database
from ..errors import ApiError
from ..metrics import InventoryMetrics
from ..models import Inventory, Product
from ..schemas import ProductCreate, ProductListOut, ProductOut

router = APIRouter(prefix="/api/v1/products", tags=["products"])
logger = logging.getLogger("inventory.products")


def get_database(request: Request) -> Database:
    return request.app.state.db


def get_session(request: Request):
    database: Database = request.app.state.db
    with database.session() as session:
        yield session


def get_metrics(request: Request) -> InventoryMetrics:
    return request.app.state.metrics


def product_to_out(product: Product, inventory: Inventory) -> ProductOut:
    return ProductOut(
        id=product.id,
        sku=product.sku,
        name=product.name,
        description=product.description,
        price_cents=product.price_cents,
        currency=product.currency,
        quantity_available=inventory.quantity_available,
        quantity_reserved=inventory.quantity_reserved,
        in_stock=inventory.quantity_available > 0,
        created_at=product.created_at,
    )


@router.post("", response_model=ProductOut, status_code=201)
def create_product(
    payload: ProductCreate,
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    metrics: Annotated[InventoryMetrics, Depends(get_metrics)],
) -> ProductOut:
    settings = request.app.state.settings
    if payload.currency != settings.store_currency:
        raise ApiError(
            422,
            "unsupported_currency",
            f"Products must use the store currency {settings.store_currency}.",
        )

    product = Product(
        sku=payload.sku,
        name=payload.name,
        description=payload.description,
        price_cents=payload.price_cents,
        currency=payload.currency,
        active=True,
    )
    inventory = Inventory(
        quantity_available=payload.initial_quantity,
        quantity_reserved=0,
    )
    product.inventory = inventory
    session.add(product)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise ApiError(
            409, "product_sku_conflict", "A product with this SKU already exists."
        ) from None

    session.refresh(product)
    session.refresh(inventory)
    metrics.products_created.inc()
    logger.info(
        "product_created",
        extra={"product_id": str(product.id), "sku": product.sku},
    )
    return product_to_out(product, inventory)


@router.get("", response_model=ProductListOut)
def list_products(
    session: Annotated[Session, Depends(get_session)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ProductListOut:
    total = session.scalar(select(func.count()).select_from(Product)) or 0
    rows = session.execute(
        select(Product, Inventory)
        .join(Inventory, Inventory.product_id == Product.id)
        .order_by(Product.created_at.desc(), Product.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return ProductListOut(
        items=[product_to_out(product, inventory) for product, inventory in rows],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/{product_id}", response_model=ProductOut)
def get_product(
    product_id: uuid.UUID,
    session: Annotated[Session, Depends(get_session)],
) -> ProductOut:
    row = session.execute(
        select(Product, Inventory)
        .join(Inventory, Inventory.product_id == Product.id)
        .where(Product.id == product_id)
    ).one_or_none()
    if row is None:
        raise ApiError(404, "product_not_found", "Product not found.")
    product, inventory = row
    return product_to_out(product, inventory)
