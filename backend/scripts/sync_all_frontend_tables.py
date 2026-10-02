import psycopg2
from psycopg2.extras import RealDictCursor

CONNECTION_STRING = "postgresql://postgres.ahgkvgbrwtbrmkoendfd:InventoryDatabase123@aws-0-ap-southeast-2.pooler.supabase.com:5432/postgres"

SYNC_SQL = """
-- 1. Extend products table with all attributes used by frontend & models
ALTER TABLE products ADD COLUMN IF NOT EXISTS manufacturing_date DATE;
ALTER TABLE products ADD COLUMN IF NOT EXISTS expiry_date DATE;
ALTER TABLE products ADD COLUMN IF NOT EXISTS is_weight_based BOOLEAN DEFAULT FALSE;
ALTER TABLE products ADD COLUMN IF NOT EXISTS weight_unit VARCHAR(10) DEFAULT 'kg';
ALTER TABLE products ADD COLUMN IF NOT EXISTS default_weight_g INTEGER DEFAULT 1000;
ALTER TABLE products ADD COLUMN IF NOT EXISTS weight_increment_g INTEGER DEFAULT 500;
ALTER TABLE products ADD COLUMN IF NOT EXISTS minimum_weight_g INTEGER DEFAULT 100;
ALTER TABLE products ADD COLUMN IF NOT EXISTS maximum_weight_g INTEGER DEFAULT 100000;
ALTER TABLE products ADD COLUMN IF NOT EXISTS weight_stock_g NUMERIC(12,2) DEFAULT 0;
ALTER TABLE products ADD COLUMN IF NOT EXISTS size VARCHAR(50);
ALTER TABLE products ADD COLUMN IF NOT EXISTS color VARCHAR(50);
ALTER TABLE products ADD COLUMN IF NOT EXISTS style VARCHAR(100);
ALTER TABLE products ADD COLUMN IF NOT EXISTS variant_name VARCHAR(150);
ALTER TABLE products ADD COLUMN IF NOT EXISTS target_stock NUMERIC(14,2) DEFAULT 0;
ALTER TABLE products ADD COLUMN IF NOT EXISTS custom_attributes JSONB DEFAULT '{}'::jsonb;
ALTER TABLE products ADD COLUMN IF NOT EXISTS parent_product_id INT;

-- 2. Extend categories table
ALTER TABLE categories ADD COLUMN IF NOT EXISTS default_weight_g INTEGER DEFAULT 1000;
ALTER TABLE categories ADD COLUMN IF NOT EXISTS weight_increment_g INTEGER DEFAULT 500;
ALTER TABLE categories ADD COLUMN IF NOT EXISTS minimum_weight_g INTEGER DEFAULT 100;
ALTER TABLE categories ADD COLUMN IF NOT EXISTS maximum_weight_g INTEGER DEFAULT 100000;

-- 3. Extend suppliers table
ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS lead_time_days INTEGER DEFAULT 3;
ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS minimum_order_quantity INTEGER DEFAULT 1;
ALTER TABLE suppliers ADD COLUMN IF NOT EXISTS reliability_score FLOAT DEFAULT 0.9;

-- 4. Extend inventory_batches
ALTER TABLE inventory_batches ADD COLUMN IF NOT EXISTS product_id INT;
ALTER TABLE inventory_batches ADD COLUMN IF NOT EXISTS lot_number VARCHAR(80);
ALTER TABLE inventory_batches ADD COLUMN IF NOT EXISTS received_date DATE DEFAULT CURRENT_DATE;
ALTER TABLE inventory_batches ADD COLUMN IF NOT EXISTS business_id UUID;

-- 5. Extend inventory_transactions
ALTER TABLE inventory_transactions ADD COLUMN IF NOT EXISTS product_id INT;
ALTER TABLE inventory_transactions ADD COLUMN IF NOT EXISTS quantity_delta INTEGER DEFAULT 0;
ALTER TABLE inventory_transactions ADD COLUMN IF NOT EXISTS weight_delta_g INTEGER;
ALTER TABLE inventory_transactions ADD COLUMN IF NOT EXISTS note VARCHAR(500) DEFAULT '';
ALTER TABLE inventory_transactions ADD COLUMN IF NOT EXISTS user_id UUID;

-- 6. Extend sales
ALTER TABLE sales ADD COLUMN IF NOT EXISTS date DATE DEFAULT CURRENT_DATE;
ALTER TABLE sales ADD COLUMN IF NOT EXISTS product_id INT;
ALTER TABLE sales ADD COLUMN IF NOT EXISTS quantity_sold INTEGER DEFAULT 1;
ALTER TABLE sales ADD COLUMN IF NOT EXISTS unit_price NUMERIC(12,2) DEFAULT 0.00;
ALTER TABLE sales ADD COLUMN IF NOT EXISTS discount NUMERIC(12,2) DEFAULT 0.00;
ALTER TABLE sales ADD COLUMN IF NOT EXISTS promotion BOOLEAN DEFAULT FALSE;
ALTER TABLE sales ADD COLUMN IF NOT EXISTS holiday BOOLEAN DEFAULT FALSE;
ALTER TABLE sales ADD COLUMN IF NOT EXISTS channel VARCHAR(40) DEFAULT 'store';
ALTER TABLE sales ADD COLUMN IF NOT EXISTS location VARCHAR(100) DEFAULT 'Main Store';
ALTER TABLE sales ADD COLUMN IF NOT EXISTS revenue NUMERIC(12,2) DEFAULT 0.00;

-- 7. Extend purchase_orders and items
ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS expected_delivery DATE;
ALTER TABLE purchase_order_items ADD COLUMN IF NOT EXISTS product_id INT;

-- 8. Extend audit_logs
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS entity VARCHAR(100);
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS entity_id VARCHAR(100);
ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS payload JSONB DEFAULT '{}'::jsonb;

-- 9. Create user_permissions
CREATE TABLE IF NOT EXISTS user_permissions (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL,
    permission VARCHAR(80) NOT NULL,
    granted_by UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_user_permission UNIQUE (user_id, permission)
);

-- 10. Create checkout_transactions and checkout_items
CREATE TABLE IF NOT EXISTS checkout_transactions (
    id SERIAL PRIMARY KEY,
    business_id UUID,
    invoice_id VARCHAR(40) UNIQUE,
    customer_name VARCHAR(180) DEFAULT 'Walk-in Customer',
    customer_phone VARCHAR(40),
    customer_id VARCHAR(80),
    subtotal NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    discount NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    tax NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    total NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    payment_method VARCHAR(20) NOT NULL DEFAULT 'CASH',
    payment_status VARCHAR(20) DEFAULT 'PAID',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS checkout_items (
    id SERIAL PRIMARY KEY,
    business_id UUID,
    transaction_id INTEGER REFERENCES checkout_transactions(id) ON DELETE CASCADE,
    product_id INTEGER,
    product_name VARCHAR(180) NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    unit_price NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    line_total NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    selected_weight_g INTEGER,
    weight_unit VARCHAR(2)
);

-- 11. Create forecasts
CREATE TABLE IF NOT EXISTS forecasts (
    id SERIAL PRIMARY KEY,
    business_id UUID,
    product_id INTEGER,
    forecast_date DATE NOT NULL,
    predicted_quantity FLOAT NOT NULL DEFAULT 0,
    model_name VARCHAR(80) NOT NULL DEFAULT 'baseline-v1',
    model_version VARCHAR(40) DEFAULT 'v1',
    horizon_days INTEGER NOT NULL DEFAULT 14,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 12. Create waste_predictions
CREATE TABLE IF NOT EXISTS waste_predictions (
    id SERIAL PRIMARY KEY,
    business_id UUID,
    product_id INTEGER,
    risk_level VARCHAR(20) NOT NULL DEFAULT 'LOW',
    units_at_risk INTEGER NOT NULL DEFAULT 0,
    estimated_value NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    recommendation VARCHAR(500) NOT NULL DEFAULT 'Normal rotation',
    calculated_for DATE DEFAULT CURRENT_DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 13. Create expiry_alerts
CREATE TABLE IF NOT EXISTS expiry_alerts (
    id SERIAL PRIMARY KEY,
    business_id UUID,
    product_id INTEGER,
    severity VARCHAR(20) NOT NULL DEFAULT 'medium',
    status VARCHAR(20) DEFAULT 'open',
    expiry_date DATE NOT NULL,
    recommendation VARCHAR(400) NOT NULL DEFAULT 'Inspect batch',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 14. Create reorder_recommendations
CREATE TABLE IF NOT EXISTS reorder_recommendations (
    id SERIAL PRIMARY KEY,
    business_id UUID,
    product_id INTEGER,
    forecast_demand INTEGER NOT NULL DEFAULT 10,
    recommended_quantity INTEGER NOT NULL DEFAULT 20,
    explanation VARCHAR(600) NOT NULL DEFAULT 'Calculated replenishment',
    status VARCHAR(20) DEFAULT 'draft',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 15. Create knowledge_documents and knowledge_chunks
CREATE TABLE IF NOT EXISTS knowledge_documents (
    id SERIAL PRIMARY KEY,
    business_id UUID,
    title VARCHAR(180) NOT NULL,
    body TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id SERIAL PRIMARY KEY,
    business_id UUID,
    document_id INTEGER REFERENCES knowledge_documents(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    metadata_json JSONB DEFAULT '{}'::jsonb
);

-- 16. Create chatbot_conversations and chatbot_messages
CREATE TABLE IF NOT EXISTS chatbot_conversations (
    id SERIAL PRIMARY KEY,
    business_id UUID,
    user_id UUID,
    title VARCHAR(150) DEFAULT 'New conversation',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chatbot_messages (
    id SERIAL PRIMARY KEY,
    business_id UUID,
    conversation_id INTEGER REFERENCES chatbot_conversations(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    intent VARCHAR(50),
    citations JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 17. Create model_runs
CREATE TABLE IF NOT EXISTS model_runs (
    id SERIAL PRIMARY KEY,
    business_id UUID,
    model_name VARCHAR(100) NOT NULL,
    version VARCHAR(50) NOT NULL,
    train_start DATE,
    train_end DATE,
    mae FLOAT NOT NULL DEFAULT 0.05,
    rmse FLOAT NOT NULL DEFAULT 0.08,
    mape FLOAT NOT NULL DEFAULT 0.04,
    r2 FLOAT NOT NULL DEFAULT 0.92,
    horizon_days INTEGER NOT NULL DEFAULT 14,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
"""

