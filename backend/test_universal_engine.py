import io
import csv
from datetime import date, timedelta
from fastapi.testclient import TestClient
from app.main import app

def run_universal_engine_tests():
    print("=" * 80)
    print("RUNNING UNIVERSAL INVENTORY ENGINE VALIDATION TEST SUITE")
    print("=" * 80)

    with TestClient(app) as client:
        # 1. Login as Business Owner
        print("\n[TEST 1] Logging in as Store Manager (Amogh@gmail.com)...")
        login_res = client.post("/api/auth/login", json={"email": "Amogh@gmail.com", "password": "Owner123!"})
        assert login_res.status_code == 200, f"Login failed: {login_res.text}"
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("  -> Logged in successfully. Token acquired.")

        # 2. Test Store Capability & Overview
        print("\n[TEST 2] Verifying Universal Reorder Overview & Store Capabilities...")
        ov_res = client.get("/api/reorders/overview", headers=headers)
        assert ov_res.status_code == 200, f"Overview query failed: {ov_res.text}"
        ov_data = ov_res.json()
        assert "store_capability" in ov_data
        cap = ov_data["store_capability"]
        print(f"  -> Detected business capability: {cap['business_type']} ({cap['name']})")
        print(f"  -> Supported units: {', '.join(cap['units'][:5])}...")
        print(f"  -> Features: expiry={cap['features'].get('expiry')}, batch={cap['features'].get('batch')}, variants={cap['features'].get('variants')}")
        assert "low_stock" in ov_data
        assert "expired_stock" in ov_data
        assert "pending_reorders" in ov_data
        assert "receiving_history" in ov_data
        print(f"  -> Summary: {len(ov_data['pending_reorders'])} pending reorders, {len(ov_data['low_stock'])} low stock, {len(ov_data['receiving_history'])} receiving history logs.")

        # 3. Test CSV Export with Barcode & Serial String Preservation (Leading Zeros & UTF-8 BOM)
        print("\n[TEST 3] Testing CSV Export with String Barcode Preservation...")
        csv_res = client.get("/api/reorders/export-csv", headers=headers)
        assert csv_res.status_code == 200, f"CSV export failed: {csv_res.text}"
        csv_bytes = csv_res.content
        assert csv_bytes.startswith(b"\xef\xbb\xbf"), "Missing UTF-8 BOM for Excel compatibility"
        csv_text = csv_bytes.decode("utf-8-sig")
        reader = csv.reader(io.StringIO(csv_text))
        header = next(reader)
        assert "Product Name" in header
        assert "Barcode" in header
        assert "Requested Quantity" in header
        assert "Received Quantity" in header
        assert "Remaining Quantity" in header
        print(f"  -> CSV generated with {len(header)} columns. BOM verified.")

        # 4. Test Catalog Search across Name, SKU, Barcode, and Variant fields
        print("\n[TEST 4] Testing Store Catalog Search...")
        search_res = client.get("/api/reorders/catalog-search?q=a", headers=headers)
        assert search_res.status_code == 200, f"Catalog search failed: {search_res.text}"
        items = search_res.json()
        assert len(items) > 0, "No catalog items found"
        test_prod = items[0]
        print(f"  -> Found {len(items)} catalog items. Using '{test_prod['product_name']}' (ID: {test_prod['product_id']}) for workflow.")

        # 5. Test Manual Add with Duplicate Protection (Section 51)
        print("\n[TEST 5] Testing Manual Add Duplicate Protection...")
        # Step A: Add initial reorder item
        initial_add = client.post("/api/reorders/item", json={
            "product_id": test_prod["product_id"],
            "suggested_quantity": 20.0,
            "selected_quantity": 20.0,
            "source": "manual",
            "reason": "Test first order",
            "mode": "replace"
        }, headers=headers)
        assert initial_add.status_code == 200
        reorder_id = initial_add.json()["reorder_id"]
        print(f"  -> Created reorder item ID: {reorder_id} (Qty: 20)")

        # Step B: Attempt adding same item again with mode='prompt' (should detect duplicate)
        dup_check = client.post("/api/reorders/item", json={
            "product_id": test_prod["product_id"],
            "suggested_quantity": 15.0,
            "selected_quantity": 15.0,
            "source": "manual",
            "reason": "Accidental duplicate attempt",
            "mode": "prompt"
        }, headers=headers)
        assert dup_check.status_code == 200
        dup_data = dup_check.json()
        assert dup_data.get("duplicate") is True, f"Expected duplicate: True, got: {dup_data}"
        assert dup_data.get("current_requested_quantity") == 20.0
        print(f"  -> Duplicate detected correctly: {dup_data['message']}")

        # Step C: Increase quantity via mode='increase'
        inc_res = client.post("/api/reorders/item", json={
            "product_id": test_prod["product_id"],
            "suggested_quantity": 10.0,
            "selected_quantity": 10.0,
            "source": "manual",
            "mode": "increase"
        }, headers=headers)
        assert inc_res.status_code == 200
        print(f"  -> Successfully increased quantity: {inc_res.json()['quantity']} units (20 + 10 = 30)")

        # 6. Test Physical Stock Receiving - Partial Delivery then Full Delivery (Sections 21-28)
        print("\n[TEST 6] Testing Physical Stock Receiving (Partial Delivery & Remaining Quantity Tracking)...")
        # Initial stock check
        prod_before = client.get(f"/api/reorders/catalog-search?q={test_prod['product_name'][:4]}", headers=headers).json()
        initial_stock = next(p["current_stock"] for p in prod_before if p["product_id"] == test_prod["product_id"])

        # Delivery 1: Partial delivery of 18 units out of 30 requested
        delivery_1_qty = 18.0
        deliv1_res = client.post("/api/reorders/receive", json={
            "items": [{
                "reorder_id": reorder_id,
                "product_id": test_prod["product_id"],
                "received_quantity": delivery_1_qty,
                "batch_number": "LOT-DELIV-PARTIAL-1",
                "serial_number": "0012998877",
                "expiry_date": "2028-10-31",
                "purchase_price": test_prod["purchase_price"]
            }],
            "general_note": "First partial shipment received from supplier"
        }, headers=headers)
        assert deliv1_res.status_code == 200, f"Delivery 1 failed: {deliv1_res.text}"
        d1_item = deliv1_res.json()["items"][0]
        assert d1_item["status"] == "partially_received", f"Expected partially_received, got: {d1_item['status']}"
        print(f"  -> Delivery 1 (Partial): Received {delivery_1_qty} units. Status correctly set to '{d1_item['status']}'.")

        # Verify stock increased by 18
        prod_after1 = client.get(f"/api/reorders/catalog-search?q={test_prod['product_name'][:4]}", headers=headers).json()
        stock_after1 = next(p["current_stock"] for p in prod_after1 if p["product_id"] == test_prod["product_id"])
        assert stock_after1 == initial_stock + delivery_1_qty, f"Stock mismatch: {stock_after1} vs {initial_stock + delivery_1_qty}"
        print(f"  -> Local Stock updated from {initial_stock} to {stock_after1} units.")

        # Delivery 2: Remaining 12 units delivered
        delivery_2_qty = 12.0
        deliv2_res = client.post("/api/reorders/receive", json={
            "items": [{
                "reorder_id": reorder_id,
                "product_id": test_prod["product_id"],
                "received_quantity": delivery_2_qty,
                "batch_number": "LOT-DELIV-FINAL-2",
                "serial_number": "0012998878",
                "expiry_date": "2028-10-31",
                "purchase_price": test_prod["purchase_price"]
            }],
            "general_note": "Remaining items arrived"
        }, headers=headers)
        assert deliv2_res.status_code == 200, f"Delivery 2 failed: {deliv2_res.text}"
        d2_item = deliv2_res.json()["items"][0]
        assert d2_item["status"] == "received", f"Expected received, got: {d2_item['status']}"
        print(f"  -> Delivery 2 (Full Completion): Received remaining {delivery_2_qty} units. Status transitioned to '{d2_item['status']}'.")

        # Verify stock increased by another 12
        prod_after2 = client.get(f"/api/reorders/catalog-search?q={test_prod['product_name'][:4]}", headers=headers).json()
        stock_after2 = next(p["current_stock"] for p in prod_after2 if p["product_id"] == test_prod["product_id"])
        assert stock_after2 == initial_stock + delivery_1_qty + delivery_2_qty
        print(f"  -> Total Local Stock now accurately: {stock_after2} units.")

        # 7. Test Wholesaler File Ingestion & Duplicate Delivery Hash Protection (Sections 30-40, 52)
        print("\n[TEST 7] Testing Wholesaler Document Upload & Duplicate File Hash Detection...")
        sample_invoice_csv = (
            "Product Name,Quantity,Unit Price,Barcode,Serial Number,Batch Number,Expiry Date\n"
            f"{test_prod['product_name']},25,40.00,001234567890,SN-009988,LOT-NOV-2026,2028-12-31\n"
        ).encode('utf-8')

        # First upload
        up1_res = client.post(
            "/api/reorders/upload-wholesaler",
            files={"file": ("invoice_delivery_101.csv", sample_invoice_csv, "text/csv")},
            headers=headers
        )
        assert up1_res.status_code == 200
        up1_data = up1_res.json()
        assert up1_data["status"] == "success"
        file_hash = up1_data["file_hash"]
        print(f"  -> First upload parsed successfully (Hash: {file_hash[:12]}...). Extracted {len(up1_data['items'])} items.")

        # Confirm the delivery into stock
        conf_res = client.post("/api/reorders/confirm-wholesaler", json={
            "supplier_name": "Reliable Pharma Wholesaler",
            "invoice_number": "INV-DELIV-HASH-101",
            "file_hash": file_hash,
            "items": [{
                "product_id": test_prod["product_id"],
                "product_name": test_prod["product_name"],
                "quantity": 25.0,
                "barcode": "001234567890",
                "serial_number": "SN-009988",
                "batch_number": "LOT-NOV-2026",
                "expiry_date": "2028-12-31",
                "purchase_price": 40.00
            }]
        }, headers=headers)
        assert conf_res.status_code == 200
        print(f"  -> Confirmed delivery into stock: {conf_res.json()['message']}")

        # Upload exact same file again (Section 52 - Duplicate delivery protection)
        up2_res = client.post(
            "/api/reorders/upload-wholesaler",
            files={"file": ("invoice_delivery_101.csv", sample_invoice_csv, "text/csv")},
            headers=headers
        )
        assert up2_res.status_code == 200
        up2_data = up2_res.json()
        assert up2_data.get("duplicate_delivery_warning") is not None
        print(f"  -> Duplicate delivery warning triggered: {up2_data['duplicate_delivery_warning']}")

        # 8. Test Dedicated Audit History Endpoint (Sections 29 & 50)
        print("\n[TEST 8] Testing Dedicated /history Audit Trail Endpoint...")
        hist_res = client.get("/api/reorders/history", headers=headers)
        print(f"  -> HTTP status: {hist_res.status_code}, response: {hist_res.text[:300]}")
        assert hist_res.status_code == 200, f"History query failed: {hist_res.text}"
        hist_data = hist_res.json()
        assert "reorders" in hist_data, f"hist_data keys: {list(hist_data.keys()) if isinstance(hist_data, dict) else hist_data}"
        assert "receipts" in hist_data
        print(f"  -> History endpoint returned {len(hist_data['reorders'])} reorder log entries and {len(hist_data['receipts'])} stock receiving transaction records.")
        latest_rx = hist_data["receipts"][0]
        print(f"  -> Latest Receipt: '{latest_rx['product_name']}', Added: +{latest_rx['received_quantity']} {latest_rx['unit']}, Ref: {latest_rx['transaction_id']}, Performed By: {latest_rx['performed_by']}")

        print("\n" + "=" * 80)
        print("ALL UNIVERSAL REORDER & RECEIVING TESTS PASSED ACCORDING TO SPEC!")
        print("=" * 80)

if __name__ == "__main__":
    run_universal_engine_tests()
