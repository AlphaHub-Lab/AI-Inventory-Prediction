import time
import json
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime

BASE_URL = "http://127.0.0.1:8000"
FRONTEND_URL = "http://localhost:5173"

def request_json(method, path, data=None, headers=None):
    url = f"{BASE_URL}{path}"
    headers = headers or {}
    req_data = None
    if data is not None:
        req_data = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    
    req = urllib.request.Request(url, data=req_data, headers=headers, method=method)
    start_time = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            elapsed = (time.perf_counter() - start_time) * 1000
            status = resp.status
            body = resp.read().decode("utf-8")
            try:
                parsed = json.loads(body)
            except Exception:
                parsed = body
            return {
                "status": status,
                "latency_ms": round(elapsed, 2),
                "data": parsed,
                "error": None
            }
    except urllib.error.HTTPError as exc:
        elapsed = (time.perf_counter() - start_time) * 1000
        body = exc.read().decode("utf-8")
        try:
            parsed = json.loads(body)
        except Exception:
            parsed = body
        return {
            "status": exc.code,
            "latency_ms": round(elapsed, 2),
            "data": parsed,
            "error": str(exc)
        }
    except Exception as exc:
        elapsed = (time.perf_counter() - start_time) * 1000
        return {
            "status": 0,
            "latency_ms": round(elapsed, 2),
            "data": None,
            "error": str(exc)
        }

