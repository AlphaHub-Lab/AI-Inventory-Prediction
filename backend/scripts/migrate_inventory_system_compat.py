import psycopg2

DB_URL = "postgresql://postgres:InventoryDatabase123@db.ahgkvgbrwtbrmkoendfd.supabase.co:5432/inventory_system"

MIGRATION_SQL = """
-- 1. Add compatibility columns to users
ALTER TABLE users ADD COLUMN IF NOT EXISTS full_name VARCHAR(120);
UPDATE users SET full_name = name WHERE full_name IS NULL;

ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(40);
UPDATE users u SET role = r.name FROM roles r WHERE u.role_id = r.id AND u.role IS NULL;

-- 2. Add compatibility columns to businesses
ALTER TABLE businesses ADD COLUMN IF NOT EXISTS business_type VARCHAR(50);
UPDATE businesses b SET business_type = bt.code FROM business_types bt WHERE b.business_type_id = bt.id AND b.business_type IS NULL;

ALTER TABLE businesses ADD COLUMN IF NOT EXISTS owner_email VARCHAR(255);
UPDATE businesses b SET owner_email = u.email FROM users u WHERE b.owner_id = u.id AND b.owner_email IS NULL;

ALTER TABLE businesses ADD COLUMN IF NOT EXISTS master_database_name VARCHAR(63);
UPDATE businesses SET master_database_name = 'master_' || business_type WHERE master_database_name IS NULL;

ALTER TABLE businesses ADD COLUMN IF NOT EXISTS local_database_name VARCHAR(63);
UPDATE businesses SET local_database_name = 'inventory_system' WHERE local_database_name IS NULL;

-- 3. Create auth_sessions compatibility table in inventory_system
CREATE TABLE IF NOT EXISTS auth_sessions (
    id VARCHAR(64) PRIMARY KEY,
    user_id UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    revoked_at TIMESTAMP WITH TIME ZONE
);

-- 4. Create compatibility view or table for categories & products
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
    supplier_id INTEGER,
    expiry_date DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Seed matching products from business_products
INSERT INTO products (sku, name, price, current_stock, reorder_point, unit, status)
SELECT bp.sku, bp.name, bp.selling_price, COALESCE(SUM(ib.available_quantity), 85), bp.reorder_level, 'unit', 'active'
FROM business_products bp
LEFT JOIN inventory_batches ib ON bp.id = ib.business_product_id
WHERE NOT EXISTS (SELECT 1 FROM products p WHERE p.sku = bp.sku)
GROUP BY bp.sku, bp.name, bp.selling_price, bp.reorder_level;
"""

def run():
    print(f"Applying compatibility bridge to inventory_system...")
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(MIGRATION_SQL)
    print("Compatibility bridge successfully applied!")
    cur.close()
    conn.close()

if __name__ == "__main__":
    run()
