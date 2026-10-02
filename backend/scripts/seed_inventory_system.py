import sys
from pathlib import Path
from datetime import date, datetime, timedelta
import uuid

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

import psycopg2
from psycopg2.extras import RealDictCursor
from app.security import hash_password

DB_URL = "postgresql://postgres:InventoryDatabase123@db.ahgkvgbrwtbrmkoendfd.supabase.co:5432/inventory_system"

def seed_database():
    print(f"Connecting to inventory_system database for seeding...")
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = True
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # 1. Seed Roles
    print("1. Seeding roles...")
    roles = [
        ("admin", "System Administrator with full access across platform"),
        ("business_owner", "Business Owner / Store Manager with access to store operations, analytics and AI"),
        ("associate", "Store Associate / Cashier with access to inventory, POS and receipts")
    ]
    role_ids = {}
    for name, desc in roles:
        cur.execute("""
            INSERT INTO roles (name, description)
            VALUES (%s, %s)
            ON CONFLICT (name) DO UPDATE SET description = EXCLUDED.description
            RETURNING id, name;
        """, (name, desc))
        row = cur.fetchone()
        role_ids[row["name"]] = row["id"]

    # 2. Seed Permissions
    print("2. Seeding permissions...")
    perms = [
        ("products.view", "View products", "products"),
        ("products.manage", "Manage products", "products"),
        ("inventory.view", "View inventory stock", "inventory"),
        ("inventory.adjust", "Adjust inventory stock", "inventory"),
        ("reorder.view", "View reorders", "reorder"),
        ("reorder.create", "Create and edit reorders", "reorder"),
        ("receipts.upload", "Upload supplier delivery receipts", "receipts"),
        ("receipts.review", "Review and approve receipts", "receipts"),
        ("ai.general", "Access AI Chat, Predictions and Forecasts", "ai"),
        ("admin.system", "Access Admin System & Multi-Store Management", "admin"),
        ("sales.pos", "Perform sales checkout at POS", "sales"),
    ]
    perm_ids = {}
    for name, desc, mod in perms:
        cur.execute("""
            INSERT INTO permissions (name, description, module)
            VALUES (%s, %s, %s)
            ON CONFLICT (name) DO UPDATE SET description = EXCLUDED.description
            RETURNING id, name;
        """, (name, desc, mod))
        row = cur.fetchone()
        perm_ids[row["name"]] = row["id"]

    # Role Permissions
    for perm_name, p_id in perm_ids.items():
        # Admin gets all
        cur.execute("""
            INSERT INTO role_permissions (role_id, permission_id)
            VALUES (%s, %s)
            ON CONFLICT (role_id, permission_id) DO NOTHING;
        """, (role_ids["admin"], p_id))

        # Business owner gets all except admin.system
        if perm_name != "admin.system":
            cur.execute("""
                INSERT INTO role_permissions (role_id, permission_id)
                VALUES (%s, %s)
                ON CONFLICT (role_id, permission_id) DO NOTHING;
            """, (role_ids["business_owner"], p_id))

        # Associate gets operations but NOT ai.general or admin.system or products.manage
        if perm_name in ["products.view", "inventory.view", "reorder.view", "receipts.upload", "receipts.review", "sales.pos"]:
            cur.execute("""
                INSERT INTO role_permissions (role_id, permission_id)
                VALUES (%s, %s)
                ON CONFLICT (role_id, permission_id) DO NOTHING;
            """, (role_ids["associate"], p_id))

    # 3. Seed Business Types (Exact 6 types from ER diagram)
    print("3. Seeding 6 business types...")
    btypes = [
        ("medical", "Medical / Pharmacy", "Pharmaceutical drugs, medical devices, OTC medications", True, True),
        ("grocery", "Grocery", "Packaged foods, pantry staples, fresh fruits and produce", True, True),
        ("restaurant", "Restaurant / Food Business", "Ingredients, recipes, perishable kitchen supplies", True, True),
        ("stationery", "Stationery", "Paper products, writing instruments, office supplies", True, True),
        ("dairy", "Dairy", "Milk, yogurt, cheeses, dairy products with strict shelf lives", True, True),
        ("other", "Others / General Retail", "General retail goods with store-defined custom products", True, False),
    ]
    btype_ids = {}
    for code, name, desc, is_pred, has_mc in btypes:
        cur.execute("""
            INSERT INTO business_types (code, name, description, is_predefined, has_master_catalog)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (code) DO UPDATE SET 
                name = EXCLUDED.name,
                description = EXCLUDED.description,
                has_master_catalog = EXCLUDED.has_master_catalog
            RETURNING id, code;
        """, (code, name, desc, is_pred, has_mc))
        row = cur.fetchone()
        btype_ids[row["code"]] = row["id"]

    # 4. Seed Master Units
    print("4. Seeding master units...")
    units = [
        ("Kilogram", "kg"),
        ("Gram", "g"),
        ("Liter", "l"),
        ("Milliliter", "ml"),
        ("Unit", "unit"),
        ("Box", "box"),
        ("Strip", "strip"),
        ("Bottle", "bottle"),
        ("Vial", "vial"),
        ("Pack", "pack"),
        ("Piece", "pc"),
        ("Meter", "m")
    ]
    unit_ids = {}
    for name, sym in units:
        cur.execute("SELECT id FROM master_units WHERE symbol = %s", (sym,))
        row = cur.fetchone()
        if row:
            unit_ids[sym] = row["id"]
        else:
            cur.execute("""
                INSERT INTO master_units (name, symbol)
                VALUES (%s, %s)
                RETURNING id;
            """, (name, sym))
            unit_ids[sym] = cur.fetchone()["id"]

    # 5. Seed Businesses
    print("5. Seeding businesses...")
    businesses = [
        ("medical", "Skull Medicals & Healthcare", "102 Health Avenue, Central District", "+91-9876543210", "contact@skullmedicals.com", "27AAAAA0000A1Z5"),
        ("grocery", "GreenLeaf Supermarket", "45 Market Square, North Sector", "+91-9876543211", "info@greenleaf.com", "27BBBBB1111B1Z6"),
        ("restaurant", "Gourmet Bistro & Cafe", "12 Culinary Row, High Street", "+91-9876543212", "chef@gourmetbistro.com", "27CCCCC2222C1Z7"),
        ("stationery", "Apex Office & Stationery Supplies", "88 University Road, Education Hub", "+91-9876543213", "sales@apexstationery.com", "27DDDDD3333D1Z8"),
        ("dairy", "Pure Pastures Dairy", "3 Dairy Farm Road, Green Meadows", "+91-9876543214", "milk@puredairy.com", "27EEEEE4444E1Z9"),
        ("other", "Universal General Traders", "5 Commercial Plaza, Trade Center", "+91-9876543215", "support@generaltraders.com", "27FFFFF5555F1Z0")
    ]
    business_ids = {}
    for b_type_code, name, addr, phone, email, gstin in businesses:
        cur.execute("""
            INSERT INTO businesses (business_type_id, name, address, phone, email, gstin, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, true)
            RETURNING id, name;
        """, (btype_ids[b_type_code], name, addr, phone, email, gstin))
        row = cur.fetchone()
        business_ids[b_type_code] = row["id"]

    # 6. Seed Users
    print("6. Seeding users...")
    admin_pw = hash_password("Admin123!")
    owner_pw = hash_password("Owner123!")
    staff_pw = hash_password("Staff123!")

    users_data = [
        (None, role_ids["admin"], "Platform Administrator", "admin@inventory.example.com", "admin", admin_pw, "+91-9999999999"),
        (business_ids["medical"], role_ids["business_owner"], "Amogh Sonawane", "Amogh@gmail.com", "amogh_owner", owner_pw, "+91-9888888881"),
        (business_ids["medical"], role_ids["associate"], "Sarah Associate", "sarah@skullmedicals.com", "sarah_staff", staff_pw, "+91-9888888882"),
        (business_ids["grocery"], role_ids["business_owner"], "Rajesh Sharma", "rajesh@greenleaf.com", "rajesh_owner", owner_pw, "+91-9888888883"),
    ]

    user_ids = {}
    for b_id, r_id, name, email, uname, pw, phone in users_data:
        cur.execute("""
            INSERT INTO users (business_id, role_id, name, email, username, password_hash, phone, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, %s, true)
            ON CONFLICT (email) DO UPDATE SET
                password_hash = EXCLUDED.password_hash,
                role_id = EXCLUDED.role_id,
                business_id = EXCLUDED.business_id,
                name = EXCLUDED.name,
                is_active = true
            RETURNING id, email;
        """, (b_id, r_id, name, email, uname, pw, phone))
        row = cur.fetchone()
        user_ids[row["email"]] = row["id"]

    # Update owner_id on businesses
    cur.execute("UPDATE businesses SET owner_id = %s WHERE id = %s", (user_ids["Amogh@gmail.com"], business_ids["medical"]))
    cur.execute("UPDATE businesses SET owner_id = %s WHERE id = %s", (user_ids["rajesh@greenleaf.com"], business_ids["grocery"]))

    # 7. Seed Master Categories, Brands, Products for Medical & Grocery
    print("7. Seeding master catalog...")
    # Medical Category
    cur.execute("""
        INSERT INTO master_categories (business_type_id, name)
        VALUES (%s, 'Pharmaceuticals') RETURNING id;
    """, (btype_ids["medical"],))
    med_cat_id = cur.fetchone()["id"]

    cur.execute("""
        INSERT INTO master_brands (business_type_id, name)
        VALUES (%s, 'Cipla') RETURNING id;
    """, (btype_ids["medical"],))
    cipla_id = cur.fetchone()["id"]

    cur.execute("""
        INSERT INTO master_brands (business_type_id, name)
        VALUES (%s, 'Sun Pharma') RETURNING id;
    """, (btype_ids["medical"],))
    sun_id = cur.fetchone()["id"]

    # Master Products for Medical
    med_prods = [
        ("Paracetamol 500mg Tablets", "Paracetamol", "MED-PARA-500", "8901234567890", 30.00, 12.0, True, 730, unit_ids["strip"], cipla_id, med_cat_id),
        ("Amoxicillin 500mg Capsules", "Amoxicillin", "MED-AMOX-500", "8901234567891", 85.00, 12.0, True, 730, unit_ids["strip"], sun_id, med_cat_id),
        ("Cetirizine 10mg Tablets", "Cetirizine HCl", "MED-CETI-010", "8901234567892", 25.00, 12.0, False, 1095, unit_ids["strip"], cipla_id, med_cat_id),
        ("Adhesive Bandage Strips", "Sterile Bandage", "MED-BAND-001", "8901234567893", 50.00, 18.0, False, 1460, unit_ids["box"], cipla_id, med_cat_id),
        ("Betadine Antiseptic Solution", "Povidone Iodine 10%", "MED-BETA-100", "8901234567894", 120.00, 18.0, False, 1095, unit_ids["bottle"], sun_id, med_cat_id),
    ]

    master_prod_ids = {}
    for name, gen, sku, barcode, mrp, gst, rx, shelf, u_id, b_id, c_id in med_prods:
        cur.execute("""
            INSERT INTO master_products (
                business_type_id, category_id, brand_id, sku, barcode, name, generic_name,
                unit_id, mrp, gst_percentage, prescription_required, shelf_life_days, is_active
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, true)
            RETURNING id, sku;
        """, (btype_ids["medical"], c_id, b_id, sku, barcode, name, gen, u_id, mrp, gst, rx, shelf))
        row = cur.fetchone()
        master_prod_ids[row["sku"]] = row["id"]

    # 8. Seed Store Suppliers for Skull Medicals
    print("8. Seeding suppliers...")
    cur.execute("""
        INSERT INTO suppliers (business_id, name, contact_person, phone, email, gstin)
        VALUES (%s, 'Apex Pharma Distributors', 'Ramesh Gupta', '+91-9820011223', 'orders@apexpharma.com', '27AABCA1234F1Z1')
        RETURNING id;
    """, (business_ids["medical"],))
    apex_sup_id = cur.fetchone()["id"]

    cur.execute("""
        INSERT INTO suppliers (business_id, name, contact_person, phone, email, gstin)
        VALUES (%s, 'MedHealth Logistics', 'Suresh Patel', '+91-9820044556', 'supply@medhealth.com', '27BBDDB5678G2Z2')
        RETURNING id;
    """, (business_ids["medical"],))
    med_sup_id = cur.fetchone()["id"]

    # 9. Seed Business Products for Skull Medicals
    print("9. Seeding business products for Skull Medicals...")
    store_prods = [
        ("MED-PARA-500", "Paracetamol 500mg Tablets", 28.00, 20.00, 30, apex_sup_id),
        ("MED-AMOX-500", "Amoxicillin 500mg Capsules", 80.00, 60.00, 25, apex_sup_id),
        ("MED-CETI-010", "Cetirizine 10mg Tablets", 22.00, 15.00, 40, med_sup_id),
        ("MED-BAND-001", "Adhesive Bandage Strips", 48.00, 32.00, 20, apex_sup_id),
        ("MED-BETA-100", "Betadine Antiseptic Solution", 115.00, 85.00, 15, med_sup_id),
    ]

    bprod_ids = {}
    for sku, name, sell_price, cost_price, rlevel, sup_id in store_prods:
        m_id = master_prod_ids.get(sku)
        cur.execute("""
            INSERT INTO business_products (
                business_id, master_product_id, sku, barcode, name, selling_price, reorder_level, default_supplier_id, is_active
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, true)
            RETURNING id, sku;
        """, (business_ids["medical"], m_id, sku, f"8901{sku.replace('-', '')}", name, sell_price, rlevel, sup_id))
        row = cur.fetchone()
        bp_id = row["id"]
        bprod_ids[sku] = bp_id

        # Link product supplier
        cur.execute("""
            INSERT INTO product_suppliers (business_product_id, supplier_id, is_default, lead_time_days, last_purchase_price)
            VALUES (%s, %s, true, 3, %s);
        """, (bp_id, sup_id, cost_price))

        # Seed initial inventory batch
        cur.execute("""
            INSERT INTO inventory_batches (
                business_product_id, batch_number, manufacturing_date, expiry_date,
                purchase_price, mrp, quantity, available_quantity, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'active')
            RETURNING id;
        """, (
            bp_id,
            f"LOT-{sku[:4]}-2026",
            date.today() - timedelta(days=90),
            date.today() + timedelta(days=500),
            cost_price,
            sell_price,
            85.0,
            85.0
        ))
        batch_id = cur.fetchone()["id"]

        # Seed initial inventory transaction
        cur.execute("""
            INSERT INTO inventory_transactions (
                business_id, business_product_id, batch_id, transaction_type,
                quantity, unit_price, previous_stock, new_stock, performed_by
            ) VALUES (%s, %s, %s, 'purchase', %s, %s, 0.0, %s, %s);
        """, (business_ids["medical"], bp_id, batch_id, 85.0, cost_price, 85.0, user_ids["Amogh@gmail.com"]))

    # 10. Seed Customers
    print("10. Seeding customers...")
    cur.execute("""
        INSERT INTO customers (business_id, name, phone, email, address)
        VALUES (%s, 'Walk-in Retail Customer', '+91-9800000000', 'walkin@example.com', 'Local Store Front');
    """, (business_ids["medical"],))

    # 11. Seed System Settings
    print("11. Seeding system settings...")
    cur.execute("""
        INSERT INTO system_settings (key, value, description)
        VALUES 
            ('app_version', '{"version": "2.0.0", "engine": "Universal Single DB"}'::jsonb, 'Application Version'),
            ('ai_settings', '{"model": "Llama-V3p2-3b-Reasoning", "temperature": 0.2}'::jsonb, 'AI Model Settings')
        ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;
    """)

    print("\n[OK] DATABASE SEEDING COMPLETED SUCCESSFULLY!")
    cur.close()
    conn.close()

if __name__ == "__main__":
    seed_database()
