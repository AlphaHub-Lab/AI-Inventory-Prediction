import psycopg2
from datetime import date, timedelta

base_url = 'postgresql://postgres:InventoryDatabase123@db.ahgkvgbrwtbrmkoendfd.supabase.co:5432/'

conn_master = psycopg2.connect(base_url + 'master_medical')
cur_m = conn_master.cursor()
cur_m.execute("""
    SELECT p.id, p.sku, p.barcode, p.product_name, p.brand, p.category, p.subcategory,
           d.generic_name, d.dosage_form, d.strength, d.manufacturer, d.prescription_required
    FROM catalog.products p
    LEFT JOIN catalog.medical_product_details d ON p.id = d.product_id
    LIMIT 15;
""")
master_prods = cur_m.fetchall()
cur_m.close()
conn_master.close()

conn_local = psycopg2.connect(base_url + 'local_business_1')
cur_l = conn_local.cursor()

# Set business profile
cur_l.execute("""
    INSERT INTO business_profile (name, business_type, owner_email, address, phone)
    VALUES ('Skull Medicals', 'medical', 'Amogh@gmail.com', '123 Health Ave, Metro City', '+91 9876543210')
    ON CONFLICT DO NOTHING;
""")

# Default Supplier
cur_l.execute("""
    INSERT INTO suppliers (name, contact_person, email, phone, address, gstin, lead_time_days)
    VALUES ('Apex Pharma Distributors', 'Rajesh Sharma', 'orders@apexpharma.com', '+91 9811223344', 'Warehouse 4, Industrial Area', '27AABCU9603R1ZM', 3)
    ON CONFLICT (name) DO UPDATE SET email = EXCLUDED.email
    RETURNING id;
""")
sup_id = cur_l.fetchone()[0]

# Default Customer
cur_l.execute("""
    INSERT INTO customers (name, phone, email)
    VALUES ('Walk-in Customer', '9999999999', 'walkin@store.local')
    ON CONFLICT DO NOTHING;
""")

print(f"Importing {len(master_prods)} products into local_business_1...")
for idx, p in enumerate(master_prods):
    m_id, sku, barcode, name, brand, cat, subcat, gen, form, strg, mfg, rx = p
    cost = 50.0 + idx * 15.0
    selling = cost * 1.3
    mrp = cost * 1.45
    # Some items low stock for reorder list testing
    stock = 4 if idx < 4 else (12 + idx * 5)
    reorder_level = 15
    
    cur_l.execute("""
        INSERT INTO products (
            master_product_id, sku, barcode, product_name, brand, category, subcategory,
            current_stock, reorder_level, minimum_stock, maximum_stock,
            selling_price, purchase_price, mrp, gst_percentage, supplier_id,
            generic_name, dosage_form, strength, manufacturer, prescription_required
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s,
            %s, %s, 5, 200,
            %s, %s, %s, 12.0, %s,
            %s, %s, %s, %s, %s
        ) ON CONFLICT (sku) DO UPDATE SET current_stock = EXCLUDED.current_stock
        RETURNING id;
    """, (
        m_id, sku, barcode or f"BAR-{sku}", name, brand, cat, subcat,
        stock, reorder_level,
        selling, cost, mrp, sup_id,
        gen, form, strg, mfg, rx or False
    ))
    prod_id = cur_l.fetchone()[0]
    
    # Batch
    cur_l.execute("""
        INSERT INTO inventory_batches (
            product_id, lot_number, quantity, cost_price, manufacturing_date, expiry_date
        ) VALUES (%s, %s, %s, %s, %s, %s);
    """, (
        prod_id, f"LOT-2026-{100+idx}", stock, cost,
        date.today() - timedelta(days=60),
        date.today() + timedelta(days=180 + idx * 30)
    ))

    # Inventory transaction
    cur_l.execute("""
        INSERT INTO inventory_transactions (
            product_id, transaction_type, quantity, previous_stock, new_stock, performed_by, note
        ) VALUES (%s, 'Purchase', %s, 0, %s, 'Amogh@gmail.com', 'Initial stock intake');
    """, (prod_id, stock, stock))
    
    # If low stock, also insert into reorder_list
    if stock <= reorder_level:
        suggested = reorder_level * 3 - stock
        cur_l.execute("""
            INSERT INTO reorder_list (
                product_id, supplier_id, current_stock, reorder_level,
                suggested_quantity, selected_quantity, last_order_date, last_order_quantity, status
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, 'pending'
            ) ON CONFLICT (product_id) DO UPDATE SET current_stock = EXCLUDED.current_stock;
        """, (
            prod_id, sup_id, stock, reorder_level, suggested, suggested,
            date.today() - timedelta(days=14), 50
        ))

# Create a sample purchase order
cur_l.execute("""
    INSERT INTO purchase_orders (po_number, supplier_id, status, total_amount, created_by)
    VALUES ('PO-2026-0001', %s, 'approved', 4500.00, 'Amogh@gmail.com')
    ON CONFLICT (po_number) DO NOTHING;
""", (sup_id,))

# Create sample sale
cur_l.execute("""
    INSERT INTO sales (invoice_id, customer_name, subtotal, tax, total, payment_method)
    VALUES ('INV-2026-0001', 'Walk-in Customer', 350.00, 42.00, 392.00, 'UPI')
    ON CONFLICT (invoice_id) DO NOTHING;
""",)

conn_local.commit()
print("Local business seeded successfully!")
cur_l.close()
conn_local.close()
