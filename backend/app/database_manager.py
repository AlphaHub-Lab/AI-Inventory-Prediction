"""
Multi-Tenant Physical PostgreSQL Database Router & Connection Pool Manager
Manages:
- admin_db: Central identities, permissions, sessions, audit, businesses
- master_<business_type>: Global product catalogs for medical, grocery, restaurant, stationery, dairy
- local_business_<id>: Dedicated local database per business for inventory, sales, purchases, batches, reorders, receipts
"""

import os
import re
from typing import Dict, Generator, Optional
from urllib.parse import urlparse, urlunparse
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from .config import get_settings

settings = get_settings()

def get_base_postgres_url() -> str:
    """Extract base connection URL without database name."""
    raw_url = settings.database_url
    # The backend requirements install psycopg v3 (`psycopg[binary]`). Keep
    # all per-database engines on that driver rather than rewriting URLs to
    # psycopg2, which is not installed in this project environment.
    if raw_url.startswith("postgresql://"):
        raw_url = raw_url.replace("postgresql://", "postgresql+psycopg://", 1)
    elif raw_url.startswith("postgresql+psycopg2://"):
        raw_url = raw_url.replace("postgresql+psycopg2://", "postgresql+psycopg://", 1)

    parsed = urlparse(raw_url)
    # Keep query parameters (such as sslmode=require) after removing the DB path.
    return urlunparse(parsed._replace(path=""))


def database_url_for(dbname: str, *, sqlalchemy_driver: bool = True) -> str:
    """Build a database-specific URL while preserving URL query options."""
    scheme = "postgresql+psycopg" if sqlalchemy_driver else "postgresql"
    return urlunparse(urlparse(BASE_URL)._replace(scheme=scheme, path=f"/{dbname}"))

BASE_URL = get_base_postgres_url()
_ENGINES: Dict[str, Engine] = {}
_SESSION_MAKERS: Dict[str, sessionmaker] = {}
_ENSURED_TENANT_SCHEMAS: set = set()

def get_engine_for_db(dbname: str, *, ensure_schema: bool = True) -> Engine:
    """Get or create a pooled SQLAlchemy engine for a specific database."""
    safe_dbname = re.sub(r'[^a-zA-Z0-9_-]', '', dbname)
    if safe_dbname not in _ENGINES:
        db_url = database_url_for(safe_dbname)
        _ENGINES[safe_dbname] = create_engine(
            db_url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=300,
            connect_args={"connect_timeout": 5}
        )
        _SESSION_MAKERS[safe_dbname] = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=_ENGINES[safe_dbname]
        )
    if ensure_schema and safe_dbname.startswith("local_business_") and safe_dbname not in _ENSURED_TENANT_SCHEMAS:
        try:
            with _ENGINES[safe_dbname].connect() as conn:
                conn.execute(text("ALTER TABLE reorder_list ADD COLUMN IF NOT EXISTS reason TEXT;"))
                conn.execute(text("ALTER TABLE reorder_list ADD COLUMN IF NOT EXISTS received_quantity NUMERIC(14,2) DEFAULT 0;"))
                conn.execute(text("ALTER TABLE reorder_list ADD COLUMN IF NOT EXISTS target_stock NUMERIC(14,2) DEFAULT 0;"))
                conn.execute(text("ALTER TABLE reorder_list ADD COLUMN IF NOT EXISTS notes TEXT;"))
                conn.execute(text("ALTER TABLE receipt_import_items ADD COLUMN IF NOT EXISTS barcode VARCHAR(100);"))
                conn.execute(text("ALTER TABLE receipt_import_items ADD COLUMN IF NOT EXISTS serial_number VARCHAR(100);"))
                conn.execute(text("ALTER TABLE receipt_import_items ADD COLUMN IF NOT EXISTS size VARCHAR(50);"))
                conn.execute(text("ALTER TABLE receipt_import_items ADD COLUMN IF NOT EXISTS color VARCHAR(50);"))
                conn.execute(text("ALTER TABLE receipt_import_items ADD COLUMN IF NOT EXISTS variant_name VARCHAR(150);"))
                conn.execute(text("ALTER TABLE receipt_import_items ADD COLUMN IF NOT EXISTS custom_attributes JSONB DEFAULT '{}'::jsonb;"))
                conn.execute(text("ALTER TABLE receipt_import_items ADD COLUMN IF NOT EXISTS error_message TEXT;"))
                conn.execute(text("ALTER TABLE inventory_batches ADD COLUMN IF NOT EXISTS serial_number VARCHAR(100);"))
                conn.execute(text("ALTER TABLE receipt_imports ADD COLUMN IF NOT EXISTS file_hash VARCHAR(64);"))
                conn.execute(text("ALTER TABLE receipt_imports ADD COLUMN IF NOT EXISTS duplicate_warning BOOLEAN DEFAULT FALSE;"))
                conn.execute(text("ALTER TABLE products ADD COLUMN IF NOT EXISTS size VARCHAR(50);"))
                conn.execute(text("ALTER TABLE products ADD COLUMN IF NOT EXISTS color VARCHAR(50);"))
                conn.execute(text("ALTER TABLE products ADD COLUMN IF NOT EXISTS style VARCHAR(100);"))
                conn.execute(text("ALTER TABLE products ADD COLUMN IF NOT EXISTS variant_name VARCHAR(150);"))
                conn.execute(text("ALTER TABLE products ADD COLUMN IF NOT EXISTS target_stock NUMERIC(14,2) DEFAULT 0;"))
                conn.execute(text("ALTER TABLE products ADD COLUMN IF NOT EXISTS custom_attributes JSONB DEFAULT '{}'::jsonb;"))
                conn.execute(text("ALTER TABLE products ADD COLUMN IF NOT EXISTS parent_product_id INT REFERENCES products(id) ON DELETE SET NULL;"))
                conn.commit()
            _ENSURED_TENANT_SCHEMAS.add(safe_dbname)
        except Exception:
            pass
    return _ENGINES[safe_dbname]

