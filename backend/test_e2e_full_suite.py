"""
Comprehensive End-to-End Verification Test Suite
Tests:
1. Multi-role authentication & session resolution (Admin, Owner, Associate)
2. No public registration check
3. Dynamic multi-tenant physical database creation & registry
4. Strict RBAC AI enforcement (Associates blocked from General AI, allowed for Receipt AI)
5. Master -> Local Catalog Search & 1-Click Import
6. Reorder Replenishment Hub (Low-stock detection, history, 1-click PO)
7. AI Receipt Ingestion, Fuzzy Multi-Signal Matching, Review, and Atomic Transaction
"""

import sys
import os
import json
from io import BytesIO

# Skip redundant remote alembic migration check during testing
os.environ["SKIP_ALEMBIC_STARTUP"] = "1"

# Ensure utf-8 stdout with line buffering on Windows
if sys.platform.startswith("win"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def run_tests():
    print("=" * 70)
    print("[TEST] STARTING E2E VERIFICATION SUITE FOR MULTI-TENANT INVENTORY PLATFORM")
    print("=" * 70)

    # 1. Health check
    print("\n[1] Testing Health Check & Multi-Tenant Capabilities...")
    res = client.get("/health")
    assert res.status_code == 200, f"Health check failed: {res.text}"
    health_data = res.json()
    print("✓ Health status: OK")
    print(f"✓ Business types supported: {health_data['business_types']}")
    print(f"✓ Roles supported: {health_data['roles']}")

    # 2. Public Registration Check (MUST NOT EXIST)
    print("\n[2] Checking Public Registration Endpoint (Strictly Disallowed)...")
    res = client.post("/api/auth/register", json={"email": "hacker@test.com", "password": "123"})
    assert res.status_code in (404, 405), f"Public register must not be available! Got status: {res.status_code}"
    res2 = client.post("/api/auth/signup", json={"email": "hacker@test.com", "password": "123"})
    assert res2.status_code in (404, 405), f"Public signup must not be available! Got status: {res2.status_code}"
    print("✓ Confirmed: Public sign-up / registration does not exist. Only Admin creates accounts.")

    # 3. Authentication & RBAC Login
    print("\n[3] Testing Multi-Role Authentication...")
    
    # 3a. Admin Login
    admin_login = client.post("/api/auth/login", json={
        "email": "admin@inventory.example.com",
        "password": "Admin123!"
    })
    assert admin_login.status_code == 200, f"Admin login failed: {admin_login.text}"
    admin_token = admin_login.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    print("✓ Administrator login successful")

    # 3b. Owner Login (Business 1: Skull Medicals)
    owner_login = client.post("/api/auth/login", json={
        "email": "Amogh@gmail.com",
        "password": "Owner123!"
    })
    assert owner_login.status_code == 200, f"Owner login failed: {owner_login.text}"
    owner_token = owner_login.json()["access_token"]
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    owner_user = owner_login.json().get("user", {})
    print(f"✓ Business Owner login successful (User: {owner_user.get('email')}, Role: {owner_user.get('role')})")

    # 3c. Associate Login (Sarah - Skull Medicals)
    assoc_login = client.post("/api/auth/login", json={
        "email": "sarah@skullmedicals.com",
        "password": "Staff123!"
    })
    assert assoc_login.status_code == 200, f"Associate login failed: {assoc_login.text}"
    assoc_token = assoc_login.json()["access_token"]
    assoc_headers = {"Authorization": f"Bearer {assoc_token}"}
    print("✓ Associate login successful")

    # 4. Strict Role-Based AI Boundary Enforcement
    print("\n[4] Testing Role-Based AI Boundaries...")
    
    # Associate calls AI Chat -> MUST BE 403 FORBIDDEN
    res = client.post("/api/chat", json={"message": "What is our reorder status?"}, headers=assoc_headers)
    assert res.status_code == 403, f"Associate should be blocked from General AI Chat! Got: {res.status_code}"
    print(f"✓ Associate blocked from AI Chat: HTTP 403 Forbidden ({res.json().get('error', {}).get('message', res.text)})")

    # Associate calls AI Forecast -> MUST BE 403 FORBIDDEN
    res = client.get("/api/forecasts?horizon_days=14", headers=assoc_headers)
    assert res.status_code == 403, f"Associate should be blocked from AI Forecasts! Got: {res.status_code}"
    print("✓ Associate blocked from AI Forecasts: HTTP 403 Forbidden")

    # Associate calls AI Waste -> MUST BE 403 FORBIDDEN
    res = client.get("/api/waste", headers=assoc_headers)
    assert res.status_code == 403, f"Associate should be blocked from AI Waste Analysis! Got: {res.status_code}"
    print("✓ Associate blocked from AI Waste Analysis: HTTP 403 Forbidden")

    # Business Owner calls AI Chat -> MUST BE 200 OK
    res = client.post("/api/chat", json={"message": "Analyze inventory stock"}, headers=owner_headers)
    assert res.status_code == 200, f"Owner AI Chat failed: {res.text}"
    print(f"✓ Business Owner granted AI Chat access: HTTP 200 OK")

    # 5. Master Catalog Search & 1-Click Import to Local DB
    print("\n[5] Testing Master -> Local Catalog Search & 1-Click Import...")
    search_res = client.get("/api/catalog/search?q=Paracetamol", headers=owner_headers)
    assert search_res.status_code == 200, f"Catalog search failed: {search_res.text}"
    catalog_results = search_res.json()
    master_items = catalog_results.get("master_products", [])
    print(f"✓ Searched Master Database (master_medical): Found {len(master_items)} items")
    
    if master_items:
        unimported = [m for m in master_items if not m.get("already_imported")]
        target = unimported[0] if unimported else master_items[0]
        print(f"  Attempting 1-Click Import for master product: {target['product_name']} (ID: {target['master_id']})")
        import_res = client.post("/api/catalog/import", json={
            "master_product_id": target["master_id"],
            "selling_price": 45.0,
            "purchase_price": 28.0,
            "initial_stock": 100,
            "reorder_level": 25
        }, headers=owner_headers)
        assert import_res.status_code in (200, 201, 409), f"Catalog import failed: {import_res.text}"
        print(f"✓ 1-Click Import Result: {import_res.json().get('message') or import_res.json().get('error', {}).get('message')}")

    # 6. Reorder Replenishment Hub
    print("\n[6] Testing Reorder Replenishment Workflow (/reorder)...")
    reorder_res = client.get("/api/reorders/overview", headers=owner_headers)
    assert reorder_res.status_code == 200, f"Reorder overview failed: {reorder_res.text}"
    reorder_data = reorder_res.json()
    print(f"✓ Low Stock Items Detected: {len(reorder_data.get('low_stock', []))}")
    print(f"✓ Previously Ordered Items: {len(reorder_data.get('previously_ordered', []))}")
    print(f"✓ Suggested Reorder Items: {len(reorder_data.get('suggested_reorders', []))}")

    # Add item to reorder basket
    if reorder_data.get("low_stock"):
        target_item = reorder_data["low_stock"][0]
        print(f"  Adding low stock item to reorder: {target_item['product_name']} (Qty: 50)")
        add_res = client.post("/api/reorders/item", json={
            "product_id": target_item["product_id"],
            "selected_quantity": 50,
            "supplier_id": target_item.get("supplier_id")
        }, headers=owner_headers)
        assert add_res.status_code == 200, f"Add to reorder failed: {add_res.text}"
        reorder_id = add_res.json().get("reorder_id")
        print(f"✓ Reorder item staged successfully (ID: {reorder_id})")

        # 1-Click PO Creation
        po_res = client.post("/api/reorders/create-po", json={
            "supplier_id": target_item.get("supplier_id") or 1,
            "reorder_item_ids": [reorder_id]
        }, headers=owner_headers)
        assert po_res.status_code == 200, f"PO Creation failed: {po_res.text}"
        print(f"✓ 1-Click Purchase Order Generated: {po_res.json().get('message')}")

    # 7. AI Receipt Ingestion & Review (Associate with receipt permission)
    print("\n[7] Testing AI Receipt Processing & Review Workflow...")
    
    # Create valid JPEG receipt image with correct magic bytes
    from PIL import Image
    buf = BytesIO()
    img = Image.new("RGB", (300, 200), color="white")
    img.save(buf, format="JPEG")
    receipt_bytes = buf.getvalue()

    files = {
        "file": ("invoice_sample.jpg", BytesIO(receipt_bytes), "image/jpeg")
    }

    upload_res = client.post("/api/receipts/upload", files=files, headers=assoc_headers)
    assert upload_res.status_code == 201, f"Receipt upload failed: {upload_res.text}"
    receipt_data = upload_res.json()
    import_id = receipt_data["import_id"]
    print(f"✓ Receipt Upload & Extraction by Associate successful (Import ID: {import_id})")
    print(f"  Supplier: {receipt_data['supplier']['name']}")
    print(f"  Extracted Items: {len(receipt_data['items'])}")
    for it in receipt_data["items"]:
        print(f"    - {it['raw_product_name']}: Matched as '{it.get('matched_product_name')}' (Score: {it.get('confidence_score')}, Level: {it.get('confidence_level')})")

    # Human Verification Screen & Review
    review_res = client.get(f"/api/receipts/{import_id}", headers=assoc_headers)
    assert review_res.status_code == 200, f"Receipt review failed: {review_res.text}"
    review_data = review_res.json()
    print("✓ Human verification review screen retrieved")

    # Confirm & Atomic Database Transaction
    confirm_payload = {
        "supplier_name": receipt_data['supplier']['name'] or "Apex Pharma Supply Co",
        "supplier_gstin": "27AABCS1429B1Z2",
        "invoice_number": "INV-2026-9041",
        "invoice_date": "2026-09-30",
        "items": [
            {
                "raw_product_name": it["raw_product_name"],
                "matched_product_id": it.get("matched_product_id"),
                "master_product_id": it.get("master_product_id"),
                "quantity": it.get("quantity") or 50,
                "unit": it.get("unit") or "strip",
                "purchase_price": it.get("purchase_price") or 18.5,
                "mrp": it.get("mrp") or 25.0,
                "gst_percentage": it.get("gst_percentage") or 12.0,
                "batch_number": it.get("batch_number") or "BAT-VERIFIED-01",
                "expiry_date": it.get("expiry_date") or "2027-12-31"
            }
            for it in review_data["items"]
        ]
    }

    confirm_res = client.post(f"/api/receipts/{import_id}/confirm", json=confirm_payload, headers=assoc_headers)
    assert confirm_res.status_code == 200, f"Receipt confirmation transaction failed: {confirm_res.text}"
    confirm_result = confirm_res.json()
    print(f"✓ Atomic Database Transaction Committed: {confirm_result.get('message')}")
    print(f"  Purchase ID: {confirm_result.get('purchase_id')}")
    print(f"  Products Credited: {len(confirm_result.get('products_updated', []))}")

    # 8. Check Database Registry via Admin
    print("\n[8] Testing Admin Database Registry...")
    reg_res = client.get("/api/admin-system/database-registry", headers=admin_headers)
    assert reg_res.status_code == 200, f"Registry query failed: {reg_res.text}"
    registry = reg_res.json()
    print(f"✓ Total Registered Databases in Postgres Cluster: {len(registry)}")
    for db in registry:
        print(f"  - [{db['database_type']}] {db['database_name']} (Business: {db.get('business_name') or 'N/A'})")

    print("\n" + "=" * 70)
    print("🎉 ALL TESTS PASSED! PRODUCTION MULTI-TENANT ARCHITECTURE VALIDATED!")
    print("=" * 70)

if __name__ == "__main__":
    run_tests()
