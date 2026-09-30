import psycopg2

base_url = 'postgresql://postgres:InventoryDatabase123@db.ahgkvgbrwtbrmkoendfd.supabase.co:5432/postgres'
conn = psycopg2.connect(base_url)
cur = conn.cursor()

cur.execute("""
    SELECT table_schema, table_name 
    FROM information_schema.tables 
    WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
    ORDER BY table_schema, table_name;
""")
tables = cur.fetchall()
print(f"=== postgres DB ({len(tables)} tables) ===")
for s, t in tables[:30]:
    print(f"  {s}.{t}")
if len(tables) > 30:
    print(f"  ... and {len(tables)-30} more")

conn.close()
