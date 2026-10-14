"""
Automated Database Schema Migration & Compatibility Layer.
Ensures that all tables, columns, indexes, and initial reference data exist.
Executed automatically on application startup so serverless deployments (Vercel, Supabase, Neon)
never experience missing column or missing table runtime errors.
"""

import logging
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from .db import Base
import app.models  # noqa: F401 - register model metadata
from .security import hash_password

logger = logging.getLogger("schema_migration")

# PostgreSQL idempotent column additions
PG_COLUMN_UPDATES = [
    # businesses
    "ALTER TABLE businesses ADD COLUMN IF NOT EXISTS owner_phone VARCHAR(40);",
    "ALTER TABLE businesses ADD COLUMN IF NOT EXISTS owner_personal_email VARCHAR(255);",
    "ALTER TABLE businesses ADD COLUMN IF NOT EXISTS phone VARCHAR(40);",
    "ALTER TABLE businesses ADD COLUMN IF NOT EXISTS address TEXT;",
    "ALTER TABLE businesses ADD COLUMN IF NOT EXISTS business_type VARCHAR(30) DEFAULT 'grocery';",
    "ALTER TABLE businesses ADD COLUMN IF NOT EXISTS master_database_name VARCHAR(63) DEFAULT 'master_grocery';",
    "ALTER TABLE businesses ADD COLUMN IF NOT EXISTS local_database_name VARCHAR(63);",
    "ALTER TABLE businesses ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;",

    # checkout_transactions
    "ALTER TABLE checkout_transactions ADD COLUMN IF NOT EXISTS customer_prescribed_by VARCHAR(180);",
    "ALTER TABLE checkout_transactions ADD COLUMN IF NOT EXISTS customer_address TEXT;",
    "ALTER TABLE checkout_transactions ADD COLUMN IF NOT EXISTS business_id INTEGER;",

    # checkout_items
    "ALTER TABLE checkout_items ADD COLUMN IF NOT EXISTS product_sku VARCHAR(50) DEFAULT '';",
    "ALTER TABLE checkout_items ADD COLUMN IF NOT EXISTS business_id INTEGER;",
    "ALTER TABLE checkout_items ADD COLUMN IF NOT EXISTS selected_weight_g INTEGER;",
    "ALTER TABLE checkout_items ADD COLUMN IF NOT EXISTS weight_unit VARCHAR(2);",

    # products
    "ALTER TABLE products ADD COLUMN IF NOT EXISTS is_weight_based BOOLEAN DEFAULT FALSE;",
    "ALTER TABLE products ADD COLUMN IF NOT EXISTS weight_unit VARCHAR(2);",
    "ALTER TABLE products ADD COLUMN IF NOT EXISTS default_weight_g INTEGER;",
    "ALTER TABLE products ADD COLUMN IF NOT EXISTS weight_increment_g INTEGER;",
    "ALTER TABLE products ADD COLUMN IF NOT EXISTS minimum_weight_g INTEGER;",
    "ALTER TABLE products ADD COLUMN IF NOT EXISTS maximum_weight_g INTEGER;",
    "ALTER TABLE products ADD COLUMN IF NOT EXISTS weight_stock_g INTEGER;",
    "ALTER TABLE products ADD COLUMN IF NOT EXISTS business_id INTEGER;",

    # categories
    "ALTER TABLE categories ADD COLUMN IF NOT EXISTS is_grocery BOOLEAN DEFAULT FALSE;",
    "ALTER TABLE categories ADD COLUMN IF NOT EXISTS default_weight_unit VARCHAR(2) DEFAULT 'kg';",
    "ALTER TABLE categories ADD COLUMN IF NOT EXISTS default_weight_g INTEGER DEFAULT 1000;",
    "ALTER TABLE categories ADD COLUMN IF NOT EXISTS weight_increment_g INTEGER DEFAULT 500;",
    "ALTER TABLE categories ADD COLUMN IF NOT EXISTS minimum_weight_g INTEGER DEFAULT 100;",
    "ALTER TABLE categories ADD COLUMN IF NOT EXISTS maximum_weight_g INTEGER DEFAULT 100000;",
    "ALTER TABLE categories ADD COLUMN IF NOT EXISTS business_id INTEGER;",

    # suppliers & scoped tables
    "ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS business_id INTEGER;",
    "ALTER TABLE inventory_batches ADD COLUMN IF NOT EXISTS business_id INTEGER;",
    "ALTER TABLE inventory_batches ADD COLUMN IF NOT EXISTS serial_number VARCHAR(100);",
    "ALTER TABLE inventory_transactions ADD COLUMN IF NOT EXISTS business_id INTEGER;",
    "ALTER TABLE sales ADD COLUMN IF NOT EXISTS business_id INTEGER;",
    "ALTER TABLE forecasts ADD COLUMN IF NOT EXISTS business_id INTEGER;",
    "ALTER TABLE waste_predictions ADD COLUMN IF NOT EXISTS business_id INTEGER;",
    "ALTER TABLE expiry_alerts ADD COLUMN IF NOT EXISTS business_id INTEGER;",
    "ALTER TABLE reorder_recommendations ADD COLUMN IF NOT EXISTS business_id INTEGER;",
    "ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS business_id INTEGER;",
    "ALTER TABLE purchase_order_items ADD COLUMN IF NOT EXISTS business_id INTEGER;",
    "ALTER TABLE knowledge_documents ADD COLUMN IF NOT EXISTS business_id INTEGER;",
    "ALTER TABLE knowledge_chunks ADD COLUMN IF NOT EXISTS business_id INTEGER;",
    "ALTER TABLE chatbot_conversations ADD COLUMN IF NOT EXISTS business_id INTEGER;",
    "ALTER TABLE chatbot_messages ADD COLUMN IF NOT EXISTS business_id INTEGER;",
    "ALTER TABLE model_runs ADD COLUMN IF NOT EXISTS business_id INTEGER;",
    "ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS business_id INTEGER;",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS business_id INTEGER;",
]