def get_session_for_db(dbname: str, *, ensure_schema: bool = True) -> Session:
    """Create a new SQLAlchemy session for a specific database."""
    get_engine_for_db(dbname, ensure_schema=ensure_schema)
    return _SESSION_MAKERS[dbname]()

def get_admin_session() -> Session:
    parsed = urlparse(settings.database_url)
    target = parsed.path.lstrip("/")
    # DATABASE_URL names the central app database in this physical-DB setup.
    # Preserve that name (normally admin_db) unless explicitly overridden.
    dbname = os.getenv("ADMIN_DB_NAME") or target or "admin_db"
    return get_session_for_db(dbname)

def get_master_session(business_type: str) -> Session:
    parsed = urlparse(settings.database_url)
    target = parsed.path.lstrip("/")
    if target in ("inventory_system", "postgres"):
        return get_session_for_db(target)
    safe_type = business_type.lower().strip()
    if safe_type not in ["medical", "grocery", "restaurant", "food", "stationery", "dairy"]:
        safe_type = "grocery"
    elif safe_type == "food":
        safe_type = "restaurant"
    return get_session_for_db(f"master_{safe_type}")

def get_local_session(local_database_name: str, *, ensure_schema: bool = True) -> Session:
    parsed = urlparse(settings.database_url)
    target = parsed.path.lstrip("/")
    if target in ("inventory_system", "postgres"):
        return get_session_for_db(target, ensure_schema=ensure_schema)
    return get_session_for_db(local_database_name, ensure_schema=ensure_schema)

