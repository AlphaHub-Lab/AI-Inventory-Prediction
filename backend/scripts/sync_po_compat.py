import psycopg2

CONNECTION_STRING = "postgresql://postgres.ahgkvgbrwtbrmkoendfd:InventoryDatabase123@aws-0-ap-southeast-2.pooler.supabase.com:5432/postgres"

def main():
    conn = psycopg2.connect(CONNECTION_STRING)
    cur = conn.cursor()
    
    print("Checking current columns...")
    for tbl in ['purchase_orders', 'purchase_order_items']:
        cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = %s AND table_schema = 'public'", (tbl,))
        cols = cur.fetchall()
        print(f"\n{tbl} columns:")
        for c in cols:
            print(f"  {c[0]} ({c[1]})")

    print("\nAdding missing compatibility columns to purchase_orders and purchase_order_items...")
    cur.execute("""
    -- purchase_orders
    ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS po_number VARCHAR(100);
    ALTER TABLE purchase_orders ADD COLUMN IF NOT EXISTS total_amount NUMERIC(14,2) DEFAULT 0;
    
    -- In case po_number is null for existing rows, backfill with default PO-xxxx
    UPDATE purchase_orders SET po_number = 'PO-' || id WHERE po_number IS NULL;
    
    -- purchase_order_items
    ALTER TABLE purchase_order_items ADD COLUMN IF NOT EXISTS total_price NUMERIC(14,2) DEFAULT 0;
    """)
    conn.commit()
    print("Compatibility columns added successfully!")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