def measure_frontend_latency():
    start_time = time.perf_counter()
    try:
        req = urllib.request.Request(FRONTEND_URL, headers={"User-Agent": "Bench"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            elapsed = (time.perf_counter() - start_time) * 1000
            return {"status": resp.status, "latency_ms": round(elapsed, 2)}
    except Exception as exc:
        return {"status": 0, "error": str(exc)}

def run_suite():
    results = {}
    print("=" * 70)
    print("LIVE RUNTIME ENDPOINT BENCHMARK & LATENCY AUDIT")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 70)

    # 1. Frontend Latency
    fe = measure_frontend_latency()
    print(f"[*] Frontend (Vite) status: {fe.get('status')}, Latency: {fe.get('latency_ms', 'N/A')} ms")
    results["frontend"] = fe

    # 2. Backend Health Latency
    health = request_json("GET", "/health")
    print(f"[*] Backend /health status: {health['status']}, Latency: {health['latency_ms']} ms")
    results["health"] = health

    # 3. Authentication Latencies
    # 3a. Admin
    admin_auth = request_json("POST", "/api/auth/login", {"email": "admin@inventory.example.com", "password": "Admin123!"})
    print(f"[*] Admin Login: Status {admin_auth['status']}, Latency: {admin_auth['latency_ms']} ms")
    results["admin_login"] = admin_auth
    admin_token = admin_auth.get("data", {}).get("access_token") if admin_auth["status"] == 200 else None
    admin_hdr = {"Authorization": f"Bearer {admin_token}"} if admin_token else {}

    # 3b. Owner
    owner_auth = request_json("POST", "/api/auth/login", {"email": "Amogh@gmail.com", "password": "Owner123!"})
    print(f"[*] Owner Login: Status {owner_auth['status']}, Latency: {owner_auth['latency_ms']} ms")
    results["owner_login"] = owner_auth
    owner_token = owner_auth.get("data", {}).get("access_token") if owner_auth["status"] == 200 else None
    owner_hdr = {"Authorization": f"Bearer {owner_token}"} if owner_token else {}

    # 3c. Associate
    assoc_auth = request_json("POST", "/api/auth/login", {"email": "sarah@skullmedicals.com", "password": "Staff123!"})
    print(f"[*] Associate Login: Status {assoc_auth['status']}, Latency: {assoc_auth['latency_ms']} ms")
    results["assoc_login"] = assoc_auth
    assoc_token = assoc_auth.get("data", {}).get("access_token") if assoc_auth["status"] == 200 else None
    assoc_hdr = {"Authorization": f"Bearer {assoc_token}"} if assoc_token else {}

    # 4. Auth Me Endpoint
    if owner_token:
        me = request_json("GET", "/api/auth/me", headers=owner_hdr)
        print(f"[*] /api/auth/me: Status {me['status']}, Latency: {me['latency_ms']} ms")
        results["auth_me"] = me

    # 5. Database Registry (Admin)
    if admin_token:
        reg = request_json("GET", "/api/admin-system/database-registry", headers=admin_hdr)
        print(f"[*] /api/admin-system/database-registry: Status {reg['status']}, Latency: {reg['latency_ms']} ms")
        results["database_registry"] = reg

        cat_summary = request_json("GET", "/api/admin-system/master-catalogs-summary", headers=admin_hdr)
        print(f"[*] /api/admin-system/master-catalogs-summary: Status {cat_summary['status']}, Latency: {cat_summary['latency_ms']} ms")
        results["master_catalogs_summary"] = cat_summary

    # 6. Reorders Overview (Owner)
    if owner_token:
        reorders = request_json("GET", "/api/reorders/overview", headers=owner_hdr)
        print(f"[*] /api/reorders/overview: Status {reorders['status']}, Latency: {reorders['latency_ms']} ms")
        results["reorders_overview"] = reorders

        # 7. Catalog Search
        cat_search = request_json("GET", "/api/catalog/search?q=Paracetamol", headers=owner_hdr)
        print(f"[*] /api/catalog/search: Status {cat_search['status']}, Latency: {cat_search['latency_ms']} ms")
        results["catalog_search"] = cat_search

        # 8. Dashboard
        dash = request_json("GET", "/api/dashboard", headers=owner_hdr)
        print(f"[*] /api/dashboard: Status {dash['status']}, Latency: {dash['latency_ms']} ms")
        results["dashboard"] = dash

        # 9. Products List
        prods = request_json("GET", "/api/products?page=1&page_size=10", headers=owner_hdr)
        print(f"[*] /api/products: Status {prods['status']}, Latency: {prods['latency_ms']} ms")
        results["products"] = prods

        # 10. Forecasts
        fc = request_json("GET", "/api/forecasts?horizon_days=7", headers=owner_hdr)
        print(f"[*] /api/forecasts: Status {fc['status']}, Latency: {fc['latency_ms']} ms")
        results["forecasts"] = fc

        # 11. Waste Predictions
        waste = request_json("GET", "/api/waste", headers=owner_hdr)
        print(f"[*] /api/waste: Status {waste['status']}, Latency: {waste['latency_ms']} ms")
        results["waste"] = waste

        # 12. Expiry Alerts
        exp = request_json("GET", "/api/expiry", headers=owner_hdr)
        print(f"[*] /api/expiry: Status {exp['status']}, Latency: {exp['latency_ms']} ms")
        results["expiry"] = exp

        # 13. Receipts list
        receipts = request_json("GET", "/api/receipts", headers=owner_hdr)
        print(f"[*] /api/receipts: Status {receipts['status']}, Latency: {receipts['latency_ms']} ms")
        results["receipts"] = receipts

        # 14. Chatbot Endpoint
        chat = request_json("POST", "/api/chat", {"message": "Which products are low on stock?"}, headers=owner_hdr)
        print(f"[*] /api/chat: Status {chat['status']}, Latency: {chat['latency_ms']} ms")
        results["chat"] = chat

    # 15. Associate Security Boundary Check
    if assoc_token:
        assoc_chat = request_json("POST", "/api/chat", {"message": "Hello"}, headers=assoc_hdr)
        print(f"[*] Associate /api/chat (RBAC enforcement): Status {assoc_chat['status']} (Expected 403), Latency: {assoc_chat['latency_ms']} ms")
        results["associate_chat_blocked"] = assoc_chat

    # 16. Rate limiting test
    print("[*] Testing Rate Limiter on /api/auth/login (burst test)...")
    burst_statuses = []
    for i in range(12):
        r = request_json("POST", "/api/auth/login", {"email": "invalid@test.com", "password": "wrong"})
        burst_statuses.append((r["status"], r["latency_ms"]))
    results["rate_limit_burst"] = burst_statuses
    print(f"    Burst results: {[s[0] for s in burst_statuses]}")

    with open("scripts/live_latency_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print("\n[+] Detailed latency results saved to scripts/live_latency_results.json")

if __name__ == "__main__":
    run_suite()
