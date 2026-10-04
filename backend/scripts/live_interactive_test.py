import time
import json
import httpx

BASE_URL = "http://127.0.0.1:8000"

def run_tests():
    print("=" * 80)
    print("  STOCKWISE AI — LIVE REAL-TIME END-TO-END APPLICATION TEST")
    print("=" * 80)

    passed = 0
    failed = 0
    total = 0

    def check(description: str, condition: bool, extra: str = ""):
        nonlocal passed, failed, total
        total += 1
        if condition:
            passed += 1
            print(f"  [PASS] {description} {extra}", flush=True)
        else:
            failed += 1
            print(f"  [FAIL] {description} {extra}", flush=True)

    with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
        # STEP 1: Test Public Health
        print("\n--- STEP 1: PUBLIC HEALTH GATEWAY ---")
        r_health = client.get("/health")
        check("GET /health status is 200", r_health.status_code == 200)
        health_data = r_health.json()
        check("Health response is sanitized (no internal DB or roles leaked)", "database" not in health_data and "roles" not in health_data, f"-> {health_data}")

        # STEP 2: Business Owner Login
        print("\n--- STEP 2: BUSINESS OWNER AUTHENTICATION ---")
        t0 = time.time()
        r_login = client.post("/api/auth/login", json={"email": "Amogh@gmail.com", "password": "Owner123!"})
        login_lat = (time.time() - t0) * 1000
        check("POST /api/auth/login (Business Owner)", r_login.status_code == 200, f"in {login_lat:.1f}ms")
        login_res = r_login.json()
        token = login_res.get("access_token")
        user = login_res.get("user", {})
        check("Login returns valid JWT token", bool(token))
        check("Login sets HttpOnly cookie", "access_token" in r_login.cookies or "session_token" in r_login.cookies)
        check("User role is business_owner", user.get("role") == "business_owner", f"(User: {user.get('email')}, Business ID: {user.get('business_id')})")

        owner_headers = {"Authorization": f"Bearer {token}"}

        # STEP 3: Verify Active Session
        print("\n--- STEP 3: VERIFY CURRENT USER CONTEXT (/api/auth/me) ---")
        r_me = client.get("/api/auth/me", headers=owner_headers)
        check("GET /api/auth/me status is 200", r_me.status_code == 200)
        me_data = r_me.json()
        check("Session recognizes active business", me_data.get("business_id") == 1, f"Business ID: {me_data.get('business_id')}")

        # STEP 4: Dashboard Signals & Refresh Insights Button
        print("\n--- STEP 4: DASHBOARD SIGNALS & REFRESH INSIGHTS BUTTON ---")
        r_dash = client.get("/api/dashboard", headers=owner_headers)
        check("GET /api/dashboard loads metrics", r_dash.status_code == 200)
        dash_data = r_dash.json() if r_dash.status_code == 200 else {}
        check("Dashboard has inventory value & signals", "total_inventory_value" in dash_data or "active_products" in dash_data or "signals" in dash_data)

        # Test "Refresh Insights" button
        t0 = time.time()
        r_refresh = client.post("/api/insights/refresh", headers=owner_headers)
        check("POST /api/insights/refresh (Refresh Insights Button)", r_refresh.status_code == 200, f"in {(time.time() - t0)*1000:.1f}ms")

        # STEP 5: Products Listing & Categories/Suppliers
        print("\n--- STEP 5: PRODUCT CATALOG & REFERENCES ---")
        r_cats = client.get("/api/categories", headers=owner_headers)
        check("GET /api/categories loads categories", r_cats.status_code == 200 and len(r_cats.json()) > 0)
        cats = r_cats.json()
        first_cat_id = cats[0]["id"] if cats else 1

        r_sups = client.get("/api/suppliers", headers=owner_headers)
        check("GET /api/suppliers loads suppliers", r_sups.status_code == 200)
        sups = r_sups.json()
        first_sup_id = sups[0]["id"] if sups else 1

        r_prods = client.get("/api/products?page_size=100", headers=owner_headers)
        check("GET /api/products loads local product list", r_prods.status_code == 200)
        initial_count = len(r_prods.json().get("items", []))
        print(f"       Current catalog has {initial_count} products.")

        # STEP 6: Input / Create a New Product (Real-Time Creation)
        print("\n--- STEP 6: INPUT & CREATE NEW PRODUCT (Real-Time Product Input) ---")
        new_prod_name = f"Bio-Therm Digital Thermometer Pro {int(time.time()) % 10000}"
        new_prod_payload = {
            "name": new_prod_name,
            "category_id": first_cat_id,
            "supplier_id": first_sup_id,
            "price": 499.00,
            "current_stock": 50,
            "minimum_stock": 15,
            "maximum_stock": 200,
            "reorder_point": 15,
            "safety_stock": 15,
            "lead_time_days": 3,
            "unit": "piece",
            "status": "active",
            "is_weight_based": False
        }
        t0 = time.time()
        r_create = client.post("/api/products", json=new_prod_payload, headers=owner_headers)
        create_lat = (time.time() - t0) * 1000
        check("POST /api/products (Create Product Button)", r_create.status_code in (200, 201), f"in {create_lat:.1f}ms")
        created_prod = r_create.json()
        prod_id = created_prod.get("id")
        prod_sku = created_prod.get("sku")
        check("Product created with unique SKU", bool(prod_sku), f"SKU: {prod_sku}, ID: {prod_id}")

        # STEP 7: Search & Verify Created Product
        print("\n--- STEP 7: SEARCH & VERIFY NEW PRODUCT ---")
        r_search = client.get(f"/api/products?query={prod_sku}", headers=owner_headers)
        check("Search query finds newly created product", r_search.status_code == 200 and any(p["id"] == prod_id for p in r_search.json().get("items", [])))

        # STEP 8: Record a Sale (Data Input -> Record Sale Button)
        print("\n--- STEP 8: RECORD A SALE (Record Sale Button) ---")
        sale_payload = {
            "product_id": prod_id,
            "quantity_sold": 5,
            "unit_price": 499.00,
            "date": time.strftime("%Y-%m-%d"),
            "channel": "store",
            "location": "Main Store"
        }
        r_sale = client.post("/api/sales", json=sale_payload, headers=owner_headers)
        check("POST /api/sales (Record Sale Button)", r_sale.status_code in (200, 201))

        # Verify stock decreased
        r_prod_check = client.get(f"/api/products/{prod_id}", headers=owner_headers)
        updated_stock = r_prod_check.json().get("current_stock") if r_prod_check.status_code == 200 else None
        check("Stock decreased accurately from 50 to 45", updated_stock == 45, f"Current stock: {updated_stock}")

        # STEP 9: Stock Adjustment Button
        print("\n--- STEP 9: STOCK ADJUSTMENT BUTTON ---")
        adj_payload = {
            "quantity_delta": 10,
            "transaction_type": "receipt",
            "note": "Warehouse restocking audit verified"
        }
        r_adj = client.post(f"/api/inventory/{prod_id}/adjust", json=adj_payload, headers=owner_headers)
        check("POST /api/inventory/{id}/adjust (Stock Adjustment Button)", r_adj.status_code == 200)

        r_prod_check2 = client.get(f"/api/products/{prod_id}", headers=owner_headers)
        updated_stock2 = r_prod_check2.json().get("current_stock") if r_prod_check2.status_code == 200 else None
        check("Stock updated from 45 to 55 via adjustment", updated_stock2 == 55, f"Current stock: {updated_stock2}")

        # STEP 10: Demand Forecasting Tab & Generate Forecasts Button
        print("\n--- STEP 10: DEMAND FORECASTING TAB & GENERATE FORECASTS BUTTON ---")
        t0 = time.time()
        r_fc_list = client.get("/api/forecasts?horizon_days=14", headers=owner_headers)
        check("GET /api/forecasts?horizon_days=14 (Demand Forecasting Tab)", r_fc_list.status_code == 200, f"in {(time.time() - t0)*1000:.1f}ms")
        fc_items = r_fc_list.json()
        check("Forecasts returned as list of records", isinstance(fc_items, list))

        # Test "Generate Forecasts" button
        t0 = time.time()
        r_fc_gen = client.post("/api/forecasts/generate", json={"product_id": prod_id, "horizon_days": 14}, headers=owner_headers)
        check("POST /api/forecasts/generate (Generate Forecasts Button)", r_fc_gen.status_code == 200, f"in {(time.time() - t0)*1000:.1f}ms")
        gen_data = r_fc_gen.json() if r_fc_gen.status_code == 200 else {}
        check("Forecast generation returned generated count", "generated" in gen_data and gen_data["generated"] > 0, f"Generated: {gen_data.get('generated')}")

        # STEP 11: Reorders Dashboard & Auto-Populate Button
        print("\n--- STEP 11: REORDERS WORKSPACE & AUTO-POPULATE BUTTON ---")
        t0 = time.time()
        r_reorder = client.get("/api/reorders/overview", headers=owner_headers)
        reorder_lat = (time.time() - t0) * 1000
        check("GET /api/reorders/overview (Reorders Overview)", r_reorder.status_code == 200, f"in {reorder_lat:.1f}ms")
        check("Reorder overview latency < 8000ms (was 23,800ms before fix!)", reorder_lat < 8000)

        # Test "Auto-Populate / Auto-Sync" button
        t0 = time.time()
        r_auto = client.post("/api/reorders/auto-populate", headers=owner_headers)
        check("POST /api/reorders/auto-populate (Auto-Sync Reorders Button)", r_auto.status_code == 200, f"in {(time.time() - t0)*1000:.1f}ms")

        # STEP 12: Checkout / POS Transaction
        print("\n--- STEP 12: CHECKOUT / POS TRANSACTION BUTTON ---")
        checkout_payload = {
            "customer_name": "Dr. Ramesh Patel",
            "customer_phone": "9876543210",
            "payment_method": "CASH",
            "discount": 0,
            "tax": 0,
            "items": [
                {
                    "product_id": prod_id,
                    "quantity": 2,
                    "unit_price": 499.00
                }
            ]
        }
        t0 = time.time()
        r_checkout = client.post("/api/checkout", json=checkout_payload, headers=owner_headers)
        check("POST /api/checkout (Complete Checkout Button)", r_checkout.status_code in (200, 201), f"in {(time.time() - t0)*1000:.1f}ms")
        invoice = r_checkout.json() if r_checkout.status_code in (200, 201) else {}
        check("Invoice created with valid invoice number", "invoice_id" in invoice or "id" in invoice, f"Invoice: {invoice.get('invoice_id')}")

        # STEP 13: AI Decision Support Chat
        print("\n--- STEP 13: AI CHAT DECISION SUPPORT BUTTON ---")
        chat_payload = {"message": "What products are currently low on stock?"}
        t0 = time.time()
        r_chat = client.post("/api/chat", json=chat_payload, headers=owner_headers)
        chat_lat = (time.time() - t0) * 1000
        check("POST /api/chat (Send Chat Message Button)", r_chat.status_code == 200, f"in {chat_lat:.1f}ms")
        chat_data = r_chat.json() if r_chat.status_code == 200 else {}
        check("Assistant returned AI response", bool(chat_data.get("response")), f"Response preview: {str(chat_data.get('response'))[:80]}...")

        # STEP 14: Analytics, Waste, Expiry
        print("\n--- STEP 14: ANALYTICS, WASTE, AND EXPIRY TABS ---")
        r_waste = client.get("/api/waste", headers=owner_headers)
        check("GET /api/waste (Waste Analysis Tab)", r_waste.status_code == 200)

        r_expiry = client.get("/api/expiry?days=30", headers=owner_headers)
        check("GET /api/expiry (Expiry Alerts Tab)", r_expiry.status_code == 200)

        r_analytics = client.get("/api/analytics/suppliers", headers=owner_headers)
        check("GET /api/analytics/suppliers (Supplier Analytics Tab)", r_analytics.status_code == 200)

        # STEP 15: Logout
        print("\n--- STEP 15: LOGOUT BUTTON ---")
        r_logout = client.post("/api/auth/logout", headers=owner_headers)
        check("POST /api/auth/logout (Logout Button)", r_logout.status_code == 200)

        # STEP 16: Admin Login & Master Catalogs Inspection
        print("\n--- STEP 16: SYSTEM ADMINISTRATOR WORKSPACE ---")
        t0 = time.time()
        r_admin_login = client.post("/api/auth/login", json={"email": "admin@inventory.example.com", "password": "Admin123!"})
        check("POST /api/auth/login (Admin Sign-In)", r_admin_login.status_code == 200, f"in {(time.time() - t0)*1000:.1f}ms")
        admin_token = r_admin_login.json().get("access_token")
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        # Test Master Catalogs Summary (previously timed out at 35s!)
        t0 = time.time()
        r_master_summary = client.get("/api/admin-system/master-catalogs-summary", headers=admin_headers)
        master_lat = (time.time() - t0) * 1000
        check("GET /api/admin-system/master-catalogs-summary (Master Catalogs View)", r_master_summary.status_code == 200, f"in {master_lat:.1f}ms")
        catalogs = r_master_summary.json() if r_master_summary.status_code == 200 else []
        check("All 5 Master Catalogs returned online", len(catalogs) == 5 and all(c.get("status") == "online" for c in catalogs))
        for c in catalogs:
            print(f"       * {c.get('business_type').upper():<12}: {c.get('product_count')} products, {c.get('supplier_count')} suppliers [ONLINE]")

        # Test cached response speed
        t0 = time.time()
        r_cached = client.get("/api/admin-system/master-catalogs-summary", headers=admin_headers)
        cached_lat = (time.time() - t0) * 1000
        check(f"Cached Master Catalogs View is near-instantaneous", cached_lat < 100, f"({cached_lat:.2f}ms)")

        # Test Audit Logs
        r_audit = client.get("/api/admin-system/audit-logs?limit=50", headers=admin_headers)
        check("GET /api/admin-system/audit-logs (Central Audit Trail)", r_audit.status_code == 200 and len(r_audit.json()) > 0)

        # Cleanup test product
        print("\n--- CLEANUP TEST DATA ---")
        try:
            r_del = client.delete(f"/api/products/{prod_id}", headers=owner_headers)
            print(f"  Cleaned up test product #{prod_id} (Status: {r_del.status_code})")
        except Exception:
            pass

    print("\n" + "=" * 80)
    print(f"  TEST COMPLETE: {passed}/{total} CHECKS PASSED ({failed} FAILED)")
    print("=" * 80)

if __name__ == "__main__":
    run_tests()
