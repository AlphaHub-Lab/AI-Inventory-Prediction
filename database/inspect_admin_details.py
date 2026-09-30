import psycopg2

base_url = 'postgresql://postgres:InventoryDatabase123@db.ahgkvgbrwtbrmkoendfd.supabase.co:5432/admin_db'
conn = psycopg2.connect(base_url)
cur = conn.cursor()

cur.execute("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public'
    ORDER BY table_name;
""")
tables = [t[0] for t in cur.fetchall()]
print(f"Total tables in admin_db: {len(tables)}")
print(tables)

for t in ['businesses', 'users', 'database_registry', 'roles', 'user_permissions', 'auth_sessions', 'audit_logs']:
    if t in tables:
        cur.execute(f"SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_schema = 'public' AND table_name = '{t}' ORDER BY ordinal_position;")
        cols = cur.fetchall()
        print(f"\n--- {t} ---")
        for c in cols:
            print(f"  {c[0]} ({c[1]}, nullable={c[2]})")

conn.close()
