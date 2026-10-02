import psycopg2

CONNECTION_STRING = "postgresql://postgres.ahgkvgbrwtbrmkoendfd:InventoryDatabase123@aws-0-ap-southeast-2.pooler.supabase.com:5432/postgres"

MIGRATION_SQL = """
-- 1. Compatibility columns for products (add only what's missing)
ALTER TABLE products ADD COLUMN IF NOT EXISTS barcode VARCHAR(100);
ALTER TABLE products ADD COLUMN IF NOT EXISTS product_name VARCHAR(255);
ALTER TABLE products ADD COLUMN IF NOT EXISTS brand VARCHAR(150);
ALTER TABLE products ADD COLUMN IF NOT EXISTS category VARCHAR(150);
ALTER TABLE products ADD COLUMN IF NOT EXISTS subcategory VARCHAR(150);
ALTER TABLE products ADD COLUMN IF NOT EXISTS reorder_level NUMERIC(14,2) DEFAULT 10;
ALTER TABLE products ADD COLUMN IF NOT EXISTS purchase_price NUMERIC(12,2) DEFAULT 0;
ALTER TABLE products ADD COLUMN IF NOT EXISTS selling_price NUMERIC(12,2) DEFAULT 0;
ALTER TABLE products ADD COLUMN IF NOT EXISTS mrp NUMERIC(12,2);
ALTER TABLE products ADD COLUMN IF NOT EXISTS pack_size VARCHAR(100);
ALTER TABLE products ADD COLUMN IF NOT EXISTS gst_percentage NUMERIC(5,2) DEFAULT 0;
ALTER TABLE products ADD COLUMN IF NOT EXISTS generic_name VARCHAR(255);
ALTER TABLE products ADD COLUMN IF NOT EXISTS dosage_form VARCHAR(100);
ALTER TABLE products ADD COLUMN IF NOT EXISTS strength VARCHAR(100);
ALTER TABLE products ADD COLUMN IF NOT EXISTS manufacturer VARCHAR(200);
ALTER TABLE products ADD COLUMN IF NOT EXISTS prescription_required BOOLEAN DEFAULT FALSE;
ALTER TABLE products ADD COLUMN IF NOT EXISTS storage_condition VARCHAR(200);
ALTER TABLE products ADD COLUMN IF NOT EXISTS expiry_required BOOLEAN DEFAULT FALSE;
ALTER TABLE products ADD COLUMN IF NOT EXISTS storage_temperature VARCHAR(100);
ALTER TABLE products ADD COLUMN IF NOT EXISTS shelf_life VARCHAR(100);

-- Populate products.product_name from name, reorder_level from reorder_point
UPDATE products SET product_name = name WHERE product_name IS NULL AND name IS NOT NULL;
UPDATE products SET reorder_level = reorder_point WHERE reorder_level IS NULL AND reorder_point IS NOT NULL;
UPDATE products SET purchase_price = price WHERE (purchase_price IS NULL OR purchase_price = 0) AND price IS NOT NULL AND price > 0;
UPDATE products SET selling_price = price WHERE (selling_price IS NULL OR selling_price = 0) AND price IS NOT NULL AND price > 0;

-- 2. Compatibility columns for receipt_imports (many are missing)
ALTER TABLE receipt_imports ADD COLUMN IF NOT EXISTS uploaded_by VARCHAR(150);
ALTER TABLE receipt_imports ADD COLUMN IF NOT EXISTS supplier_name_extracted VARCHAR(255);
ALTER TABLE receipt_imports ADD COLUMN IF NOT EXISTS invoice_number VARCHAR(100);
ALTER TABLE receipt_imports ADD COLUMN IF NOT EXISTS invoice_date DATE;
ALTER TABLE receipt_imports ADD COLUMN IF NOT EXISTS processing_status VARCHAR(50) DEFAULT 'review_required';
ALTER TABLE receipt_imports ADD COLUMN IF NOT EXISTS subtotal NUMERIC(14,2) DEFAULT 0;
ALTER TABLE receipt_imports ADD COLUMN IF NOT EXISTS gst_amount NUMERIC(14,2) DEFAULT 0;
ALTER TABLE receipt_imports ADD COLUMN IF NOT EXISTS ai_confidence FLOAT DEFAULT 0.0;
ALTER TABLE receipt_imports ADD COLUMN IF NOT EXISTS confirmed_at TIMESTAMPTZ;
ALTER TABLE receipt_imports ADD COLUMN IF NOT EXISTS confirmed_by VARCHAR(150);
ALTER TABLE receipt_imports ADD COLUMN IF NOT EXISTS file_path VARCHAR(500);
ALTER TABLE receipt_imports ADD COLUMN IF NOT EXISTS raw_extraction_json JSONB DEFAULT '{}'::jsonb;

-- 3. Compatibility columns for receipt_import_items
ALTER TABLE receipt_import_items ADD COLUMN IF NOT EXISTS match_source VARCHAR(50) DEFAULT 'local';
ALTER TABLE receipt_import_items ADD COLUMN IF NOT EXISTS unit VARCHAR(50);
ALTER TABLE receipt_import_items ADD COLUMN IF NOT EXISTS barcode VARCHAR(100);
ALTER TABLE receipt_import_items ADD COLUMN IF NOT EXISTS serial_number VARCHAR(100);
ALTER TABLE receipt_import_items ADD COLUMN IF NOT EXISTS size VARCHAR(50);
ALTER TABLE receipt_import_items ADD COLUMN IF NOT EXISTS color VARCHAR(50);
ALTER TABLE receipt_import_items ADD COLUMN IF NOT EXISTS variant_name VARCHAR(150);
ALTER TABLE receipt_import_items ADD COLUMN IF NOT EXISTS custom_attributes JSONB DEFAULT '{}'::jsonb;
ALTER TABLE receipt_import_items ADD COLUMN IF NOT EXISTS error_message TEXT;
ALTER TABLE receipt_import_items ADD COLUMN IF NOT EXISTS gst_percentage NUMERIC(5,2) DEFAULT 0;
ALTER TABLE receipt_import_items ADD COLUMN IF NOT EXISTS confidence_level VARCHAR(30) DEFAULT 'UNKNOWN';
ALTER TABLE receipt_import_items ADD COLUMN IF NOT EXISTS review_status VARCHAR(50) DEFAULT 'pending';
ALTER TABLE receipt_import_items ADD COLUMN IF NOT EXISTS edited_by VARCHAR(150);
ALTER TABLE receipt_import_items ADD COLUMN IF NOT EXISTS matched_product_id INT;

-- 4. Reorder compatibility: add reason/target_stock/notes to reorder_items
ALTER TABLE reorder_items ADD COLUMN IF NOT EXISTS reason TEXT DEFAULT 'low_stock';
ALTER TABLE reorder_items ADD COLUMN IF NOT EXISTS target_stock NUMERIC(14,2) DEFAULT 0;
ALTER TABLE reorder_items ADD COLUMN IF NOT EXISTS received_quantity NUMERIC(14,2) DEFAULT 0;
ALTER TABLE reorder_items ADD COLUMN IF NOT EXISTS notes TEXT;
ALTER TABLE reorder_items ADD COLUMN IF NOT EXISTS average_order_quantity NUMERIC(14,2) DEFAULT 0;
ALTER TABLE reorder_items ADD COLUMN IF NOT EXISTS source VARCHAR(50) DEFAULT 'low_stock';
"""

def main():
    conn = psycopg2.connect(CONNECTION_STRING)
    cur = conn.cursor()
    print("Applying compatibility columns to Supabase PostgreSQL database...")
    cur.execute(MIGRATION_SQL)
    conn.commit()
    print("All compatibility columns applied successfully!")

    # Verify
    for tbl in ['products', 'receipt_imports', 'receipt_import_items', 'reorder_items']:
        cur.execute(
            "SELECT COUNT(*) FROM information_schema.columns WHERE table_name = %s AND table_schema = 'public'",
            (tbl,)
        )
        count = cur.fetchone()[0]
        print(f"  {tbl}: {count} columns")

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
