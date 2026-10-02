import psycopg2

CONNECTION_STRING = "postgresql://postgres.ahgkvgbrwtbrmkoendfd:InventoryDatabase123@aws-0-ap-southeast-2.pooler.supabase.com:5432/postgres"

def main():
    conn = psycopg2.connect(CONNECTION_STRING)
    cur = conn.cursor()
    
    print("Checking purchases columns...")
    cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'purchases' AND table_schema = 'public'")
    for c in cur.fetchall():
        print(f"  {c[0]} ({c[1]})")

    print("\nApplying compatibility migrations for inventory_transactions, purchases, and purchase_items...")
    cur.execute("""
    -- 1. inventory_transactions
    ALTER TABLE inventory_transactions ADD COLUMN IF NOT EXISTS timestamp TIMESTAMPTZ DEFAULT NOW();
    UPDATE inventory_transactions SET timestamp = created_at WHERE timestamp IS NULL AND created_at IS NOT NULL;
    
    -- Relax reference_id and performed_by to VARCHAR(150) so both UUIDs and strings (e.g. email, invoice code) work
    DO $$
    BEGIN
        ALTER TABLE inventory_transactions ALTER COLUMN reference_id TYPE VARCHAR(150) USING reference_id::text;
    EXCEPTION WHEN OTHERS THEN NULL;
    END $$;

    DO $$
    BEGIN
        ALTER TABLE inventory_transactions ALTER COLUMN performed_by TYPE VARCHAR(150) USING performed_by::text;
    EXCEPTION WHEN OTHERS THEN NULL;
    END $$;

    -- 2. purchases
    ALTER TABLE purchases ADD COLUMN IF NOT EXISTS purchase_date DATE;
    ALTER TABLE purchases ADD COLUMN IF NOT EXISTS total_amount NUMERIC(14,2) DEFAULT 0;
    ALTER TABLE purchases ADD COLUMN IF NOT EXISTS subtotal NUMERIC(14,2) DEFAULT 0;
    ALTER TABLE purchases ADD COLUMN IF NOT EXISTS tax_amount NUMERIC(14,2) DEFAULT 0;
    ALTER TABLE purchases ADD COLUMN IF NOT EXISTS payment_status VARCHAR(50) DEFAULT 'unpaid';
    ALTER TABLE purchases ADD COLUMN IF NOT EXISTS notes TEXT;
    UPDATE purchases SET purchase_date = invoice_date WHERE purchase_date IS NULL AND invoice_date IS NOT NULL;

    -- 3. purchase_items
    ALTER TABLE purchase_items ADD COLUMN IF NOT EXISTS purchase_id UUID;
    ALTER TABLE purchase_items ADD COLUMN IF NOT EXISTS product_name VARCHAR(255);
    ALTER TABLE purchase_items ADD COLUMN IF NOT EXISTS unit VARCHAR(50);
    ALTER TABLE purchase_items ADD COLUMN IF NOT EXISTS mrp NUMERIC(12,2);
    ALTER TABLE purchase_items ADD COLUMN IF NOT EXISTS line_total NUMERIC(14,2) DEFAULT 0;
    ALTER TABLE purchase_items ADD COLUMN IF NOT EXISTS batch_number VARCHAR(100);
    ALTER TABLE purchase_items ADD COLUMN IF NOT EXISTS expiry_date DATE;

    -- 4. inventory_batches Lot/Expiry/Batch compatibility
    ALTER TABLE inventory_batches ADD COLUMN IF NOT EXISTS product_id INT;
    ALTER TABLE inventory_batches ADD COLUMN IF NOT EXISTS lot_number VARCHAR(100);
    ALTER TABLE inventory_batches ADD COLUMN IF NOT EXISTS serial_number VARCHAR(100);
    ALTER TABLE inventory_batches ADD COLUMN IF NOT EXISTS batch_number VARCHAR(100);
    ALTER TABLE inventory_batches ADD COLUMN IF NOT EXISTS cost_price NUMERIC(12,2) DEFAULT 0;
    ALTER TABLE inventory_batches ADD COLUMN IF NOT EXISTS quantity NUMERIC(14,2) DEFAULT 0;
    ALTER TABLE inventory_batches ADD COLUMN IF NOT EXISTS manufacturing_date DATE;
    ALTER TABLE inventory_batches ADD COLUMN IF NOT EXISTS expiry_date DATE;
    ALTER TABLE inventory_batches ADD COLUMN IF NOT EXISTS status VARCHAR(30) DEFAULT 'active';
    """)
    conn.commit()
    print("All compatibility columns and type relaxations applied successfully!")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