def sync():
    conn = psycopg2.connect(CONNECTION_STRING)
    conn.autocommit = True
    cur = conn.cursor(cursor_factory=RealDictCursor)
    print("Executing SYNC DDL for frontend tables...")
    cur.execute(SYNC_SQL)
    print("DDL executed successfully!")

    # Check businesses
    cur.execute("SELECT id, name FROM businesses LIMIT 1")
    biz = cur.fetchone()
    biz_id = biz["id"] if biz else None

    # Check categories
    cur.execute("SELECT id FROM categories LIMIT 1")
    cat = cur.fetchone()
    if not cat:
        cur.execute("""
            INSERT INTO categories (name, business_id, is_grocery, default_weight_unit)
            VALUES ('General Healthcare', %s, FALSE, 'unit'),
                   ('Daily Grocery', %s, TRUE, 'kg')
            RETURNING id
        """, (biz_id, biz_id))
        cat_id = cur.fetchone()["id"]
    else:
        cat_id = cat["id"]

    # Check products
    cur.execute("SELECT id FROM products LIMIT 1")
    prod = cur.fetchone()
    if not prod:
        cur.execute("""
            INSERT INTO products (
                business_id, sku, name, price, current_stock, reorder_point,
                minimum_stock, maximum_stock, safety_stock, lead_time_days,
                unit, status, category_id, manufacturing_date, expiry_date
            )
            VALUES (
                %s, 'MED-BAND-001', 'Adhesive Bandage Strips (Pack of 10)', 45.00,
                100, 20, 10, 500, 15, 3, 'pack', 'active', %s,
                CURRENT_DATE - INTERVAL '30 days', CURRENT_DATE + INTERVAL '700 days'
            ),
            (
                %s, 'GROC-RICE-001', 'Organic Basmati Rice 5kg', 450.00,
                50, 15, 5, 200, 10, 2, 'kg', 'active', %s,
                CURRENT_DATE - INTERVAL '10 days', CURRENT_DATE + INTERVAL '365 days'
            )
            RETURNING id
        """, (biz_id, cat_id, biz_id, cat_id))
        prod_id = cur.fetchone()["id"]
    else:
        prod_id = prod["id"]

    # Seed a sample forecast if empty
    cur.execute("SELECT id FROM forecasts LIMIT 1")
    if not cur.fetchone():
        cur.execute("""
            INSERT INTO forecasts (business_id, product_id, forecast_date, predicted_quantity, model_name, horizon_days)
            VALUES (%s, %s, CURRENT_DATE + INTERVAL '7 days', 25.5, 'LightGBM-v2', 7),
                   (%s, %s, CURRENT_DATE + INTERVAL '14 days', 52.0, 'LightGBM-v2', 14)
        """, (biz_id, prod_id, biz_id, prod_id))

    # Seed a sample waste prediction if empty
    cur.execute("SELECT id FROM waste_predictions LIMIT 1")
    if not cur.fetchone():
        cur.execute("""
            INSERT INTO waste_predictions (business_id, product_id, risk_level, units_at_risk, estimated_value, recommendation)
            VALUES (%s, %s, 'LOW', 2, 90.00, 'Stock is fresh. Standard rotation applies.')
        """, (biz_id, prod_id))

    # Seed a sample model run if empty
    cur.execute("SELECT id FROM model_runs LIMIT 1")
    if not cur.fetchone():
        cur.execute("""
            INSERT INTO model_runs (business_id, model_name, version, mae, rmse, mape, r2, horizon_days)
            VALUES (%s, 'LightGBM Demand Forecaster', 'v2.1', 0.042, 0.068, 0.035, 0.945, 14)
        """, (biz_id,))

    # Seed a sample knowledge document if empty
    cur.execute("SELECT id FROM knowledge_documents LIMIT 1")
    if not cur.fetchone():
        cur.execute("""
            INSERT INTO knowledge_documents (business_id, title, body)
            VALUES (%s, 'Standard Operating Procedure: Stock Receiving & Quarantine',
                    'When stock arrives from wholesalers, verify physical delivery against purchase order items before receiving into batches.')
            RETURNING id
        """, (biz_id,))
        doc_id = cur.fetchone()["id"]
        cur.execute("""
            INSERT INTO knowledge_chunks (business_id, document_id, content)
            VALUES (%s, %s, 'Verify physical delivery against purchase order items before receiving into batches.')
        """, (biz_id, doc_id))

    # Seed sample sales if empty
    cur.execute("SELECT id FROM sales LIMIT 1")
    if not cur.fetchone():
        cur.execute("""
            INSERT INTO sales (business_id, date, product_id, quantity_sold, unit_price, total_amount, revenue, payment_status)
            VALUES (%s, CURRENT_DATE - INTERVAL '1 day', %s, 5, 45.00, 225.00, 225.00, 'paid'),
                   (%s, CURRENT_DATE, %s, 3, 45.00, 135.00, 135.00, 'paid')
        """, (biz_id, prod_id, biz_id, prod_id))

    conn.close()
    print("Database sync and seed completed successfully!")

if __name__ == "__main__":
    sync()
