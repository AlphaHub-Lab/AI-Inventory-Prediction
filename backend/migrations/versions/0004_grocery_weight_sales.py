"""add grocery-only gram inventory and selling defaults

Revision ID: 0004_grocery_weight_sales
Revises: 0003_checkout
Create Date: 2026-09-25
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0004_grocery_weight_sales"
down_revision = "0003_checkout"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    existing_tables = set(inspect(bind).get_table_names())

    def add_if_missing(table: str, column: sa.Column) -> None:
        if table in existing_tables and column.name not in {item["name"] for item in inspect(bind).get_columns(table)}:
            op.add_column(table, column)

    for name, type_, default in (
        ("is_grocery", sa.Boolean(), sa.false()),
        ("default_weight_unit", sa.String(length=2), "kg"),
        ("default_weight_g", sa.Integer(), "1000"),
        ("weight_increment_g", sa.Integer(), "500"),
        ("minimum_weight_g", sa.Integer(), "100"),
        ("maximum_weight_g", sa.Integer(), "100000"),
    ):
        add_if_missing("categories", sa.Column(name, type_, nullable=False, server_default=default))

    for name, type_, nullable in (
        ("is_weight_based", sa.Boolean(), False),
        ("weight_unit", sa.String(length=2), True),
        ("default_weight_g", sa.Integer(), True),
        ("weight_increment_g", sa.Integer(), True),
        ("minimum_weight_g", sa.Integer(), True),
        ("maximum_weight_g", sa.Integer(), True),
        ("weight_stock_g", sa.Integer(), True),
    ):
        add_if_missing("products", sa.Column(name, type_, nullable=nullable, **({"server_default": sa.false()} if name == "is_weight_based" else {})))
    add_if_missing("inventory_transactions", sa.Column("weight_delta_g", sa.Integer(), nullable=True))
    add_if_missing("checkout_items", sa.Column("selected_weight_g", sa.Integer(), nullable=True))
    add_if_missing("checkout_items", sa.Column("weight_unit", sa.String(length=2), nullable=True))

    # Mark the already-created Groceries workspace's categories as grocery-only;
    # medical and general retail workspaces retain the default false value.
    op.execute(sa.text("""
        UPDATE categories SET is_grocery = TRUE
        WHERE business_id IN (SELECT id FROM businesses WHERE lower(name) LIKE '%grocer%')
    """))


def downgrade() -> None:
    op.drop_column("checkout_items", "weight_unit")
    op.drop_column("checkout_items", "selected_weight_g")
    op.drop_column("inventory_transactions", "weight_delta_g")
    op.drop_column("products", "weight_stock_g")
    op.drop_column("products", "maximum_weight_g")
    op.drop_column("products", "minimum_weight_g")
    op.drop_column("products", "weight_increment_g")
    op.drop_column("products", "default_weight_g")
    op.drop_column("products", "weight_unit")
    op.drop_column("products", "is_weight_based")
    op.drop_column("categories", "maximum_weight_g")
    op.drop_column("categories", "minimum_weight_g")
    op.drop_column("categories", "weight_increment_g")
    op.drop_column("categories", "default_weight_g")
    op.drop_column("categories", "default_weight_unit")
    op.drop_column("categories", "is_grocery")
