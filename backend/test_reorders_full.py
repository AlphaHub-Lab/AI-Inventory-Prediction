import io
import csv
from fastapi.testclient import TestClient
from app.main import app

def test_full_reorder_workflow():
    with TestClient(app) as client:
        # 1. Login as business owner
        print("1. Logging in as owner...", flush=True)
        login_res = client.post("/api/auth/login", json={"email": "Amogh@gmail.com", "password": "Owner123!"})
        assert login_res.status_code == 200, f"Login failed: {login_res.text}"
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Test overview with expired_stock & low_stock auto-sync
        print("2. Testing Reorder Overview...", flush=True)
        ov_res = client.get("/api/reorders/overview", headers=headers)
        assert ov_res.status_code == 200, f"Overview failed: {ov_res.text}"
        data = ov_res.json()
        assert "low_stock" in data
        assert "expired_stock" in data
        assert "pending_reorders" in data
        print(f"   -> Found {len(data['low_stock'])} low stock items")
        print(f"   -> Found {len(data['expired_stock'])} expired stock items")
        print(f"   -> Found {len(data['pending_reorders'])} pending reorder items")

        # 3. Test CSV Export
        print("3. Testing CSV Export...", flush=True)
        csv_res = client.get("/api/reorders/export-csv", headers=headers)
        assert csv_res.status_code == 200, f"CSV export failed: {csv_res.text}"
        assert "text/csv" in csv_res.headers.get("content-type", "")
        csv_text = csv_res.text
        assert "Product Name" in csv_text and "Barcode" in csv_text
        print(f"   -> CSV Export succeeded ({len(csv_text.splitlines())} lines)")

        # 4. Test Catalog Search for manual add
        print("4. Testing Catalog Search...", flush=True)
        search_res = client.get("/api/reorders/catalog-search?q=a", headers=headers)
        assert search_res.status_code == 200, f"Catalog search failed: {search_res.text}"
        catalog_items = search_res.json()
        print(f"   -> Found {len(catalog_items)} matching items in catalog")
        assert len(catalog_items) > 0, "No catalog items found"
        test_product = catalog_items[0]

        # 5. Test Manual Add to Reorder List
        print(f"5. Testing Manual Add for '{test_product['product_name']}'...", flush=True)
        add_res = client.post("/api/reorders/item", json={
            "product_id": test_product["product_id"],
            "suggested_quantity": 25.0,
            "selected_quantity": 30.0,
            "source": "manual",
            "reason": "Test manual addition by store manager"
        }, headers=headers)
        assert add_res.status_code == 200, f"Manual add failed: {add_res.text}"
        reorder_id = add_res.json().get("reorder_id")
        print(f"   -> Added reorder item ID: {reorder_id}")

        # 6. Test Physical Stock Receiving into Local Stock
        print("6. Testing Physical Stock Receiving into Local Stock...", flush=True)
        initial_stock = test_product["current_stock"]
        receive_qty = 15.0
        recv_res = client.post("/api/reorders/receive", json={
            "items": [{
                "reorder_id": reorder_id,
                "product_id": test_product["product_id"],
                "received_quantity": receive_qty,
                "batch_number": "LOT-TEST-999",
                "serial_number": "SN-TEST-888",
                "expiry_date": "2027-12-31",
                "purchase_price": 45.0,
                "note": "Verified arrival at loading dock"
            }],
            "general_note": "Physical inspection passed"
        }, headers=headers)
        assert recv_res.status_code == 200, f"Stock receiving failed: {recv_res.text}"
        recv_data = recv_res.json()
        assert recv_data["status"] == "success"
        print(f"   -> Received {recv_data['received_count']} items ({recv_data['total_units']} units)")

        # Verify stock was increased
        verify_res = client.get("/api/reorders/catalog-search?q=" + test_product["product_name"][:4], headers=headers)
        assert verify_res.status_code == 200
        updated_prod = next((p for p in verify_res.json() if p["product_id"] == test_product["product_id"]), None)
        assert updated_prod is not None
        assert updated_prod["current_stock"] == initial_stock + receive_qty, f"Expected {initial_stock + receive_qty}, got {updated_prod['current_stock']}"
        print(f"   -> Stock accurately updated from {initial_stock} to {updated_prod['current_stock']}")

        # 7. Test Wholesaler CSV Document Ingestion
        print("7. Testing Wholesaler Document Ingestion (CSV format with Barcode & S/N)...", flush=True)
        wholesaler_csv = (
            "Product Name,Quantity,Unit Price,Barcode,Serial Number,Batch Number,Expiry Date\n"
            f"{test_product['product_name']},50,42.50,BAR-WH-12345,SN-WH-9999,LOT-WH-2026,2028-06-30\n"
            "Wholesaler Special Item,20,15.00,8901234567890,SN-SPEC-001,LOT-SPEC-1,2027-01-15\n"
        ).encode('utf-8')

        upload_res = client.post(
            "/api/reorders/upload-wholesaler",
            files={"file": ("wholesaler_order.csv", wholesaler_csv, "text/csv")},
            headers=headers
        )
        assert upload_res.status_code == 200, f"Wholesaler upload failed: {upload_res.text}"
        up_data = upload_res.json()
        assert up_data["status"] == "success"
        assert len(up_data["items"]) == 2
        print(f"   -> Extracted {len(up_data['items'])} wholesaler items with Barcodes and Serials")

        # 8. Test Wholesaler Stock Confirmation directly into stock
        print("8. Testing Confirm Wholesaler into Local Stock...", flush=True)
        conf_res = client.post("/api/reorders/confirm-wholesaler", json={
            "supplier_name": "Apex Wholesale Corp",
            "invoice_number": "INV-APEX-7788",
            "items": [{
                "product_id": test_product["product_id"],
                "product_name": test_product["product_name"],
                "quantity": 10.0,
                "barcode": "BAR-WH-12345",
                "serial_number": "SN-WH-9999",
                "batch_number": "LOT-WH-2026",
                "purchase_price": 42.50,
                "expiry_date": "2028-06-30"
            }]
        }, headers=headers)
        assert conf_res.status_code == 200, f"Wholesaler confirm failed: {conf_res.text}"
        conf_data = conf_res.json()
        assert conf_data["status"] == "success"
        print(f"   -> Wholesaler items successfully added to stock: {conf_data['message']}")

        print("\nALL REORDER & WHOLESALER INGESTION BACKEND TESTS PASSED!", flush=True)

if __name__ == "__main__":
    test_full_reorder_workflow()
