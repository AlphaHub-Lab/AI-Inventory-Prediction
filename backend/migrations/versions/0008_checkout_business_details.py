"""add saved checkout details, business contact data, and owner email OTPs

Revision ID: 0008_checkout_business_details
Revises: 0007_database_registry
"""
from alembic import op
import sqlalchemy as sa

revision = "0008_checkout_business_details"
down_revision = "0007_database_registry"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("businesses", sa.Column("owner_phone", sa.String(40), nullable=True))
    op.add_column("businesses", sa.Column("owner_personal_email", sa.String(255), nullable=True))
    op.add_column("businesses", sa.Column("phone", sa.String(40), nullable=True))
    op.add_column("businesses", sa.Column("address", sa.Text(), nullable=True))
    op.add_column("checkout_transactions", sa.Column("customer_prescribed_by", sa.String(180), nullable=True))
    op.add_column("checkout_transactions", sa.Column("customer_address", sa.Text(), nullable=True))
    op.add_column("checkout_items", sa.Column("product_sku", sa.String(50), nullable=False, server_default=""))
    op.create_table(
        "owner_email_verifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("verified_at", sa.DateTime(), nullable=True),
        sa.Column("consumed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_owner_email_verifications_email", "owner_email_verifications", ["email"])
    op.create_index("ix_owner_email_verifications_expires_at", "owner_email_verifications", ["expires_at"])


def downgrade() -> None:
    op.drop_table("owner_email_verifications")
    op.drop_column("checkout_items", "product_sku")
    op.drop_column("checkout_transactions", "customer_address")
    op.drop_column("checkout_transactions", "customer_prescribed_by")
    op.drop_column("businesses", "address")
    op.drop_column("businesses", "phone")
    op.drop_column("businesses", "owner_personal_email")
    op.drop_column("businesses", "owner_phone")
