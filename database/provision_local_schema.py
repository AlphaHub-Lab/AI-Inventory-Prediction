import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

LOCAL_DB_SCHEMA_SQL = """
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
    master_product_id INT,
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
    quantity NUMERIC(14,2) NOT NULL DEFAULT 0,
    cost_price NUMERIC(12,2) DEFAULT 0,
    manufacturing_date DATE,
    expiry_date DATE,
    status VARCHAR(30) DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_batches_product_id ON inventory_batches(product_id);
CREATE INDEX IF NOT EXISTS ix_batches_expiry_date ON inventory_batches(expiry_date);

-- 7. Inventory Transactions (Auditable movements)
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
    master_product_id INT,
    quantity NUMERIC(14,2) NOT NULL DEFAULT 1,
    unit VARCHAR(50),
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

def provision_local_db(dbname):
    base_url = 'postgresql://postgres:InventoryDatabase123@db.ahgkvgbrwtbrmkoendfd.supabase.co:5432/'
    conn = psycopg2.connect(base_url + dbname)
    cur = conn.cursor()
    cur.execute(LOCAL_DB_SCHEMA_SQL)
    conn.commit()
    print(f"Provisioned schema for {dbname}")
    
    # Check tables
    cur.execute("""
        SELECT table_name FROM information_schema.tables 
        WHERE table_schema = 'public' ORDER BY table_name;
    """)
    tables = [t[0] for t in cur.fetchall()]
    print(f"Tables in {dbname} ({len(tables)}): {tables}")
    cur.close()
    conn.close()

if __name__ == '__main__':
    provision_local_db('local_business_1')
