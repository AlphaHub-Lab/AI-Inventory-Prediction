import sys
from pathlib import Path
from datetime import date, datetime, timedelta
import uuid
import psycopg2
from psycopg2.extras import RealDictCursor

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.security import hash_password

# Use pooler connection provided by user, with fallback to direct
CONNECTION_STRINGS = [
    "postgresql://postgres.ahgkvgbrwtbrmkoendfd:InventoryDatabase123@aws-0-ap-southeast-2.pooler.supabase.com:5432/postgres",
    "postgresql://postgres:InventoryDatabase123@db.ahgkvgbrwtbrmkoendfd.supabase.co:5432/postgres"
]

def get_connection():
    for cs in CONNECTION_STRINGS:
        try:
            conn = psycopg2.connect(cs)
            conn.autocommit = True
            print(f"Connected to: {cs.split('@')[-1]}")
            return conn
        except Exception as e:
            print(f"Failed to connect to {cs.split('@')[-1]}: {e}")
    raise RuntimeError("Could not connect to any postgres connection string")

# 1. Full 38-table DDL Schema from the ER Diagram
SCHEMA_SQL = """
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ========================================================
-- MODULE 1: AUTHENTICATION & AUTHORIZATION
-- ========================================================
CREATE TABLE IF NOT EXISTS roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    module VARCHAR(50) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS role_permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    role_id UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permission_id UUID NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_role_permission UNIQUE (role_id, permission_id)
);

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID,
    role_id UUID REFERENCES roles(id) ON DELETE RESTRICT,
    name VARCHAR(100) NOT NULL,
    full_name VARCHAR(120),
    role VARCHAR(40),
    email VARCHAR(100) NOT NULL UNIQUE,
    username VARCHAR(100) UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    phone VARCHAR(20),
    is_active BOOLEAN DEFAULT TRUE,
    created_by UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token VARCHAR(255) NOT NULL,
    ip_address VARCHAR(50),
    user_agent TEXT,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ========================================================
-- MODULE 2: BUSINESSES & CONFIGURATION
-- ========================================================
CREATE TABLE IF NOT EXISTS business_types (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    is_predefined BOOLEAN DEFAULT TRUE,
    has_master_catalog BOOLEAN DEFAULT TRUE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS businesses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_type_id UUID REFERENCES business_types(id) ON DELETE RESTRICT,
    business_type VARCHAR(50),
    name VARCHAR(100) NOT NULL,
    address TEXT,
    phone VARCHAR(20),
    email VARCHAR(100),
    owner_email VARCHAR(255),
    gstin VARCHAR(30),
    owner_id UUID REFERENCES users(id) ON DELETE SET NULL,
    is_active BOOLEAN DEFAULT TRUE,
    settings JSONB DEFAULT '{}'::jsonb,
    master_database_name VARCHAR(63) DEFAULT 'postgres',
    local_database_name VARCHAR(63) DEFAULT 'postgres',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE users DROP CONSTRAINT IF EXISTS fk_users_business;
ALTER TABLE users ADD CONSTRAINT fk_users_business FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE SET NULL;

CREATE TABLE IF NOT EXISTS business_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    key VARCHAR(100) NOT NULL,
    value JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_business_settings_key UNIQUE (business_id, key)
);

-- ========================================================
-- MODULE 3: MASTER PRODUCT CATALOG
-- ========================================================
CREATE TABLE IF NOT EXISTS master_categories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_type_id UUID REFERENCES business_types(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    parent_id UUID REFERENCES master_categories(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS master_subcategories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category_id UUID NOT NULL REFERENCES master_categories(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS master_brands (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_type_id UUID REFERENCES business_types(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS master_manufacturers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_type_id UUID REFERENCES business_types(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    contact_person VARCHAR(100),
    phone VARCHAR(20),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS master_suppliers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_type_id UUID REFERENCES business_types(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    contact_person VARCHAR(100),
    phone VARCHAR(20),
    email VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS master_units (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(50) NOT NULL UNIQUE,
    symbol VARCHAR(20) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS master_allergens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS master_products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_type_id UUID REFERENCES business_types(id) ON DELETE CASCADE,
    category_id UUID REFERENCES master_categories(id) ON DELETE SET NULL,
    subcategory_id UUID REFERENCES master_subcategories(id) ON DELETE SET NULL,
    brand_id UUID REFERENCES master_brands(id) ON DELETE SET NULL,
    manufacturer_id UUID REFERENCES master_manufacturers(id) ON DELETE SET NULL,
    sku VARCHAR(100) NOT NULL UNIQUE,
    barcode VARCHAR(100),
    name VARCHAR(255) NOT NULL,
    generic_name VARCHAR(255),
    description TEXT,
    unit_id UUID REFERENCES master_units(id) ON DELETE SET NULL,
    pack_size VARCHAR(50),
    mrp NUMERIC(12,2) DEFAULT 0.00,
    gst_percentage NUMERIC(5,2) DEFAULT 0.00,
    prescription_required BOOLEAN DEFAULT FALSE,
    storage_condition TEXT,
    shelf_life_days INTEGER,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ========================================================
-- MODULE 4: BUSINESS PRODUCTS (STORE-SPECIFIC)
-- ========================================================
CREATE TABLE IF NOT EXISTS business_products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    master_product_id UUID REFERENCES master_products(id) ON DELETE SET NULL,
    sku VARCHAR(100) NOT NULL,
    barcode VARCHAR(100),
    name VARCHAR(255) NOT NULL,
    selling_price NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    reorder_level INTEGER DEFAULT 10,
    default_supplier_id UUID,
    is_active BOOLEAN DEFAULT TRUE,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_business_product_sku UNIQUE (business_id, sku)
);

CREATE TABLE IF NOT EXISTS product_suppliers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_product_id UUID NOT NULL REFERENCES business_products(id) ON DELETE CASCADE,
    supplier_id UUID NOT NULL,
    is_default BOOLEAN DEFAULT FALSE,
    lead_time_days INTEGER DEFAULT 3,
    last_purchase_price NUMERIC(12,2) DEFAULT 0.00,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ========================================================
-- MODULE 5: SUPPLIERS & CUSTOMERS
-- ========================================================
CREATE TABLE IF NOT EXISTS suppliers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    contact_person VARCHAR(100),
    phone VARCHAR(20),
    email VARCHAR(100),
    address TEXT,
    gstin VARCHAR(30),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE product_suppliers DROP CONSTRAINT IF EXISTS fk_product_suppliers_supplier;
ALTER TABLE product_suppliers ADD CONSTRAINT fk_product_suppliers_supplier FOREIGN KEY (supplier_id) REFERENCES suppliers(id) ON DELETE CASCADE;

ALTER TABLE business_products DROP CONSTRAINT IF EXISTS fk_business_products_default_supplier;
ALTER TABLE business_products ADD CONSTRAINT fk_business_products_default_supplier FOREIGN KEY (default_supplier_id) REFERENCES suppliers(id) ON DELETE SET NULL;

CREATE TABLE IF NOT EXISTS customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    phone VARCHAR(20),
    email VARCHAR(100),
    address TEXT,
    gstin VARCHAR(30),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ========================================================
-- MODULE 6: INVENTORY MANAGEMENT
-- ========================================================
CREATE TABLE IF NOT EXISTS inventory_batches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_product_id UUID NOT NULL REFERENCES business_products(id) ON DELETE CASCADE,
    batch_number VARCHAR(100) NOT NULL,
    manufacturing_date DATE,
    expiry_date DATE,
    purchase_price NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    mrp NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    quantity NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    available_quantity NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    storage_location VARCHAR(100),
    status VARCHAR(50) DEFAULT 'available',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS inventory_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    business_product_id UUID NOT NULL REFERENCES business_products(id) ON DELETE CASCADE,
    batch_id UUID REFERENCES inventory_batches(id) ON DELETE SET NULL,
    transaction_type VARCHAR(50) NOT NULL,
    quantity NUMERIC(12,2) NOT NULL,
    unit_price NUMERIC(12,2) DEFAULT 0.00,
    reference_type VARCHAR(50),
    reference_id UUID,
    previous_stock NUMERIC(12,2) DEFAULT 0.00,
    new_stock NUMERIC(12,2) DEFAULT 0.00,
    performed_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ========================================================
-- MODULE 7: PURCHASES & PURCHASE ORDERS
-- ========================================================
CREATE TABLE IF NOT EXISTS purchase_orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    supplier_id UUID REFERENCES suppliers(id) ON DELETE SET NULL,
    order_date DATE NOT NULL,
    expected_date DATE,
    status VARCHAR(50) DEFAULT 'draft',
    total_amount NUMERIC(12,2) DEFAULT 0.00,
    notes TEXT,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS purchase_order_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    purchase_order_id UUID NOT NULL REFERENCES purchase_orders(id) ON DELETE CASCADE,
    business_product_id UUID NOT NULL REFERENCES business_products(id) ON DELETE CASCADE,
    quantity NUMERIC(12,2) NOT NULL,
    unit_price NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    gst_percentage NUMERIC(5,2) DEFAULT 0.00,
    total_amount NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS purchases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    supplier_id UUID REFERENCES suppliers(id) ON DELETE SET NULL,
    purchase_order_id UUID REFERENCES purchase_orders(id) ON DELETE SET NULL,
    invoice_number VARCHAR(100),
    invoice_date DATE,
    total_amount NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    gst_amount NUMERIC(12,2) DEFAULT 0.00,
    discount_amount NUMERIC(12,2) DEFAULT 0.00,
    status VARCHAR(50) DEFAULT 'received',
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS purchase_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    purchase_id UUID NOT NULL REFERENCES purchases(id) ON DELETE CASCADE,
    business_product_id UUID NOT NULL REFERENCES business_products(id) ON DELETE CASCADE,
    batch_id UUID REFERENCES inventory_batches(id) ON DELETE SET NULL,
    product_name VARCHAR(255),
    quantity NUMERIC(12,2) NOT NULL,
    unit_price NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    mrp NUMERIC(12,2) DEFAULT 0.00,
    gst_percentage NUMERIC(5,2) DEFAULT 0.00,
    total_amount NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ========================================================
-- MODULE 8: SALES, INVOICES & PAYMENTS
-- ========================================================
CREATE TABLE IF NOT EXISTS sales (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    customer_id UUID REFERENCES customers(id) ON DELETE SET NULL,
    invoice_number VARCHAR(100) UNIQUE,
    sale_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    predicted_demand NUMERIC(12,2),
    total_amount NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    payment_status VARCHAR(50) DEFAULT 'paid',
    payment_method VARCHAR(50) DEFAULT 'cash',
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sale_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sale_id UUID NOT NULL REFERENCES sales(id) ON DELETE CASCADE,
    business_product_id UUID NOT NULL REFERENCES business_products(id) ON DELETE CASCADE,
    batch_id UUID REFERENCES inventory_batches(id) ON DELETE SET NULL,
    quantity NUMERIC(12,2) NOT NULL,
    unit_price NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    gst_percentage NUMERIC(5,2) DEFAULT 0.00,
    total_amount NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS invoices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sale_id UUID REFERENCES sales(id) ON DELETE SET NULL,
    invoice_number VARCHAR(100) NOT NULL UNIQUE,
    invoice_date DATE NOT NULL,
    total_amount NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    gst_amount NUMERIC(12,2) DEFAULT 0.00,
    status VARCHAR(50) DEFAULT 'issued',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ai_waste_predictions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    business_product_id UUID REFERENCES business_products(id) ON DELETE SET NULL,
    batch_id UUID REFERENCES inventory_batches(id) ON DELETE SET NULL,
    risk_level VARCHAR(50) NOT NULL,
    risk_reason TEXT,
    suggested_action TEXT,
    confidence_score NUMERIC(5,2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ai_recommendations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    business_product_id UUID REFERENCES business_products(id) ON DELETE SET NULL,
    recommendation_type VARCHAR(50) NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    confidence_score NUMERIC(5,2),
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ========================================================
-- MODULE 9: REORDER LIST
-- ========================================================
CREATE TABLE IF NOT EXISTS reorder_lists (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    name VARCHAR(100),
    status VARCHAR(50) DEFAULT 'pending',
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS reorder_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    reorder_list_id UUID NOT NULL REFERENCES reorder_lists(id) ON DELETE CASCADE,
    business_product_id UUID NOT NULL REFERENCES business_products(id) ON DELETE CASCADE,
    supplier_id UUID REFERENCES suppliers(id) ON DELETE SET NULL,
    current_stock NUMERIC(12,2) DEFAULT 0.00,
    reorder_level INTEGER DEFAULT 10,
    last_order_quantity NUMERIC(12,2) DEFAULT 0.00,
    last_order_date DATE,
    suggested_quantity NUMERIC(12,2) NOT NULL,
    selected_quantity NUMERIC(12,2) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ========================================================
-- MODULE 10: RECEIPT PROCESSING (AI)
-- ========================================================
CREATE TABLE IF NOT EXISTS receipt_imports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    supplier_id UUID REFERENCES suppliers(id) ON DELETE SET NULL,
    file_name VARCHAR(255) NOT NULL,
    status VARCHAR(50) DEFAULT 'processing',
    total_amount NUMERIC(12,2),
    file_hash VARCHAR(64),
    duplicate_warning BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS receipt_import_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    receipt_import_id UUID NOT NULL REFERENCES receipt_imports(id) ON DELETE CASCADE,
    master_product_id UUID REFERENCES master_products(id) ON DELETE SET NULL,
    business_product_id UUID REFERENCES business_products(id) ON DELETE SET NULL,
    raw_product_name VARCHAR(255) NOT NULL,
    matched_product_name VARCHAR(255),
    purchase_price NUMERIC(12,2) DEFAULT 0.00,
    mrp NUMERIC(12,2) DEFAULT 0.00,
    batch_number VARCHAR(100),
    manufacturing_date DATE,
    expiry_date DATE,
    confidence_score NUMERIC(5,2),
    status VARCHAR(50) DEFAULT 'matched',
    quantity NUMERIC(12,2) DEFAULT 1.00,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ========================================================
-- MODULE 12: AUDIT LOGS & SYSTEM
-- ========================================================
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID REFERENCES businesses(id) ON DELETE SET NULL,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(50) NOT NULL,
    resource VARCHAR(100),
    resource_id UUID,
    metadata JSONB DEFAULT '{}'::jsonb,
    ip_address VARCHAR(50),
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS system_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key VARCHAR(100) NOT NULL UNIQUE,
    value JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    business_id UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    file_name VARCHAR(255) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    file_type VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Compatibility bridging table for auth_sessions and legacy views
CREATE TABLE IF NOT EXISTS auth_sessions (
    id VARCHAR(64) PRIMARY KEY,
    user_id UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    revoked_at TIMESTAMP WITH TIME ZONE
);

CREATE TABLE IF NOT EXISTS categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    business_id UUID,
    is_grocery BOOLEAN DEFAULT FALSE,
    default_weight_unit VARCHAR(10) DEFAULT 'kg',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    business_id UUID,
    sku VARCHAR(100),
    name VARCHAR(255),
    price NUMERIC(12,2) DEFAULT 0.00,
    current_stock NUMERIC(12,2) DEFAULT 0.00,
    reorder_point NUMERIC(12,2) DEFAULT 10.00,
    minimum_stock NUMERIC(12,2) DEFAULT 5.00,
    maximum_stock NUMERIC(12,2) DEFAULT 200.00,
    safety_stock NUMERIC(12,2) DEFAULT 5.00,
    lead_time_days INTEGER DEFAULT 3,
    unit VARCHAR(50) DEFAULT 'unit',
    status VARCHAR(50) DEFAULT 'active',
    category_id INTEGER,
    supplier_id UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
"""