LOCAL_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS business_profile (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    business_type VARCHAR(50) NOT NULL,
    owner_email VARCHAR(255) NOT NULL,
    address TEXT,
    phone VARCHAR(50),
    gstin VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS customers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    phone VARCHAR(50),
    email VARCHAR(255),
    address TEXT,
    gstin VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS reorder_list (
    id SERIAL PRIMARY KEY,
    product_id INT,
    supplier_id INT,
    suggested_quantity NUMERIC(14,2) DEFAULT 0,
    selected_quantity NUMERIC(14,2) DEFAULT 0,
    received_quantity NUMERIC(14,2) DEFAULT 0,
    target_stock NUMERIC(14,2) DEFAULT 0,
    status VARCHAR(30) DEFAULT 'pending',
    source VARCHAR(30) DEFAULT 'low_stock',
    reason TEXT,
    notes TEXT,
    last_order_date DATE,
    last_order_quantity NUMERIC(14,2),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS receipt_imports (
    id SERIAL PRIMARY KEY,
    file_name VARCHAR(255),
    file_type VARCHAR(50),
    file_hash VARCHAR(64),
    duplicate_warning BOOLEAN DEFAULT FALSE,
    invoice_number VARCHAR(100),
    invoice_date DATE,
    supplier_name VARCHAR(255),
    supplier_gstin VARCHAR(50),
    subtotal NUMERIC(12,2) DEFAULT 0,
    tax_amount NUMERIC(12,2) DEFAULT 0,
    total_amount NUMERIC(12,2) DEFAULT 0,
    status VARCHAR(50) DEFAULT 'uploaded',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS receipt_import_items (
    id SERIAL PRIMARY KEY,
    receipt_import_id INT,
    raw_product_name VARCHAR(255) NOT NULL,
    matched_product_id INT,
    match_source VARCHAR(50) DEFAULT 'local',
    quantity NUMERIC(14,2) NOT NULL DEFAULT 1,
    unit VARCHAR(50),
    barcode VARCHAR(100),
    serial_number VARCHAR(100),
    size VARCHAR(50),
    color VARCHAR(50),
    variant_name VARCHAR(150),
    custom_attributes JSONB DEFAULT '{}'::jsonb,
    error_message TEXT,
    mrp NUMERIC(12,2),
    purchase_price NUMERIC(12,2) NOT NULL DEFAULT 0,
    gst_percentage NUMERIC(5,2) DEFAULT 0,
    batch_number VARCHAR(100),
    manufacturing_date DATE,
    expiry_date DATE,
    review_status VARCHAR(50) DEFAULT 'pending'
);
"""


def ensure_schema_compatibility(engine: Engine) -> None:
    """
    Idempotent schema verification and repair. Runs safely on any PostgreSQL or SQLite database.
    """
    try:
        # 1. Create all missing tables registered in SQLAlchemy models
        Base.metadata.create_all(bind=engine)
    except Exception as exc:
        logger.warning("Metadata create_all non-fatal warning: %s", exc)

    dialect_name = engine.dialect.name.lower()

    with engine.connect() as conn:
        # 2. Add missing columns for PostgreSQL
        if dialect_name == "postgresql":
            for stmt in PG_COLUMN_UPDATES:
                try:
                    conn.execute(text(stmt))
                except Exception:
                    pass

            # Create local tables if not existing
            try:
                conn.execute(text(LOCAL_TABLES_SQL))
            except Exception:
                pass

            # Ensure reorder_list columns
            reorder_cols = [
                "ALTER TABLE reorder_list ADD COLUMN IF NOT EXISTS reason TEXT;",
                "ALTER TABLE reorder_list ADD COLUMN IF NOT EXISTS received_quantity NUMERIC(14,2) DEFAULT 0;",
                "ALTER TABLE reorder_list ADD COLUMN IF NOT EXISTS target_stock NUMERIC(14,2) DEFAULT 0;",
                "ALTER TABLE reorder_list ADD COLUMN IF NOT EXISTS notes TEXT;",
            ]
            for stmt in reorder_cols:
                try:
                    conn.execute(text(stmt))
                except Exception:
                    pass

        elif dialect_name == "sqlite":
            # For SQLite, check and add missing columns dynamically
            inspector = inspect(engine)
            existing_tables = set(inspector.get_table_names())
            
            sqlite_columns = {
                "businesses": [
                    ("owner_phone", "VARCHAR(40)"),
                    ("owner_personal_email", "VARCHAR(255)"),
                    ("phone", "VARCHAR(40)"),
                    ("address", "TEXT"),
                    ("business_type", "VARCHAR(30) DEFAULT 'grocery'"),
                    ("master_database_name", "VARCHAR(63) DEFAULT 'master_grocery'"),
                    ("local_database_name", "VARCHAR(63)"),
                ],
                "checkout_transactions": [
                    ("customer_prescribed_by", "VARCHAR(180)"),
                    ("customer_address", "TEXT"),
                ],
                "checkout_items": [
                    ("product_sku", "VARCHAR(50) DEFAULT ''"),
                ],
            }

            for tbl, cols in sqlite_columns.items():
                if tbl in existing_tables:
                    existing_cols = {c["name"] for c in inspector.get_columns(tbl)}
                    for col_name, col_type in cols:
                        if col_name not in existing_cols:
                            try:
                                conn.execute(text(f"ALTER TABLE {tbl} ADD COLUMN {col_name} {col_type}"))
                            except Exception:
                                pass

        # 3. Ensure core application roles exist
        try:
            for role_name in ["admin", "business_owner", "associate"]:
                if dialect_name == "postgresql":
                    conn.execute(text("""
                        INSERT INTO roles (name, description)
                        VALUES (:name, :desc)
                        ON CONFLICT (name) DO NOTHING;
                    """), {"name": role_name, "desc": f"{role_name.replace('_', ' ').title()} application role"})
                else:
                    if not conn.execute(text("SELECT 1 FROM roles WHERE name = :name"), {"name": role_name}).fetchone():
                        conn.execute(text("INSERT INTO roles (name, description) VALUES (:name, :desc)"),
                                     {"name": role_name, "desc": f"{role_name.replace('_', ' ').title()} role"})
        except Exception as exc:
            logger.warning("Roles seeding warning: %s", exc)

        # 4. Ensure at least one active Super Administrator user exists
        try:
            admin_exists = conn.execute(text("SELECT 1 FROM users WHERE role = 'admin' LIMIT 1")).fetchone()
            if not admin_exists:
                admin_pw = hash_password("Admin123!")
                if dialect_name == "postgresql":
                    conn.execute(text("""
                        INSERT INTO users (email, full_name, password_hash, role, is_active)
                        VALUES ('admin@inventory.example.com', 'System Administrator', :pw, 'admin', TRUE)
                        ON CONFLICT (email) DO NOTHING;
                    """), {"pw": admin_pw})
                else:
                    conn.execute(text("""
                        INSERT OR IGNORE INTO users (email, full_name, password_hash, role, is_active)
                        VALUES ('admin@inventory.example.com', 'System Administrator', :pw, 'admin', 1)
                    """), {"pw": admin_pw})
        except Exception as exc:
            logger.warning("Admin user seed warning: %s", exc)

        # 5. Ensure database_registry entries exist
        try:
            reg_names = [
                ("admin_db", "admin", None),
                ("master_medical", "master", "medical"),
                ("master_grocery", "master", "grocery"),
                ("master_restaurant", "master", "restaurant"),
                ("master_stationery", "master", "stationery"),
                ("master_dairy", "master", "dairy"),
            ]
            for dbname, dbtype, btype in reg_names:
                if dialect_name == "postgresql":
                    conn.execute(text("""
                        INSERT INTO database_registry (database_name, database_type, business_type, status)
                        VALUES (:dbname, :dbtype, :btype, 'active')
                        ON CONFLICT (database_name) DO NOTHING;
                    """), {"dbname": dbname, "dbtype": dbtype, "btype": btype})
        except Exception:
            pass

        # 6. Stamp alembic_version to head if alembic table exists
        try:
            if dialect_name == "postgresql":
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS alembic_version (
                        version_num VARCHAR(32) NOT NULL PRIMARY KEY
                    );
                """))
                current_rev = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).scalar()
                if not current_rev:
                    conn.execute(text("INSERT INTO alembic_version (version_num) VALUES ('0008_checkout_business_details');"))
                else:
                    conn.execute(text("UPDATE alembic_version SET version_num = '0008_checkout_business_details';"))
        except Exception:
            pass

        conn.commit()