# DDL for newly provisioned local business databases
LOCAL_DB_DDL = """
-- 1. Business Profile
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

-- 2. Categories
CREATE TABLE IF NOT EXISTS categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(150) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Suppliers
CREATE TABLE IF NOT EXISTS suppliers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    contact_person VARCHAR(150),
    email VARCHAR(255),
    phone VARCHAR(50),
    address TEXT,
    gstin VARCHAR(50),
    reliability_score FLOAT DEFAULT 0.95,
    lead_time_days INT DEFAULT 3,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Customers
CREATE TABLE IF NOT EXISTS customers (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    phone VARCHAR(50),
    email VARCHAR(255),
    address TEXT,
    gstin VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. Products / Local Inventory
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    master_product_id VARCHAR(100),
    sku VARCHAR(100) NOT NULL UNIQUE,
    barcode VARCHAR(100),
    product_name VARCHAR(255) NOT NULL,
    brand VARCHAR(150),
    category VARCHAR(150),
    subcategory VARCHAR(150),
    unit VARCHAR(50) DEFAULT 'unit',
    pack_size VARCHAR(100),
    current_stock NUMERIC(14,2) NOT NULL DEFAULT 0,
    reorder_level NUMERIC(14,2) NOT NULL DEFAULT 10,
    minimum_stock NUMERIC(14,2) NOT NULL DEFAULT 5,
    maximum_stock NUMERIC(14,2) NOT NULL DEFAULT 500,
    selling_price NUMERIC(12,2) NOT NULL DEFAULT 0,
    purchase_price NUMERIC(12,2) NOT NULL DEFAULT 0,
    mrp NUMERIC(12,2),
    gst_percentage NUMERIC(5,2) DEFAULT 0,
    supplier_id INT REFERENCES suppliers(id) ON DELETE SET NULL,
    status VARCHAR(30) DEFAULT 'active',
    -- Specific attributes
    generic_name VARCHAR(255),
    dosage_form VARCHAR(100),
    strength VARCHAR(100),
    manufacturer VARCHAR(200),
    prescription_required BOOLEAN DEFAULT FALSE,
    storage_condition VARCHAR(200),
    expiry_required BOOLEAN DEFAULT FALSE,
    storage_temperature VARCHAR(100),
    shelf_life VARCHAR(100),
    size VARCHAR(50),
    color VARCHAR(50),
    style VARCHAR(100),
    variant_name VARCHAR(150),
    target_stock NUMERIC(14,2) DEFAULT 0,
    custom_attributes JSONB DEFAULT '{}'::jsonb,
    parent_product_id INT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_products_sku ON products(sku);
CREATE INDEX IF NOT EXISTS ix_products_barcode ON products(barcode);
CREATE INDEX IF NOT EXISTS ix_products_name ON products(product_name);
CREATE INDEX IF NOT EXISTS ix_products_category ON products(category);

-- 6. Inventory Batches
CREATE TABLE IF NOT EXISTS inventory_batches (
    id SERIAL PRIMARY KEY,
    product_id INT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    lot_number VARCHAR(100) NOT NULL,
    serial_number VARCHAR(100),
    quantity NUMERIC(14,2) NOT NULL DEFAULT 0,
    cost_price NUMERIC(12,2) DEFAULT 0,
    manufacturing_date DATE,
    expiry_date DATE,
    status VARCHAR(30) DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_batches_product_id ON inventory_batches(product_id);
CREATE INDEX IF NOT EXISTS ix_batches_expiry_date ON inventory_batches(expiry_date);

-- 7. Inventory Transactions
CREATE TABLE IF NOT EXISTS inventory_transactions (
    id SERIAL PRIMARY KEY,
    product_id INT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    batch_id INT REFERENCES inventory_batches(id) ON DELETE SET NULL,
    transaction_type VARCHAR(50) NOT NULL,
    quantity NUMERIC(14,2) NOT NULL,
    previous_stock NUMERIC(14,2) NOT NULL,
    new_stock NUMERIC(14,2) NOT NULL,
    reference_id VARCHAR(100),
    performed_by VARCHAR(150),
    note TEXT,
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_inv_tx_product ON inventory_transactions(product_id);
CREATE INDEX IF NOT EXISTS ix_inv_tx_type ON inventory_transactions(transaction_type);
CREATE INDEX IF NOT EXISTS ix_inv_tx_time ON inventory_transactions(timestamp);

-- 8. Purchases & Items
CREATE TABLE IF NOT EXISTS purchases (
    id SERIAL PRIMARY KEY,
    supplier_id INT REFERENCES suppliers(id) ON DELETE SET NULL,
    invoice_number VARCHAR(100),
    purchase_date DATE NOT NULL DEFAULT CURRENT_DATE,
    subtotal NUMERIC(14,2) DEFAULT 0,
    gst_amount NUMERIC(14,2) DEFAULT 0,
    total_amount NUMERIC(14,2) DEFAULT 0,
    payment_status VARCHAR(30) DEFAULT 'PAID',
    source VARCHAR(50) DEFAULT 'manual',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS purchase_items (
    id SERIAL PRIMARY KEY,
    purchase_id INT NOT NULL REFERENCES purchases(id) ON DELETE CASCADE,
    product_id INT REFERENCES products(id) ON DELETE SET NULL,
    product_name VARCHAR(255) NOT NULL,
    quantity NUMERIC(14,2) NOT NULL,
    unit VARCHAR(50),
    unit_price NUMERIC(12,2) NOT NULL,
    mrp NUMERIC(12,2),
    gst_percentage NUMERIC(5,2) DEFAULT 0,
    line_total NUMERIC(14,2) NOT NULL,
    batch_number VARCHAR(100),
    expiry_date DATE
);

-- 9. Sales & Items
CREATE TABLE IF NOT EXISTS sales (
    id SERIAL PRIMARY KEY,
    invoice_id VARCHAR(100) UNIQUE NOT NULL,
    customer_id INT REFERENCES customers(id) ON DELETE SET NULL,
    customer_name VARCHAR(255) DEFAULT 'Walk-in Customer',
    customer_phone VARCHAR(50),
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    subtotal NUMERIC(14,2) NOT NULL DEFAULT 0,
    discount NUMERIC(14,2) DEFAULT 0,
    tax NUMERIC(14,2) DEFAULT 0,
    total NUMERIC(14,2) NOT NULL DEFAULT 0,
    payment_method VARCHAR(50) DEFAULT 'CASH',
    payment_status VARCHAR(50) DEFAULT 'PAID',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sale_items (
    id SERIAL PRIMARY KEY,
    sale_id INT NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
    product_id INT REFERENCES products(id) ON DELETE SET NULL,
    product_name VARCHAR(255) NOT NULL,
    quantity NUMERIC(14,2) NOT NULL,
    unit_price NUMERIC(12,2) NOT NULL,
    line_total NUMERIC(14,2) NOT NULL
);

-- 10. Reorder List
CREATE TABLE IF NOT EXISTS reorder_list (
    id SERIAL PRIMARY KEY,
    product_id INT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    supplier_id INT REFERENCES suppliers(id) ON DELETE SET NULL,
    current_stock NUMERIC(14,2) NOT NULL DEFAULT 0,
    reorder_level NUMERIC(14,2) NOT NULL DEFAULT 0,
    suggested_quantity NUMERIC(14,2) NOT NULL DEFAULT 0,
    selected_quantity NUMERIC(14,2) NOT NULL DEFAULT 0,
    last_order_date DATE,
    last_order_quantity NUMERIC(14,2) DEFAULT 0,
    average_order_quantity NUMERIC(14,2) DEFAULT 0,
    status VARCHAR(50) DEFAULT 'pending',
    source VARCHAR(50) DEFAULT 'low_stock',
    reason TEXT DEFAULT 'low_stock',
    received_quantity NUMERIC(14,2) NOT NULL DEFAULT 0,
    target_stock NUMERIC(14,2) NOT NULL DEFAULT 0,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(product_id)
);

-- 11. Purchase Orders & Items
CREATE TABLE IF NOT EXISTS purchase_orders (
    id SERIAL PRIMARY KEY,
    po_number VARCHAR(100) UNIQUE NOT NULL,
    supplier_id INT REFERENCES suppliers(id) ON DELETE SET NULL,
    status VARCHAR(50) DEFAULT 'draft',
    total_amount NUMERIC(14,2) DEFAULT 0,
    expected_delivery DATE,
    created_by VARCHAR(150),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS purchase_order_items (
    id SERIAL PRIMARY KEY,
    purchase_order_id INT NOT NULL REFERENCES purchase_orders(id) ON DELETE CASCADE,
    product_id INT REFERENCES products(id) ON DELETE SET NULL,
    product_name VARCHAR(255),
    quantity NUMERIC(14,2) NOT NULL,
    unit_price NUMERIC(12,2) NOT NULL,
    line_total NUMERIC(14,2) NOT NULL
);

-- 12. Receipt Imports & Items (AI Ingestion Pipeline)
CREATE TABLE IF NOT EXISTS receipt_imports (
    id SERIAL PRIMARY KEY,
    file_name VARCHAR(255) NOT NULL,
    file_path VARCHAR(500),
    file_hash VARCHAR(64),
    duplicate_warning BOOLEAN DEFAULT FALSE,
    uploaded_by VARCHAR(150),
    supplier_id INT REFERENCES suppliers(id) ON DELETE SET NULL,
    supplier_name_extracted VARCHAR(255),
    invoice_number VARCHAR(100),
    invoice_date DATE,
    processing_status VARCHAR(50) DEFAULT 'review_required',
    subtotal NUMERIC(14,2) DEFAULT 0,
    gst_amount NUMERIC(14,2) DEFAULT 0,
    total_amount NUMERIC(14,2) DEFAULT 0,
    ai_confidence FLOAT DEFAULT 0.0,
    raw_extraction_json JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    confirmed_at TIMESTAMPTZ,
    confirmed_by VARCHAR(150)
);

CREATE TABLE IF NOT EXISTS receipt_import_items (
    id SERIAL PRIMARY KEY,
    receipt_import_id INT NOT NULL REFERENCES receipt_imports(id) ON DELETE CASCADE,
    raw_product_name VARCHAR(255) NOT NULL,
    matched_product_id INT REFERENCES products(id) ON DELETE SET NULL,
    match_source VARCHAR(50) DEFAULT 'local',
    master_product_id VARCHAR(100),
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
    confidence_score FLOAT DEFAULT 0.0,
    confidence_level VARCHAR(30) DEFAULT 'UNKNOWN',
    review_status VARCHAR(50) DEFAULT 'pending',
    edited_by VARCHAR(150)
);

-- 13. Audit Logs (Local)
CREATE TABLE IF NOT EXISTS audit_logs (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(150),
    action VARCHAR(100) NOT NULL,
    resource VARCHAR(100) NOT NULL,
    resource_id VARCHAR(100),
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    ip_address VARCHAR(50),
    metadata JSONB DEFAULT '{}'::jsonb
);

-- 14. Forecasts and Waste Predictions
CREATE TABLE IF NOT EXISTS forecasts (
    id SERIAL PRIMARY KEY,
    product_id INT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    forecast_date DATE NOT NULL,
    predicted_quantity FLOAT NOT NULL,
    model_name VARCHAR(100) DEFAULT 'xgboost-timeseries',
    model_version VARCHAR(50) DEFAULT 'v1',
    horizon_days INT DEFAULT 7,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(product_id, forecast_date, model_name)
);

CREATE TABLE IF NOT EXISTS waste_predictions (
    id SERIAL PRIMARY KEY,
    product_id INT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    risk_level VARCHAR(20) NOT NULL,
    units_at_risk INT NOT NULL,
    estimated_value NUMERIC(12,2) NOT NULL,
    recommendation TEXT,
    calculated_for DATE DEFAULT CURRENT_DATE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
"""

