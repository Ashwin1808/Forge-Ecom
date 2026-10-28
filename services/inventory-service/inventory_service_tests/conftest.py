import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from inventory_service.config import Settings
from inventory_service.main import create_app
from inventory_service.models import Base

TEST_DATABASE_URL = os.getenv(
    "TEST_INVENTORY_DATABASE_URL",
    "postgresql+psycopg://postgres@localhost:55433/forge_inventory_test",
)


@pytest.fixture(scope="session")
def settings() -> Settings:
    return Settings(
        database_url=TEST_DATABASE_URL,
        environment="test",
        log_level="WARNING",
        rate_limit_per_minute=100_000,
        seed_on_start=False,
        db_pool_size=10,
        db_max_overflow=20,
    )


@pytest.fixture(scope="session")
def app(settings):
    application = create_app(settings)
    Base.metadata.drop_all(application.state.db.engine)
    Base.metadata.create_all(application.state.db.engine)
    yield application
    Base.metadata.drop_all(application.state.db.engine)
    application.state.db.dispose()


@pytest.fixture
def database(app):
    with app.state.db.engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE TABLE inventory_reservation_items, inventory_reservations, "
                "inventory, products RESTART IDENTITY CASCADE"
            )
        )
    return app.state.db


@pytest.fixture
def client(app, database):
    return TestClient(app)
