import psycopg2

conn = psycopg2.connect('postgresql://postgres:InventoryDatabase123@db.ahgkvgbrwtbrmkoendfd.supabase.co:5432/admin_db')
cur = conn.cursor()
cur.execute("UPDATE users SET email = 'sarah@skullmedicals.com' WHERE email = 'staff@medical.local';")
conn.commit()
print("Updated associate email to sarah@skullmedicals.com")
conn.close()
