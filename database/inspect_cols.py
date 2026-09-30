import psycopg2

base_url = 'postgresql://postgres:InventoryDatabase123@db.ahgkvgbrwtbrmkoendfd.supabase.co:5432/'
conn = psycopg2.connect(base_url + 'admin_db')
cur = conn.cursor()

def show_cols(table):
    cur.execute(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{table}';")
    cols = cur.fetchall()
    print(f"Columns in {table}:", cols)

show_cols('businesses')
show_cols('users')
show_cols('database_registry')
show_cols('auth_sessions')

cur.execute("SELECT * FROM businesses;")
print("Businesses rows:", cur.fetchall())

cur.execute("SELECT * FROM database_registry;")
print("Database registry rows:", cur.fetchall())

conn.close()
