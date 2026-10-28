"""add storefront checkout fields

Revision ID: 4e8a1c2d7f90
Revises: 1809c26a66de
Create Date: 2026-10-28 18:00:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = '4e8a1c2d7f90'
down_revision: str | None = '1809c26a66de'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'orders',
        sa.Column('payment_status', sa.String(length=20), nullable=True),
    )
    op.add_column(
        'orders',
        sa.Column(
            'channel',
            sa.String(length=20),
            nullable=False,
            server_default='OPS',
        ),
    )
    op.add_column(
        'orders',
        sa.Column('delivery_line1', sa.String(length=200), nullable=True),
    )
    op.add_column(
        'orders',
        sa.Column('delivery_line2', sa.String(length=200), nullable=True),
    )
    op.add_column(
        'orders',
        sa.Column('delivery_city', sa.String(length=120), nullable=True),
    )
    op.add_column(
        'orders',
        sa.Column('delivery_region', sa.String(length=120), nullable=True),
    )
    op.add_column(
        'orders',
        sa.Column('delivery_postal_code', sa.String(length=32), nullable=True),
    )
    op.add_column(
        'orders',
        sa.Column('delivery_country', sa.String(length=80), nullable=True),
    )
    op.add_column(
        'orders',
        sa.Column(
            'reservation_expires_at',
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.drop_constraint(op.f('ck_orders_valid_status'), 'orders', type_='check')
    op.create_check_constraint(
        op.f('ck_orders_valid_status'),
        'orders',
        "status IN ('PENDING', 'AWAITING_PAYMENT', 'CONFIRMED', 'FAILED', 'EXPIRED')",
    )
    op.create_check_constraint(
        op.f('ck_orders_valid_payment_status'),
        'orders',
        "payment_status IS NULL OR payment_status IN "
        "('CREATED', 'PENDING', 'PAID', 'FAILED', 'REFUNDED')",
    )
    op.create_check_constraint(
        op.f('ck_orders_valid_channel'),
        'orders',
        "channel IN ('OPS', 'STOREFRONT')",
    )
    op.create_index(
        'ix_orders_reservation_expires_at',
        'orders',
        ['reservation_expires_at'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_orders_reservation_expires_at', table_name='orders')
    op.drop_constraint(op.f('ck_orders_valid_channel'), 'orders', type_='check')
    op.drop_constraint(op.f('ck_orders_valid_payment_status'), 'orders', type_='check')
    op.drop_constraint(op.f('ck_orders_valid_status'), 'orders', type_='check')
    op.create_check_constraint(
        op.f('ck_orders_valid_status'),
        'orders',
        "status IN ('PENDING', 'CONFIRMED', 'FAILED')",
    )
    op.drop_column('orders', 'reservation_expires_at')
    op.drop_column('orders', 'delivery_country')
    op.drop_column('orders', 'delivery_postal_code')
    op.drop_column('orders', 'delivery_region')
    op.drop_column('orders', 'delivery_city')
    op.drop_column('orders', 'delivery_line2')
    op.drop_column('orders', 'delivery_line1')
    op.drop_column('orders', 'channel')
    op.drop_column('orders', 'payment_status')
