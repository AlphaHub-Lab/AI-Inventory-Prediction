import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

base_url = 'postgresql://postgres:InventoryDatabase123@db.ahgkvgbrwtbrmkoendfd.supabase.co:5432/'

def ensure_database(dbname):
    conn = psycopg2.connect(base_url + 'postgres')
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s;", (dbname,))
    exists = cur.fetchone()
    if not exists:
        print(f"Creating database {dbname}...")
        cur.execute(f'CREATE DATABASE "{dbname}";')
        print(f"Database {dbname} created successfully.")
    else:
        print(f"Database {dbname} already exists.")
    cur.close()
    conn.close()

ensure_database("local_business_1")

# Now connect to local_business_1 to verify
conn = psycopg2.connect(base_url + "local_business_1")
cur = conn.cursor()
cur.execute("SELECT current_database();")
print("Connected to:", cur.fetchone()[0])
cur.close()
conn.close()
