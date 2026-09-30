import psycopg2

base_url = 'postgresql://postgres:InventoryDatabase123@db.ahgkvgbrwtbrmkoendfd.supabase.co:5432/'
master_dbs = ['master_medical', 'master_grocery', 'master_restaurant', 'master_stationery', 'master_dairy']

for mdb in master_dbs:
    conn = psycopg2.connect(base_url + mdb)
    cur = conn.cursor()
    print(f"\n=================== {mdb} ===================")
    cur.execute("""
        SELECT table_name FROM information_schema.tables 
        WHERE table_schema = 'catalog'
    """)
    tables = [t[0] for t in cur.fetchall()]
    print("Tables in catalog schema:", tables)
    for t in tables:
        cur.execute(f"SELECT COUNT(*) FROM catalog.{t};")
        cnt = cur.fetchone()[0]
        cur.execute(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_schema = 'catalog' AND table_name = '{t}' LIMIT 8;")
        cols = [c[0] for c in cur.fetchall()]
        print(f"  catalog.{t}: {cnt} rows, cols: {cols}")
    conn.close()
