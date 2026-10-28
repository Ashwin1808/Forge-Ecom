"""add reservation release state

Revision ID: 8d3f0b6a2c1e
Revises: 2f7d7d993203
Create Date: 2026-10-28 17:30:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '8d3f0b6a2c1e'
down_revision: str | None = '2f7d7d993203'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'inventory_reservations',
        sa.Column('released_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        op.f('ck_inventory_reservations_valid_status'),
        'inventory_reservations',
        "status IN ('RESERVED', 'RELEASED')",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f('ck_inventory_reservations_valid_status'),
        'inventory_reservations',
        type_='check',
    )
    op.drop_column('inventory_reservations', 'released_at')
