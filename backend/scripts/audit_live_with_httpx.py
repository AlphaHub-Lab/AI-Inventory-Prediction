import time
import json
import httpx
from datetime import datetime

BASE_URL = "http://127.0.0.1:8000"
FRONTEND_URL = "http://localhost:5173"

def run_audit():
    print("=" * 70, flush=True)
    print("      STOCKWISE AI - LIVE PRODUCTION RUNTIME AUDIT & BENCHMARK", flush=True)
    print("=" * 70, flush=True)

    results = {}

    with httpx.Client(base_url=BASE_URL, timeout=35.0) as client:
        # 1. Frontend Latency Test
        print("\n--- 1. FRONTEND SERVER LATENCY (VITE) ---", flush=True)
        try:
            fe_client = httpx.Client(timeout=5.0)
            t0 = time.perf_counter()
            r_fe = fe_client.get(FRONTEND_URL)
            fe_lat = (time.perf_counter() - t0) * 1000
            print(f"  [GET] {FRONTEND_URL} -> HTTP {r_fe.status_code} in {fe_lat:.2f} ms", flush=True)
            results["frontend"] = {"status": r_fe.status_code, "latency_ms": round(fe_lat, 2)}
        except Exception as e:
            print(f"  [GET] {FRONTEND_URL} -> FAILED: {e}", flush=True)
            results["frontend"] = {"error": str(e)}

        # 2. Health & Gateway Latency
        print("\n--- 2. SYSTEM HEALTH & LATENCY ---", flush=True)
        t0 = time.perf_counter()
        r_health = client.get("/health")
        lat = (time.perf_counter() - t0) * 1000
        print(f"  [GET] /health -> HTTP {r_health.status_code} in {lat:.2f} ms", flush=True)
        print(f"        Payload: {r_health.json()}", flush=True)
        results["health"] = {"status": r_health.status_code, "latency_ms": round(lat, 2), "data": r_health.json()}

        # 3. Authentication Latencies
        print("\n--- 3. AUTHENTICATION & SESSION LATENCY ---", flush=True)
        
        # 3a. Admin
        t0 = time.perf_counter()
        r_admin = client.post("/api/auth/login", json={"email": "admin@inventory.example.com", "password": "Admin123!"})
        admin_lat = (time.perf_counter() - t0) * 1000
        print(f"  [POST] /api/auth/login (Admin) -> HTTP {r_admin.status_code} in {admin_lat:.2f} ms", flush=True)
        admin_token = r_admin.json().get("access_token") if r_admin.status_code == 200 else None
        results["login_admin"] = {"status": r_admin.status_code, "latency_ms": round(admin_lat, 2)}

        # 3b. Business Owner
        t0 = time.perf_counter()
        r_owner = client.post("/api/auth/login", json={"email": "Amogh@gmail.com", "password": "Owner123!"})
        owner_lat = (time.perf_counter() - t0) * 1000
        print(f"  [POST] /api/auth/login (Owner) -> HTTP {r_owner.status_code} in {owner_lat:.2f} ms", flush=True)
        owner_token = r_owner.json().get("access_token") if r_owner.status_code == 200 else None
        results["login_owner"] = {"status": r_owner.status_code, "latency_ms": round(owner_lat, 2)}

        # 3c. Associate
        t0 = time.perf_counter()
        r_assoc = client.post("/api/auth/login", json={"email": "sarah@skullmedicals.com", "password": "Staff123!"})
        assoc_lat = (time.perf_counter() - t0) * 1000
        print(f"  [POST] /api/auth/login (Associate) -> HTTP {r_assoc.status_code} in {assoc_lat:.2f} ms", flush=True)
        assoc_token = r_assoc.json().get("access_token") if r_assoc.status_code == 200 else None
        results["login_associate"] = {"status": r_assoc.status_code, "latency_ms": round(assoc_lat, 2)}

        # 4. Identity & RBAC Verification
        print("\n--- 4. USER IDENTITY & AUTHORIZATION CHECKS ---", flush=True)
        for name, token in [("Admin", admin_token), ("Owner", owner_token), ("Associate", assoc_token)]:
            if token:
                t0 = time.perf_counter()
                r_me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
                lat = (time.perf_counter() - t0) * 1000
                me_data = r_me.json()
                print(f"  [GET] /api/auth/me ({name}) -> HTTP {r_me.status_code} in {lat:.2f} ms | Role: {me_data.get('role')}, Biz: {me_data.get('business_id')}", flush=True)
                results[f"me_{name.lower()}"] = {"status": r_me.status_code, "latency_ms": round(lat, 2), "data": me_data}

        # 5. Core Operational Endpoints (Owner Token)
        owner_hdr = {"Authorization": f"Bearer {owner_token}"} if owner_token else {}
        admin_hdr = {"Authorization": f"Bearer {admin_token}"} if admin_token else {}
        assoc_hdr = {"Authorization": f"Bearer {assoc_token}"} if assoc_token else {}

        print("\n--- 5. CORE API ENDPOINTS & LATENCY BENCHMARK ---", flush=True)
        endpoints = [
            ("Products List", "GET", "/api/products?page=1&page_size=10", owner_hdr),
            ("Categories List", "GET", "/api/categories", owner_hdr),
            ("Suppliers List", "GET", "/api/suppliers", owner_hdr),
            ("Inventory Batches", "GET", "/api/inventory/batches", owner_hdr),
            ("Inventory Transactions", "GET", "/api/inventory/transactions", owner_hdr),
            ("Sales History", "GET", "/api/sales", owner_hdr),
            ("Analytics Dashboard", "GET", "/api/dashboard", owner_hdr),
            ("Supplier Analytics", "GET", "/api/analytics/suppliers", owner_hdr),
            ("Expiry Alerts", "GET", "/api/expiry", owner_hdr),
            ("Waste Predictions", "GET", "/api/waste", owner_hdr),
            ("Forecasts", "GET", "/api/forecasts?horizon_days=7", owner_hdr),
            ("Reorder List", "GET", "/api/reorders", owner_hdr),
            ("Reorders Overview", "GET", "/api/reorders/overview", owner_hdr),
            ("Purchase Orders", "GET", "/api/purchase-orders", owner_hdr),
            ("Receipts List", "GET", "/api/receipts", owner_hdr),
            ("Knowledge Docs", "GET", "/api/knowledge", owner_hdr),
            ("Model Runs", "GET", "/api/models/runs", owner_hdr),
            ("Users List (Admin)", "GET", "/api/users", admin_hdr),
            ("Admin DB Registry", "GET", "/api/admin-system/database-registry", admin_hdr),
            ("Master Catalog Summary", "GET", "/api/admin-system/master-catalogs-summary", admin_hdr),
            ("Catalog Search (Medical)", "GET", "/api/catalog/search?q=Paracetamol", owner_hdr),
        ]

        endpoint_latencies = []
        for label, method, path, headers in endpoints:
            t0 = time.perf_counter()
            try:
                r = client.request(method, path, headers=headers)
                lat = (time.perf_counter() - t0) * 1000
                endpoint_latencies.append(lat)
                status_mark = "OK" if r.status_code == 200 else f"ERR {r.status_code}"
                print(f"  [{method}] {path:<42} [{status_mark}] {lat:7.2f} ms", flush=True)
                results[label] = {"method": method, "path": path, "status": r.status_code, "latency_ms": round(lat, 2)}
            except Exception as e:
                lat = (time.perf_counter() - t0) * 1000
                print(f"  [{method}] {path:<42} [FAIL] {lat:7.2f} ms -> {e}", flush=True)
                results[label] = {"method": method, "path": path, "status": 0, "latency_ms": round(lat, 2), "error": str(e)}

        # 6. Chatbot Benchmark (Owner vs Associate)
        print("\n--- 6. AI CHATBOT & RBAC SECURITY BOUNDARY ---", flush=True)
        # Owner Chat
        t0 = time.perf_counter()
        r_chat_owner = client.post("/api/chat", json={"message": "Which products are below their reorder point?"}, headers=owner_hdr)
        chat_owner_lat = (time.perf_counter() - t0) * 1000
        print(f"  [POST] /api/chat (Owner): HTTP {r_chat_owner.status_code} in {chat_owner_lat:.2f} ms", flush=True)
        if r_chat_owner.status_code == 200:
            cdata = r_chat_owner.json()
            print(f"         Intent: {cdata.get('intent')}, Grounded response preview: {cdata.get('response', '')[:100]}...", flush=True)
        results["chat_owner"] = {"status": r_chat_owner.status_code, "latency_ms": round(chat_owner_lat, 2)}

        # Associate Chat (Must be 403 Forbidden)
        t0 = time.perf_counter()
        r_chat_assoc = client.post("/api/chat", json={"message": "What is our stock status?"}, headers=assoc_hdr)
        chat_assoc_lat = (time.perf_counter() - t0) * 1000
        print(f"  [POST] /api/chat (Associate): HTTP {r_chat_assoc.status_code} in {chat_assoc_lat:.2f} ms (Expected 403)", flush=True)
        results["chat_associate_rbac"] = {"status": r_chat_assoc.status_code, "latency_ms": round(chat_assoc_lat, 2), "blocked": r_chat_assoc.status_code == 403}

        # 7. Latency Summary Statistics
        if endpoint_latencies:
            min_lat = min(endpoint_latencies)
            max_lat = max(endpoint_latencies)
            mean_lat = sum(endpoint_latencies) / len(endpoint_latencies)
            sorted_lat = sorted(endpoint_latencies)
            p95_idx = int(len(sorted_lat) * 0.95)
            p95_lat = sorted_lat[p95_idx] if p95_idx < len(sorted_lat) else max_lat
            print("\n" + "=" * 70, flush=True)
            print("LATENCY SUMMARY (Cross-Region Supabase DB Engine):", flush=True)
            print(f"  Fastest Endpoint:   {min_lat:.2f} ms", flush=True)
            print(f"  Average (Mean):     {mean_lat:.2f} ms", flush=True)
            print(f"  95th Percentile:    {p95_lat:.2f} ms", flush=True)
            print(f"  Slowest Endpoint:   {max_lat:.2f} ms", flush=True)
            print("=" * 70, flush=True)
            results["latency_stats"] = {
                "min_ms": round(min_lat, 2),
                "mean_ms": round(mean_lat, 2),
                "p95_ms": round(p95_lat, 2),
                "max_ms": round(max_lat, 2)
            }

    with open("scripts/live_audit_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print("\n[✓] Audit report data saved to scripts/live_audit_results.json", flush=True)

if __name__ == "__main__":
    run_audit()
