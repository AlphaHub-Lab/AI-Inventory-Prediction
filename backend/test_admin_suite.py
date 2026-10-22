from fastapi.testclient import TestClient
from app.main import app
import json

client = TestClient(app)

print("--- 1. Testing Admin Login ---")
login_res = client.post("/api/auth/login", json={"email": "admin@inventory.example.com", "password": "Admin123!"})
assert login_res.status_code == 200, f"Login failed: {login_res.text}"
token = login_res.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}
print("Admin login success. Token obtained.")

print("\n--- 2. Testing /api/auth/me ---")
me_res = client.get("/api/auth/me", headers=headers)
assert me_res.status_code == 200, f"/api/auth/me failed: {me_res.text}"
user_me = me_res.json()
print("Current user:", user_me["email"], "Role:", user_me["role"], "Business ID:", user_me["business_id"])

print("\n--- 3. Testing Admin Dashboard APIs ---")
dash_res = client.get("/api/admin/dashboard", headers=headers)
print("Dashboard status:", dash_res.status_code)
assert dash_res.status_code == 200, f"Dashboard failed: {dash_res.text}"
dash_data = dash_res.json()
print("Dashboard KPIs:", dash_data.get("kpis"))
print("Businesses count:", len(dash_data.get("businesses", [])))

overview_res = client.get("/api/admin/overview", headers=headers)
print("Overview status:", overview_res.status_code)
assert overview_res.status_code == 200, f"Overview failed: {overview_res.text}"
ov_data = overview_res.json()
print("Overview engine:", ov_data.get("database_engine"), "active_accounts:", ov_data.get("active_accounts"))

accounts_res = client.get("/api/admin/accounts", headers=headers)
print("Accounts status:", accounts_res.status_code)
assert accounts_res.status_code == 200, f"Accounts failed: {accounts_res.text}"
print("Accounts count:", len(accounts_res.json()))

biz_res = client.get("/api/admin/businesses", headers=headers)
print("Businesses status:", biz_res.status_code)
assert biz_res.status_code == 200, f"Businesses failed: {biz_res.text}"
print("Businesses list count:", len(biz_res.json()))

notif_res = client.get("/api/admin/notifications", headers=headers)
print("Notifications status:", notif_res.status_code)
assert notif_res.status_code == 200, f"Notifications failed: {notif_res.text}"

act_res = client.get("/api/admin/activity?limit=50", headers=headers)
print("Activity status:", act_res.status_code)
assert act_res.status_code == 200, f"Activity failed: {act_res.text}"
print("Activity events:", len(act_res.json()))

print("\n--- 4. Testing Admin System APIs ---")
cat_res = client.get("/api/admin-system/master-catalogs-summary", headers=headers)
print("Master Catalogs Summary status:", cat_res.status_code)
assert cat_res.status_code == 200, f"Catalogs summary failed: {cat_res.text}"

audit_res = client.get("/api/admin-system/audit-logs", headers=headers)
print("Audit logs status:", audit_res.status_code)
assert audit_res.status_code == 200, f"Audit logs failed: {audit_res.text}"
print("Audit logs count:", len(audit_res.json()))

reg_res = client.get("/api/admin-system/database-registry", headers=headers)
print("Registry status:", reg_res.status_code)
assert reg_res.status_code == 200, f"Registry failed: {reg_res.text}"
print("Registry items:", len(reg_res.json()))

print("\n--- 5. Testing Business Creation Flow (Email code -> Verify -> Create -> Update -> Delete) ---")
import time
ts = int(time.time())
test_personal_email = f"testowner_{ts}@example.com"

# Request code
code_res = client.post("/api/admin/businesses/owner-email-code", json={"email": test_personal_email}, headers=headers)
print("Owner email code status:", code_res.status_code)
assert code_res.status_code == 200, f"Owner email code failed: {code_res.text}"
code_data = code_res.json()
dev_code = code_data.get("dev_code")
print("Obtained dev_code:", dev_code)

# Verify code
ver_res = client.post("/api/admin/businesses/verify-owner-email", json={"email": test_personal_email, "code": dev_code}, headers=headers)
print("Verify code status:", ver_res.status_code)
assert ver_res.status_code == 200, f"Verify code failed: {ver_res.text}"

# Create business
new_biz_payload = {
    "name": f"Automated Test Pharmacy {ts}",
    "business_type": "medical",
    "owner_name": "Test Owner",
    "owner_email": f"testowner_{ts}@example.com",
    "owner_personal_email": test_personal_email,
    "owner_phone": "+91-99999-88888",
    "phone": "+91-11-223344",
    "address": "456 Healthcare Blvd",
    "email_verification_code": dev_code,
    "owner_password": "OwnerPassword123!"
}
create_biz_res = client.post("/api/admin/businesses", json=new_biz_payload, headers=headers)
print("Create business status:", create_biz_res.status_code)
assert create_biz_res.status_code in [200, 201], f"Create business failed: {create_biz_res.text}"
created_biz = create_biz_res.json()
print("Created business:", created_biz)
created_biz_id = created_biz["id"]

# Toggle / Update business
update_biz_res = client.put(f"/api/admin/businesses/{created_biz_id}", json={"is_active": False, "business_type": "grocery"}, headers=headers)
print("Update business status:", update_biz_res.status_code)
assert update_biz_res.status_code == 200, f"Update business failed: {update_biz_res.text}"

# Delete business
del_biz_res = client.delete(f"/api/admin/businesses/{created_biz_id}", headers=headers)
print("Delete business status:", del_biz_res.status_code)
assert del_biz_res.status_code == 200, f"Delete business failed: {del_biz_res.text}"

print("\n--- ALL ADMIN SUITE TESTS PASSED COMPLETELY! ---")
