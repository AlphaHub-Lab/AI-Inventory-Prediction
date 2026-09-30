import psycopg2
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

conn = psycopg2.connect('postgresql://postgres:InventoryDatabase123@db.ahgkvgbrwtbrmkoendfd.supabase.co:5432/admin_db')
cur = conn.cursor()
cur.execute("SELECT id, email, password_hash, role, is_active FROM users WHERE email = 'admin@inventory.example.com';")
row = cur.fetchone()
print("Admin user:", row[:2], row[3:])
if row:
    matches = pwd_context.verify("Admin123!", row[2])
    print("Admin123! matches:", matches)
conn.close()
