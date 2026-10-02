import psycopg2

CONNECTION_STRING = "postgresql://postgres.ahgkvgbrwtbrmkoendfd:InventoryDatabase123@aws-0-ap-southeast-2.pooler.supabase.com:5432/postgres"

def main():
    conn = psycopg2.connect(CONNECTION_STRING)
    cur = conn.cursor()
    
    cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'inventory_transactions' AND table_schema = 'public'")
    cols = cur.fetchall()
    print("inventory_transactions columns:")
    for c in cols:
        print(f"  {c[0]} ({c[1]})")

    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
