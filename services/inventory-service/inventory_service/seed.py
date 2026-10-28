import logging

from sqlalchemy import select

from .config import Settings, get_settings
from .database import Database
from .logging_setup import setup_logging
from .models import Inventory, Product

logger = logging.getLogger("inventory.seed")

SAMPLE_PRODUCTS = [
    {
        "sku": "KEY-001",
        "name": "Forge Mechanical Keyboard",
        "description": "Hot-swappable 75% keyboard with tactile switches.",
        "price_cents": 14900,
        "quantity": 42,
    },
    {
        "sku": "MON-002",
        "name": "Forge 27-inch Studio Display",
        "description": "4K IPS display with USB-C power delivery.",
        "price_cents": 42900,
        "quantity": 18,
    },
    {
        "sku": "MOU-003",
        "name": "Forge Precision Mouse",
        "description": "Low-latency wireless mouse with an aluminium body.",
        "price_cents": 7900,
        "quantity": 65,
    },
    {
        "sku": "HUB-004",
        "name": "Forge USB-C Hub",
        "description": "Seven-port hub with HDMI and gigabit Ethernet.",
        "price_cents": 5900,
        "quantity": 6,
    },
    {
        "sku": "CAM-005",
        "name": "Forge 4K Webcam",
        "description": "Privacy-shuttered webcam with dual microphones.",
        "price_cents": 11900,
        "quantity": 23,
    },
    {
        "sku": "STD-006",
        "name": "Forge Laptop Stand",
        "description": "Adjustable aluminium stand for 13 to 17-inch laptops.",
        "price_cents": 4900,
        "quantity": 0,
    },
]


def seed_products(database: Database, settings: Settings) -> int:
    created = 0
    with database.session() as session:
        for sample in SAMPLE_PRODUCTS:
            exists = session.scalar(select(Product.id).where(Product.sku == sample["sku"]))
            if exists is not None:
                continue
            product = Product(
                sku=sample["sku"],
                name=sample["name"],
                description=sample["description"],
                price_cents=sample["price_cents"],
                currency=settings.store_currency,
                active=True,
            )
            product.inventory = Inventory(
                quantity_available=sample["quantity"],
                quantity_reserved=0,
            )
            session.add(product)
            created += 1
        session.commit()
    logger.info("seed_complete", extra={"products_created": created})
    return created


def main() -> None:
    settings = get_settings()
    setup_logging(settings.app_name, settings.environment, settings.log_level)
    database = Database(
        settings.database_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        connect_timeout_seconds=settings.db_connect_timeout_seconds,
        statement_timeout_ms=settings.db_statement_timeout_ms,
    )
    try:
        seed_products(database, settings)
    finally:
        database.dispose()


if __name__ == "__main__":
    main()
