import psycopg2

CONNECTION_STRING = "postgresql://postgres.ahgkvgbrwtbrmkoendfd:InventoryDatabase123@aws-0-ap-southeast-2.pooler.supabase.com:5432/postgres"

conn = psycopg2.connect(CONNECTION_STRING)
cur = conn.cursor()

cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name")
tables = [r[0] for r in cur.fetchall()]
print(f"Total tables: {len(tables)}")
for t in tables:
    print(f"  {t}")

# Check if purchase_items exists
for tbl in ['purchase_items', 'purchases', 'purchase_orders', 'purchase_order_items']:
    cur.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name = %s AND table_schema = 'public' ORDER BY ordinal_position",
        (tbl,)
    )
    cols = [r[0] for r in cur.fetchall()]
    print(f"\n{tbl}: {cols}")

cur.close()
conn.close()
