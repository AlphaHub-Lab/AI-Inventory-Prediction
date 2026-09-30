import psycopg2

base_url = 'postgresql://postgres:InventoryDatabase123@db.ahgkvgbrwtbrmkoendfd.supabase.co:5432/'
conn = psycopg2.connect(base_url + 'admin_db')
cur = conn.cursor()

print("--- USERS in admin_db ---")
cur.execute("SELECT id, email, role, is_active FROM users;")
for r in cur.fetchall():
    print(r)

print("\n--- BUSINESSES in admin_db ---")
cur.execute("SELECT id, name, business_type, master_database_name, local_database_name, status FROM businesses;")
for r in cur.fetchall():
    print(r)

print("\n--- DATABASE REGISTRY in admin_db ---")
cur.execute("SELECT id, database_name, database_type, business_type, business_id, status FROM database_registry;")
for r in cur.fetchall():
    print(r)

conn.close()
