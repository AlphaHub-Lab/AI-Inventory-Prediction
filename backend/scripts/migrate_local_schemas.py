from app.database_manager import get_engine_for_db
from sqlalchemy import text

LOCAL_DBS = ["local_business_1", "local_business_3", "local_business_4"]

DDL_STATEMENTS = [
    # products table
    "ALTER TABLE products ADD COLUMN IF NOT EXISTS size VARCHAR(50);",
    "ALTER TABLE products ADD COLUMN IF NOT EXISTS color VARCHAR(50);",
    "ALTER TABLE products ADD COLUMN IF NOT EXISTS style VARCHAR(100);",
    "ALTER TABLE products ADD COLUMN IF NOT EXISTS variant_name VARCHAR(150);",
    "ALTER TABLE products ADD COLUMN IF NOT EXISTS target_stock NUMERIC(14,2) DEFAULT 0;",
    "ALTER TABLE products ADD COLUMN IF NOT EXISTS custom_attributes JSONB DEFAULT '{}'::jsonb;",
    "ALTER TABLE products ADD COLUMN IF NOT EXISTS parent_product_id INT REFERENCES products(id) ON DELETE SET NULL;",
    
    # reorder_list table
    "ALTER TABLE reorder_list ADD COLUMN IF NOT EXISTS reason TEXT;",
    "ALTER TABLE reorder_list ADD COLUMN IF NOT EXISTS received_quantity NUMERIC(14,2) DEFAULT 0;",
    "ALTER TABLE reorder_list ADD COLUMN IF NOT EXISTS target_stock NUMERIC(14,2) DEFAULT 0;",
    "ALTER TABLE reorder_list ADD COLUMN IF NOT EXISTS notes TEXT;",
    
    # inventory_batches
    "ALTER TABLE inventory_batches ADD COLUMN IF NOT EXISTS serial_number VARCHAR(100);",
    
    # receipt_imports
    "ALTER TABLE receipt_imports ADD COLUMN IF NOT EXISTS file_hash VARCHAR(64);",
    "ALTER TABLE receipt_imports ADD COLUMN IF NOT EXISTS duplicate_warning BOOLEAN DEFAULT FALSE;",
    
    # receipt_import_items
    "ALTER TABLE receipt_import_items ADD COLUMN IF NOT EXISTS barcode VARCHAR(100);",
    "ALTER TABLE receipt_import_items ADD COLUMN IF NOT EXISTS serial_number VARCHAR(100);",
    "ALTER TABLE receipt_import_items ADD COLUMN IF NOT EXISTS size VARCHAR(50);",
    "ALTER TABLE receipt_import_items ADD COLUMN IF NOT EXISTS color VARCHAR(50);",
    "ALTER TABLE receipt_import_items ADD COLUMN IF NOT EXISTS variant_name VARCHAR(150);",
    "ALTER TABLE receipt_import_items ADD COLUMN IF NOT EXISTS custom_attributes JSONB DEFAULT '{}'::jsonb;",
    "ALTER TABLE receipt_import_items ADD COLUMN IF NOT EXISTS error_message TEXT;"
]

def migrate():
    for dbname in LOCAL_DBS:
        print(f"Migrating schema for {dbname}...")
        try:
            engine = get_engine_for_db(dbname)
            with engine.connect() as conn:
                for stmt in DDL_STATEMENTS:
                    conn.execute(text(stmt))
                conn.commit()
            print(f"  [OK] {dbname} updated successfully.")
        except Exception as e:
            print(f"  [FAIL] Failed for {dbname}: {e}")

if __name__ == "__main__":
    migrate()
