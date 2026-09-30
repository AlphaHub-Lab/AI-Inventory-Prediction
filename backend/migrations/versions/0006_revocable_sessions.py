"""persist revocable authentication sessions

Revision ID: 0006_revocable_sessions
Revises: 0005_business_types_roles
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0006_revocable_sessions"
down_revision = "0005_business_types_roles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "auth_sessions" in inspect(bind).get_table_names():
        return
    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_index("ix_auth_sessions_expires_at", "auth_sessions", ["expires_at"])


def downgrade() -> None:
    op.drop_table("auth_sessions")