def deploy():
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    print("Deploying DDL schema to postgres...")
    cur.execute(SCHEMA_SQL)
    print("DDL schema successfully executed!")

    # Seed data
    print("Seeding roles...")
    roles = [
        ("admin", "System Administrator with full access across platform"),
        ("business_owner", "Business Owner / Store Manager with access to store operations, analytics and AI"),
        ("associate", "Store Associate / Cashier with access to inventory, POS and receipts")
    ]
    role_ids = {}
    for name, desc in roles:
        cur.execute("""
            INSERT INTO roles (name, description)
            VALUES (%s, %s)
            ON CONFLICT (name) DO UPDATE SET description = EXCLUDED.description
            RETURNING id, name
        """, (name, desc))
        row = cur.fetchone()
        role_ids[row["name"]] = row["id"]

    print("Seeding permissions...")
    perms = [
        ("auth.login", "User Login & Session Management", "auth"),
        ("inventory.view", "View Inventory and Stock Levels", "inventory"),
        ("inventory.adjust", "Adjust Stock and Audit Count", "inventory"),
        ("inventory.receive", "Receive Reordered Stock", "inventory"),
        ("reorder.manage", "Manage Reorder Lists and Replenishment", "reorders"),
        ("receipt.upload", "Upload and Ingest Invoices/Receipts", "receipts"),
        ("pos.checkout", "Execute Point of Sale Sales & Invoicing", "sales"),
        ("analytics.view", "View Business Analytics & Reports", "analytics"),
        ("ai.forecast", "View AI Demand Forecasts & Waste Insights", "ai"),
        ("admin.users", "Manage User Accounts & Roles", "admin"),
        ("admin.business", "Configure Business Profile and Store Settings", "admin")
    ]
    perm_ids = []
    for pname, pdesc, pmod in perms:
        cur.execute("""
            INSERT INTO permissions (name, description, module)
            VALUES (%s, %s, %s)
            ON CONFLICT (name) DO UPDATE SET description = EXCLUDED.description, module = EXCLUDED.module
            RETURNING id
        """, (pname, pdesc, pmod))
        perm_ids.append(cur.fetchone()["id"])

    # Link all permissions to admin and owner
    for pid in perm_ids:
        cur.execute("""
            INSERT INTO role_permissions (role_id, permission_id)
            VALUES (%s, %s)
            ON CONFLICT (role_id, permission_id) DO NOTHING
        """, (role_ids["admin"], pid))
        cur.execute("""
            INSERT INTO role_permissions (role_id, permission_id)
            VALUES (%s, %s)
            ON CONFLICT (role_id, permission_id) DO NOTHING
        """, (role_ids["business_owner"], pid))

    # Associate gets basic permissions
    for pname, pdesc, pmod in perms[:7]:
        cur.execute("SELECT id FROM permissions WHERE name = %s", (pname,))
        p_row = cur.fetchone()
        if p_row:
            cur.execute("""
                INSERT INTO role_permissions (role_id, permission_id)
                VALUES (%s, %s)
                ON CONFLICT (role_id, permission_id) DO NOTHING
            """, (role_ids["associate"], p_row["id"]))

    print("Seeding 6 predefined business types...")
    btypes = [
        ("medical", "Medical / Pharmacy", "Retail pharmacy and pharmaceutical healthcare", True, True),
        ("grocery", "Grocery & Supermarket", "Supermarkets, FMCG and daily essentials", True, True),
        ("restaurant", "Restaurant & Food Business", "Dine-in, cafes, cloud kitchens and food outlets", True, True),
        ("stationery", "Stationery & Office Supplies", "Office, school, paper and stationery goods", True, True),
        ("dairy", "Dairy & Fresh Produce", "Milk, dairy products, perishables and cold storage", True, True),
        ("other", "General Retail & Other", "General retail store (no predefined master catalog)", True, False)
    ]
    btype_ids = {}
    for code, bname, bdesc, is_pred, has_mc in btypes:
        cur.execute("""
            INSERT INTO business_types (code, name, description, is_predefined, has_master_catalog)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (code) DO UPDATE SET
                name = EXCLUDED.name,
                description = EXCLUDED.description,
                is_predefined = EXCLUDED.is_predefined,
                has_master_catalog = EXCLUDED.has_master_catalog
            RETURNING id, code
        """, (code, bname, bdesc, is_pred, has_mc))
        row = cur.fetchone()
        btype_ids[row["code"]] = row["id"]

    print("Seeding master units...")
    units = [
        ("Kilogram", "kg"),
        ("Gram", "g"),
        ("Liter", "l"),
        ("Milliliter", "ml"),
        ("Unit", "unit"),
        ("Box", "box"),
        ("Strip", "strip"),
        ("Bottle", "bottle"),
        ("Vial", "vial"),
        ("Pack", "pack"),
        ("Piece", "pc"),
        ("Meter", "m")
    ]
    unit_ids = {}
    for uname, usym in units:
        cur.execute("""
            INSERT INTO master_units (name, symbol)
            VALUES (%s, %s)
            ON CONFLICT (name) DO UPDATE SET symbol = EXCLUDED.symbol
            RETURNING id, name
        """, (uname, usym))
        row = cur.fetchone()
        unit_ids[row["name"]] = row["id"]

    print("Seeding users...")
    admin_hash = hash_password("Admin123!")
    owner_hash = hash_password("Owner123!")

    # 1. Admin Users
    for email, uname in [
        ("admin@inventory.example.com", "System Admin"),
        ("Amogh@gmail.com", "Amogh Admin")
    ]:
        cur.execute("""
            INSERT INTO users (role_id, name, full_name, role, email, username, password_hash, is_active)
            VALUES (%s, %s, %s, 'admin', %s, %s, %s, TRUE)
            ON CONFLICT (email) DO UPDATE SET
                name = EXCLUDED.name,
                full_name = EXCLUDED.full_name,
                role = 'admin',
                role_id = EXCLUDED.role_id,
                password_hash = EXCLUDED.password_hash,
                is_active = TRUE
        """, (role_ids["admin"], uname, uname, email, email.split("@")[0], admin_hash))

    print("Seeding businesses...")
    businesses = [
        ("medical", "Skull Medicals & Healthcare", "124 Hospital Road, Medical City", "+91 98765 43210", "contact@skullmedicals.com", "sarah@skullmedicals.com", "29AAAAA0000A1Z5"),
        ("grocery", "GreenLeaf Supermarket", "45 Market Street, Green Park", "+91 98765 11223", "orders@greenleaf.com", "rajesh@greenleaf.com", "29BBBBB0000B1Z6"),
        ("restaurant", "Gourmet Bistro & Cafe", "78 Food Avenue, Downtown", "+91 98765 22334", "manager@gourmetbistro.com", "bistro@example.com", "29CCCCC0000C1Z7"),
        ("stationery", "Apex Office & Stationery Supplies", "12 Commerce Lane, Central", "+91 98765 33445", "sales@apexstationery.com", "apex@example.com", "29DDDDD0000D1Z8"),
        ("dairy", "Pure Pastures Dairy", "9 Farm Road, Suburban Valley", "+91 98765 44556", "supply@purepastures.com", "dairy@example.com", "29EEEEE0000E1Z9"),
        ("other", "Universal General Traders", "88 Trade Center, West Port", "+91 98765 55667", "info@universaltraders.com", "trader@example.com", "29FFFFF0000F1ZA")
    ]
    biz_ids = {}
    for bcode, bname, baddr, bphone, bemail, bowner_email, bgst in businesses:
        cur.execute("SELECT id, name FROM businesses WHERE name = %s", (bname,))
        existing_b = cur.fetchone()
        if existing_b:
            cur.execute("""
                UPDATE businesses 
                SET business_type_id = %s, business_type = %s, address = %s, phone = %s, email = %s, owner_email = %s, gstin = %s
                WHERE id = %s
            """, (btype_ids[bcode], bcode, baddr, bphone, bemail, bowner_email, bgst, existing_b["id"]))
            biz_ids[bcode] = existing_b["id"]
            b_id = existing_b["id"]
        else:
            cur.execute("""
                INSERT INTO businesses (business_type_id, business_type, name, address, phone, email, owner_email, gstin, is_active, master_database_name, local_database_name)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, TRUE, 'postgres', 'postgres')
                RETURNING id, name
            """, (btype_ids[bcode], bcode, bname, baddr, bphone, bemail, bowner_email, bgst))
            b_row = cur.fetchone()
            biz_ids[bcode] = b_row["id"]
            b_id = b_row["id"]

        # Insert or update owner user
        cur.execute("""
            INSERT INTO users (business_id, role_id, name, full_name, role, email, username, password_hash, is_active)
            VALUES (%s, %s, %s, %s, 'business_owner', %s, %s, %s, TRUE)
            ON CONFLICT (email) DO UPDATE SET
                business_id = EXCLUDED.business_id,
                role_id = EXCLUDED.role_id,
                role = 'business_owner',
                full_name = EXCLUDED.full_name,
                password_hash = EXCLUDED.password_hash,
                is_active = TRUE
            RETURNING id
        """, (b_id, role_ids["business_owner"], bname + " Owner", bname + " Owner", bowner_email, bowner_email.split("@")[0], owner_hash))
        owner_id = cur.fetchone()["id"]
        cur.execute("UPDATE businesses SET owner_id = %s WHERE id = %s", (owner_id, b_id))

    # Seed master categories & products for medical & grocery
    print("Seeding master categories & products...")
    cur.execute("SELECT id FROM master_categories WHERE name = 'First Aid & Bandages' LIMIT 1")
    cat_row = cur.fetchone()
    if cat_row:
        med_cat_id = cat_row["id"]
    else:
        cur.execute("""
            INSERT INTO master_categories (business_type_id, name)
            VALUES (%s, 'First Aid & Bandages')
            RETURNING id
        """, (btype_ids["medical"],))
        med_cat_id = cur.fetchone()["id"]

    cur.execute("SELECT id FROM master_brands WHERE name = 'Band-Aid' LIMIT 1")
    b_row = cur.fetchone()
    if b_row:
        med_brand_id = b_row["id"]
    else:
        cur.execute("""
            INSERT INTO master_brands (business_type_id, name)
            VALUES (%s, 'Band-Aid')
            RETURNING id
        """, (btype_ids["medical"],))
        med_brand_id = cur.fetchone()["id"]

    cur.execute("""
        INSERT INTO master_products (
            business_type_id, category_id, brand_id, sku, barcode, name, generic_name,
            unit_id, pack_size, mrp, gst_percentage, prescription_required, shelf_life_days
        )
        VALUES (
            %s, %s, %s, 'MED-BAND-001', '890103000001', 'Adhesive Bandage Strips',
            'Sterile Plaster Strips', %s, 'Pack of 10', 50.00, 12.00, FALSE, 730
        )
        ON CONFLICT (sku) DO UPDATE SET name = EXCLUDED.name, mrp = EXCLUDED.mrp
        RETURNING id
    """, (btype_ids["medical"], med_cat_id, med_brand_id, unit_ids["Pack"]))
    m_prod_id = cur.fetchone()["id"]

    # Seed store products & suppliers for Skull Medicals
    med_biz_id = biz_ids["medical"]
    cur.execute("""
        INSERT INTO suppliers (business_id, name, contact_person, phone, email, is_active)
        VALUES (%s, 'MedSupply Wholesale Corp', 'Vikas Sharma', '+91 99887 76655', 'sales@medsupply.com', TRUE)
        RETURNING id
    """, (med_biz_id,))
    supp_id = cur.fetchone()["id"]

    cur.execute("""
        INSERT INTO business_products (business_id, master_product_id, sku, barcode, name, selling_price, reorder_level, default_supplier_id)
        VALUES (%s, %s, 'MED-BAND-001', '890103000001', 'Adhesive Bandage Strips (Pack of 10)', 45.00, 20, %s)
        ON CONFLICT (business_id, sku) DO UPDATE SET selling_price = EXCLUDED.selling_price
        RETURNING id
    """, (med_biz_id, m_prod_id, supp_id))
    b_prod_id = cur.fetchone()["id"]

    cur.execute("""
        INSERT INTO inventory_batches (business_product_id, batch_number, manufacturing_date, expiry_date, purchase_price, mrp, quantity, available_quantity)
        VALUES (%s, 'MED-2026-B1', CURRENT_DATE - INTERVAL '30 days', CURRENT_DATE + INTERVAL '700 days', 30.00, 50.00, 100, 100)
        RETURNING id
    """, (b_prod_id,))
    batch_id = cur.fetchone()["id"]

    cur.execute("""
        INSERT INTO inventory_transactions (business_id, business_product_id, batch_id, transaction_type, quantity, unit_price, previous_stock, new_stock)
        VALUES (%s, %s, %s, 'purchase', 100, 30.00, 0, 100)
    """, (med_biz_id, b_prod_id, batch_id))

    cur.execute("""
        INSERT INTO system_settings (key, value)
        VALUES 
            ('platform_version', '{"version": "2.0.0"}'::jsonb),
            ('auto_reorder_enabled', '{"enabled": true}'::jsonb)
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
    """)

    # Verify tables
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        ORDER BY table_name
    """)
    tables = [r["table_name"] for r in cur.fetchall()]
    print(f"\nTotal tables in 'postgres' public schema: {len(tables)}")
    print(f"Tables: {tables}")

    conn.close()

if __name__ == "__main__":
    deploy()