def provision_new_business_database(
    business_id: int,
    business_type: str,
    business_name: str,
    owner_email: str
) -> str:
    """
    Creates a new physical PostgreSQL database local_business_<business_id> on Supabase cluster,
    executes full schema provisioning, seeds default supplier and profile, and returns the dbname.
    """
    import psycopg

    local_dbname = f"local_business_{business_id}"
    parsed = urlparse(settings.database_url)
    target = parsed.path.lstrip("/")
    if target in ("inventory_system", "postgres"):
        # In unified database architectures (e.g. Supabase postgres), all local tables exist directly
        return local_dbname

    # 1. Connect to postgres database to execute CREATE DATABASE
    with psycopg.connect(database_url_for("postgres", sqlalchemy_driver=False), autocommit=True) as conn:
        if not conn.execute("SELECT 1 FROM pg_database WHERE datname = %s;", (local_dbname,)).fetchone():
            conn.execute(f'CREATE DATABASE "{local_dbname}";')

    # 2. Connect to the newly created local database and apply full DDL
    with psycopg.connect(database_url_for(local_dbname, sqlalchemy_driver=False), autocommit=True) as local_conn:
        local_conn.execute(LOCAL_DB_DDL)

        # 3. Insert Business Profile & Default Supplier
        local_conn.execute("""
            INSERT INTO business_profile (name, business_type, owner_email)
            VALUES (%s, %s, %s)
            ON CONFLICT DO NOTHING;
        """, (business_name, business_type, owner_email))

        local_conn.execute("""
            INSERT INTO suppliers (name, contact_person, email, phone)
            VALUES ('Primary Supplier', 'Accounts Department', %s, '+91 9000000000')
            ON CONFLICT (name) DO NOTHING;
        """, (owner_email,))

        local_conn.execute("""
            INSERT INTO customers (name, phone, email)
            VALUES ('Walk-in Customer', '9999999999', 'walkin@store.local')
            ON CONFLICT DO NOTHING;
        """)

    return local_dbname
