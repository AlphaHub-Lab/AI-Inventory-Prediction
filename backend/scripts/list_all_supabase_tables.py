import psycopg2

CONNECTION_STRING = "postgresql://postgres.ahgkvgbrwtbrmkoendfd:InventoryDatabase123@aws-0-ap-southeast-2.pooler.supabase.com:5432/postgres"

def main():
    conn = psycopg2.connect(CONNECTION_STRING)
    cur = conn.cursor()
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name;")
    tables = [r[0] for r in cur.fetchall()]
    print(f"Total tables in Supabase public schema: {len(tables)}")
    for i, t in enumerate(tables, 1):
        print(f"  {i}. {t}")
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
