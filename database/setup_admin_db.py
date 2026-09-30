import psycopg2
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
admin_hash = pwd_context.hash("Admin123!")
owner_hash = pwd_context.hash("Owner123!")
staff_hash = pwd_context.hash("Staff123!")

conn = psycopg2.connect('postgresql://postgres:InventoryDatabase123@db.ahgkvgbrwtbrmkoendfd.supabase.co:5432/admin_db')
cur = conn.cursor()

# 1. Update admin password
cur.execute("UPDATE users SET password_hash = %s WHERE email = 'admin@inventory.example.com';", (admin_hash,))
print("Updated admin@inventory.example.com password to Admin123!")

# 2. Update owner password
cur.execute("UPDATE users SET password_hash = %s WHERE email = 'Amogh@gmail.com';", (owner_hash,))
print("Updated Amogh@gmail.com password to Owner123!")

# 3. Add associate if not exists
cur.execute("SELECT id FROM users WHERE email = 'staff@medical.local';")
staff = cur.fetchone()
if not staff:
    cur.execute("""
        INSERT INTO users (email, full_name, password_hash, role, is_active, business_id, created_at, updated_at)
        VALUES ('staff@medical.local', 'Sarah Staff', %s, 'associate', TRUE, 1, NOW(), NOW())
        RETURNING id;
    """, (staff_hash,))
    staff_id = cur.fetchone()[0]
    print(f"Created associate staff@medical.local (id={staff_id}) with password Staff123!")
    # Grant initial operational permissions to staff (including receipt permissions!)
    permissions = [
        "inventory.view", "inventory.create", "inventory.update",
        "sales.view", "sales.create",
        "orders.view", "orders.create",
        "reorder.view", "reorder.create",
        "receipt.scan", "receipt.extract", "receipt.review", "receipt.import"
    ]
    for p in permissions:
        cur.execute("""
            INSERT INTO user_permissions (user_id, permission, granted_by, created_at)
            VALUES (%s, %s, 2, NOW())
            ON CONFLICT DO NOTHING;
        """, (staff_id, p))
    print(f"Granted {len(permissions)} permissions to associate {staff_id}")
else:
    cur.execute("UPDATE users SET password_hash = %s WHERE email = 'staff@medical.local';", (staff_hash,))
    print("Updated staff@medical.local password to Staff123!")

# 4. Register local_business_1 in database_registry
cur.execute("SELECT id FROM database_registry WHERE database_name = 'local_business_1';")
if not cur.fetchone():
    cur.execute("""
        INSERT INTO database_registry (database_name, database_type, business_type, business_id, status, created_at)
        VALUES ('local_business_1', 'local', 'medical', 1, 'active', NOW());
    """)
    print("Registered local_business_1 in database_registry")

conn.commit()
cur.close()
conn.close()
