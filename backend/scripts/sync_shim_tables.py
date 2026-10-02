import psycopg2

CONNECTION_STRING = "postgresql://postgres.ahgkvgbrwtbrmkoendfd:InventoryDatabase123@aws-0-ap-southeast-2.pooler.supabase.com:5432/postgres"

SHIM_SQL = """
-- =============================================
-- Compatibility shim tables and columns
-- These let the reorders_router / receipts_router raw SQL 
-- work alongside the ER-diagram tables that already exist
-- =============================================

-- 1. Create reorder_list table (integer PK, as expected by reorders_router)
CREATE TABLE IF NOT EXISTS reorder_list (
    id SERIAL PRIMARY KEY,
    product_id INT REFERENCES products(id) ON DELETE CASCADE,
    supplier_id UUID,
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

-- 2. Add product_id and purchase_date to purchase_items/purchases for raw SQL compat
ALTER TABLE purchase_items ADD COLUMN IF NOT EXISTS product_id INT;
ALTER TABLE purchases ADD COLUMN IF NOT EXISTS purchase_date DATE;

-- Backfill purchase_date from invoice_date
UPDATE purchases SET purchase_date = invoice_date WHERE purchase_date IS NULL AND invoice_date IS NOT NULL;

-- 3. Add file_hash and duplicate_warning columns to receipt_imports if not yet present
ALTER TABLE receipt_imports ADD COLUMN IF NOT EXISTS file_hash VARCHAR(64);
ALTER TABLE receipt_imports ADD COLUMN IF NOT EXISTS duplicate_warning BOOLEAN DEFAULT FALSE;

-- 4. Add inventory_batches.product_id if not yet UUID-compatible
-- (batch table uses ib.product_id in joins — verify it exists)
ALTER TABLE inventory_batches ADD COLUMN IF NOT EXISTS product_id INT;
ALTER TABLE inventory_batches ADD COLUMN IF NOT EXISTS lot_number VARCHAR(100);
ALTER TABLE inventory_batches ADD COLUMN IF NOT EXISTS serial_number VARCHAR(100);
ALTER TABLE inventory_batches ADD COLUMN IF NOT EXISTS cost_price NUMERIC(12,2) DEFAULT 0;
ALTER TABLE inventory_batches ADD COLUMN IF NOT EXISTS quantity NUMERIC(14,2) DEFAULT 0;
ALTER TABLE inventory_batches ADD COLUMN IF NOT EXISTS manufacturing_date DATE;
ALTER TABLE inventory_batches ADD COLUMN IF NOT EXISTS expiry_date DATE;
ALTER TABLE inventory_batches ADD COLUMN IF NOT EXISTS status VARCHAR(30) DEFAULT 'active';
"""

def main():
    conn = psycopg2.connect(CONNECTION_STRING)
    cur = conn.cursor()
    print("Applying compatibility shim tables/columns...")
    cur.execute(SHIM_SQL)
    conn.commit()
    print("Done! Verifying...")
    
    # Verify reorder_list exists
    cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'reorder_list' AND table_schema = 'public'")
    print(f"  reorder_list table exists: {cur.fetchone()[0] > 0}")
    
    # Verify purchase_items.product_id exists
    cur.execute("SELECT COUNT(*) FROM information_schema.columns WHERE table_name = 'purchase_items' AND column_name = 'product_id'")
    print(f"  purchase_items.product_id exists: {cur.fetchone()[0] > 0}")

    # Verify purchases.purchase_date exists
    cur.execute("SELECT COUNT(*) FROM information_schema.columns WHERE table_name = 'purchases' AND column_name = 'purchase_date'")
    print(f"  purchases.purchase_date exists: {cur.fetchone()[0] > 0}")
    
    # Total table count
    cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public'")
    print(f"  Total tables in public schema: {cur.fetchone()[0]}")

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
