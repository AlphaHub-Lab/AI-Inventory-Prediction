import psycopg2

base_url = 'postgresql://postgres:InventoryDatabase123@db.ahgkvgbrwtbrmkoendfd.supabase.co:5432/'
db_names = ['admin_db', 'master_medical', 'master_grocery', 'master_restaurant', 'master_stationery', 'master_dairy']

for dbname in db_names:
    try:
        conn = psycopg2.connect(base_url + dbname)
        cur = conn.cursor()
        cur.execute("""
            SELECT table_schema, table_name 
            FROM information_schema.tables 
            WHERE table_schema NOT IN ('information_schema', 'pg_catalog')
            ORDER BY table_schema, table_name;
        """)
        tables = cur.fetchall()
        print(f"=== {dbname} ({len(tables)} tables) ===")
        for s, t in tables[:25]:
            print(f"  {s}.{t}")
        if len(tables) > 25:
            print(f"  ... and {len(tables)-25} more")
        conn.close()
    except Exception as e:
        print(f"Error connecting to {dbname}: {e}")
