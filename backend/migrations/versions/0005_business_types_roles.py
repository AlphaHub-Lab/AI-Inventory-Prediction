"""enforce the three application roles and register business database mapping

Revision ID: 0005_business_types_roles
Revises: 0004_grocery_weight_sales
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0005_business_types_roles"
down_revision = "0004_grocery_weight_sales"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {col["name"] for col in inspect(bind).get_columns("businesses")}
    if "business_type" not in columns:
        op.add_column("businesses", sa.Column("business_type", sa.String(30), nullable=False, server_default="grocery"))
    if "master_database_name" not in columns:
        op.add_column("businesses", sa.Column("master_database_name", sa.String(63), nullable=False, server_default="master_grocery"))
    if "local_database_name" not in columns:
        op.add_column("businesses", sa.Column("local_database_name", sa.String(63), nullable=True))
    unique_columns = {tuple(c.get("column_names") or []) for c in inspect(bind).get_unique_constraints("businesses")}
    if ("local_database_name",) not in unique_columns:
        op.create_unique_constraint("uq_business_local_database_name", "businesses", ["local_database_name"])
    if "ix_businesses_business_type" not in {i["name"] for i in inspect(bind).get_indexes("businesses")}:
        op.create_index("ix_businesses_business_type", "businesses", ["business_type"])
    op.execute(sa.text("UPDATE businesses SET local_database_name = 'local_business_' || id::text WHERE local_database_name IS NULL"))
    if "ck_businesses_supported_type" not in {c.get("name") for c in inspect(bind).get_check_constraints("businesses")}:
        op.create_check_constraint("ck_businesses_supported_type", "businesses", "business_type IN ('medical', 'grocery', 'restaurant', 'stationery', 'dairy')")
    op.execute(sa.text("""
        UPDATE users SET role = CASE role
          WHEN 'staff' THEN 'associate'
          WHEN 'manager' THEN 'business_owner'
          ELSE role END
    """))
    op.execute(sa.text("UPDATE users SET role = 'associate' WHERE role NOT IN ('admin', 'business_owner', 'associate')"))
    if "ck_users_supported_role" not in {c.get("name") for c in inspect(bind).get_check_constraints("users")}:
        op.create_check_constraint("ck_users_supported_role", "users", "role IN ('admin', 'business_owner', 'associate')")
    op.execute(sa.text("DELETE FROM roles WHERE name NOT IN ('admin', 'business_owner', 'associate')"))
    op.execute(sa.text("""
        INSERT INTO roles(name, description) VALUES
          ('admin', 'Administrator application role'),
          ('business_owner', 'Business Owner application role'),
          ('associate', 'Associate application role')
        ON CONFLICT (name) DO NOTHING
    """))
    if "user_permissions" not in inspect(bind).get_table_names():
        op.create_table(
            "user_permissions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("permission", sa.String(80), nullable=False),
            sa.Column("granted_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("user_id", "permission", name="uq_user_permission"),
        )
    permission_indexes = {i["name"] for i in inspect(bind).get_indexes("user_permissions")}
    if "ix_user_permissions_user_id" not in permission_indexes:
        op.create_index("ix_user_permissions_user_id", "user_permissions", ["user_id"])
    if "ix_user_permissions_permission" not in permission_indexes:
        op.create_index("ix_user_permissions_permission", "user_permissions", ["permission"])


def downgrade() -> None:
    op.drop_table("user_permissions")
    op.drop_constraint("ck_users_supported_role", "users", type_="check")
    op.drop_constraint("ck_businesses_supported_type", "businesses", type_="check")
    op.drop_index("ix_businesses_business_type", table_name="businesses")
    op.drop_constraint("uq_business_local_database_name", "businesses", type_="unique")
    op.drop_column("businesses", "local_database_name")
    op.drop_column("businesses", "master_database_name")
    op.drop_column("businesses", "business_type")
