"""track physical PostgreSQL databases used by the application

Revision ID: 0007_database_registry
Revises: 0006_revocable_sessions
"""
from alembic import op
import sqlalchemy as sa

revision = "0007_database_registry"
down_revision = "0006_revocable_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "database_registry",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("database_name", sa.String(63), nullable=False, unique=True),
        sa.Column("database_type", sa.String(16), nullable=False),
        sa.Column("business_type", sa.String(30), nullable=True),
        sa.Column("business_id", sa.Integer(), sa.ForeignKey("businesses.id", ondelete="CASCADE"), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("database_type IN ('admin', 'master', 'local')", name="ck_database_registry_type"),
        sa.CheckConstraint("status IN ('active', 'inactive')", name="ck_database_registry_status"),
        sa.CheckConstraint(
            "(database_type = 'admin' AND business_type IS NULL AND business_id IS NULL) OR "
            "(database_type = 'master' AND business_type IS NOT NULL AND business_id IS NULL) OR "
            "(database_type = 'local' AND business_type IS NOT NULL AND business_id IS NOT NULL)",
            name="ck_database_registry_scope",
        ),
    )
    op.create_index("ix_database_registry_type", "database_registry", ["database_type"])
    op.create_index("ix_database_registry_business", "database_registry", ["business_id"])
    registry = sa.table(
        "database_registry",
        sa.column("database_name", sa.String),
        sa.column("database_type", sa.String),
        sa.column("business_type", sa.String),
        sa.column("status", sa.String),
    )
    op.bulk_insert(
        registry,
        [
            {"database_name": "admin_db", "database_type": "admin", "business_type": None, "status": "active"},
            {"database_name": "master_medical", "database_type": "master", "business_type": "medical", "status": "active"},
            {"database_name": "master_grocery", "database_type": "master", "business_type": "grocery", "status": "active"},
            {"database_name": "master_restaurant", "database_type": "master", "business_type": "restaurant", "status": "active"},
            {"database_name": "master_stationery", "database_type": "master", "business_type": "stationery", "status": "active"},
            {"database_name": "master_dairy", "database_type": "master", "business_type": "dairy", "status": "active"},
        ],
    )


def downgrade() -> None:
    op.drop_table("database_registry")
