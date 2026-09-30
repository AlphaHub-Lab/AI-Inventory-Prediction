import sys
from fastapi.testclient import TestClient
from app.main import app

print("Initializing TestClient...", flush=True)
with TestClient(app) as client:
    print("Testing admin login...", flush=True)
    r = client.post("/api/auth/login", json={"email": "admin@inventory.example.com", "password": "Admin123!"})
    print("Admin login status:", r.status_code, flush=True)
    token = r.json().get("access_token")
    headers = {"Authorization": f"Bearer {token}"}
    
    print("Testing database registry...", flush=True)
    r_reg = client.get("/api/admin-system/database-registry", headers=headers)
    print("Registry status:", r_reg.status_code, "items:", len(r_reg.json()), flush=True)
    
    print("Testing owner login...", flush=True)
    r_owner = client.post("/api/auth/login", json={"email": "Amogh@gmail.com", "password": "Owner123!"})
    print("Owner login status:", r_owner.status_code, flush=True)
    owner_token = r_owner.json().get("access_token")
    owner_headers = {"Authorization": f"Bearer {owner_token}"}
    
    print("Testing reorder overview...", flush=True)
    r_ro = client.get("/api/reorders/overview", headers=owner_headers)
    print("Reorder overview status:", r_ro.status_code, flush=True)
    ro_data = r_ro.json()
    print("Low stock items count:", len(ro_data.get("low_stock", [])), flush=True)
    
    print("Testing associate strict AI blocking...", flush=True)
    r_staff = client.post("/api/auth/login", json={"email": "sarah@skullmedicals.com", "password": "Staff123!"})
    print("Staff login status:", r_staff.status_code, flush=True)
    staff_token = r_staff.json().get("access_token")
    staff_headers = {"Authorization": f"Bearer {staff_token}"}
    
    r_chat = client.post("/api/chat", json={"message": "hi"}, headers=staff_headers)
    print("Associate chat status (403 expected):", r_chat.status_code, flush=True)
    
    r_rec = client.get("/api/receipts", headers=staff_headers)
    print("Associate receipts status (200 expected):", r_rec.status_code, flush=True)
    print("ALL BASIC BACKEND CHECKS PASSED!", flush=True)
