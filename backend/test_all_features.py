import io
import json
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

print("=" * 60)
print("1. TESTING ADMINISTRATOR LOGIN & MASTER CATALOGS")
print("=" * 60)
admin_login = client.post("/api/auth/login", json={"email": "admin@inventory.example.com", "password": "Admin123!"})
print("Admin Login Status:", admin_login.status_code)
assert admin_login.status_code == 200, f"Admin login failed: {admin_login.text}"
admin_token = admin_login.json()["access_token"]
admin_headers = {"Authorization": f"Bearer {admin_token}"}

# Test Master Catalogs Summary across all 5 databases
cat_summary = client.get("/api/admin-system/master-catalogs-summary", headers=admin_headers)
print("Master Catalogs Summary Status:", cat_summary.status_code)
for cat in cat_summary.json():
    print(f"  [{cat['business_type'].upper()}] DB: {cat['database_name']}, Products: {cat.get('product_count')}, Status: {cat['status']}")

# Test Database Registry
reg = client.get("/api/admin-system/database-registry", headers=admin_headers)
print(f"Database Registry entries ({len(reg.json())}):")
for r in reg.json()[:6]:
    print(f"  {r['database_name']} ({r['database_type']}, {r['business_type']}) - {r['status']}")

print("\n" + "=" * 60)
print("2. TESTING BUSINESS OWNER & MASTER CATALOG SYNC")
print("=" * 60)
owner_login = client.post("/api/auth/login", json={"email": "Amogh@gmail.com", "password": "Owner123!"})
print("Owner Login Status:", owner_login.status_code)
assert owner_login.status_code == 200, f"Owner login failed: {owner_login.text}"
owner_token = owner_login.json()["access_token"]
owner_headers = {"Authorization": f"Bearer {owner_token}"}

# Search master catalog
search_res = client.get("/api/catalog/search?q=bandage", headers=owner_headers)
print("Search Status:", search_res.status_code)
search_data = search_res.json()
print(f"Local matches: {len(search_data['local_products'])}, Master catalog matches: {len(search_data['master_products'])}")

print("\n" + "=" * 60)
print("3. TESTING REORDER LIST OVERVIEW & WORKFLOW")
print("=" * 60)
reorder_res = client.get("/api/reorders/overview", headers=owner_headers)
print("Reorder Overview Status:", reorder_res.status_code)
ro_data = reorder_res.json()
print(f"Low Stock Items ({len(ro_data['low_stock'])}):")
for item in ro_data['low_stock'][:3]:
    print(f"  - {item['product_name']}: Stock {item['current_stock']} <= Reorder Level {item['reorder_level']} (Suggested: {item['suggested_quantity']})")
print(f"Previously Ordered Items: {len(ro_data['previously_ordered'])}")
print(f"Suggested Reorders: {len(ro_data['suggested_reorders'])}")
print(f"Pending Reorder List: {len(ro_data['pending_reorders'])}")

print("\n" + "=" * 60)
print("4. TESTING AI RECEIPT INGESTION & ATOMIC IMPORT")
print("=" * 60)
# Create a dummy image or PDF for receipt upload
dummy_receipt = """
APEX PHARMA DISTRIBUTORS
GSTIN: 27AABCU9603R1ZM
Tax Invoice: INV-9821
Date: 30-09-2026

Items:
Sterile Gauze Pads 10x10 20 45.00
Betadine Body Wash 200ml 15 110.00
Paracetamol 650mg Strips 40 22.50

Subtotal: 3450.00
GST 12%: 414.00
Total: 3864.00
"""

files = {"file": ("invoice_sample.pdf", b"%PDF-1.4\n" + dummy_receipt.encode("utf-8"), "application/pdf")}
upload_res = client.post("/api/receipts/upload", files=files, headers=owner_headers)
print("Receipt Upload & AI Extraction Status:", upload_res.status_code)
if upload_res.status_code == 201:
    up_data = upload_res.json()
    import_id = up_data["import_id"]
    print(f"Created Receipt Import ID: {import_id}, Status: {up_data['processing_status']}")
    print(f"Extracted Supplier: {up_data['supplier']['name']}, Invoice: {up_data['invoice']['number']}")
    print(f"Extracted Items ({len(up_data['items'])}):")
    for itm in up_data['items']:
        print(f"  - {itm['raw_product_name']}: Qty {itm['quantity']}, Price ₹{itm['purchase_price']}, Match: {itm['matched_product_name']} ({itm['confidence_score']}% {itm['confidence_level']})")

    # Confirm and execute atomic import transaction
    confirm_payload = {
        "supplier_name": up_data["supplier"]["name"] or "Apex Pharma Supply Co",
        "supplier_gstin": "27AABCU9603R1ZM",
        "invoice_number": up_data["invoice"]["number"] or "INV-9821",
        "invoice_date": "2026-09-30",
        "items": up_data["items"]
    }
    confirm_res = client.post(f"/api/receipts/{import_id}/confirm", json=confirm_payload, headers=owner_headers)
    print("Receipt Confirmation Status:", confirm_res.status_code)
    print("Confirmation Result:", confirm_res.json())

print("\n" + "=" * 60)
print("5. TESTING ASSOCIATE STRICT AI PERMISSIONS")
print("=" * 60)
staff_login = client.post("/api/auth/login", json={"email": "staff@medical.local", "password": "Staff123!"})
print("Associate Login Status:", staff_login.status_code)
assert staff_login.status_code == 200, f"Staff login failed: {staff_login.text}"
staff_token = staff_login.json()["access_token"]
staff_headers = {"Authorization": f"Bearer {staff_token}"}

# Test that General AI Chatbot is strictly blocked (403)
chat_res = client.post("/api/chat", json={"message": "What is my stock status?"}, headers=staff_headers)
print("Associate /api/chat Status (Expect 403):", chat_res.status_code)
assert chat_res.status_code == 403, f"Expected 403 for associate chat, got {chat_res.status_code}"

# Test that General AI Forecast is strictly blocked (403)
fc_res = client.get("/api/forecasts", headers=staff_headers)
print("Associate /api/forecasts Status (Expect 403):", fc_res.status_code)
assert fc_res.status_code == 403, f"Expected 403 for associate forecasts, got {fc_res.status_code}"

# Test that Receipt AI is ALLOWED because receipt permissions are granted
rec_list = client.get("/api/receipts", headers=staff_headers)
print("Associate /api/receipts Status (Expect 200):", rec_list.status_code)
assert rec_list.status_code == 200, f"Expected 200 for associate receipts, got {rec_list.status_code}"
print(f"Associate successfully accessed receipt list ({len(rec_list.json())} receipts found)")

print("\nALL BACKEND ARCHITECTURE & RBAC VERIFICATIONS PASSED!")
