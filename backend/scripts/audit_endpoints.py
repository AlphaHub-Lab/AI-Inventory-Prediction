import requests

s = requests.Session()
login = s.post('http://127.0.0.1:8000/api/auth/login', json={'email':'admin@inventory.example.com','password':'Admin123!'})
print('Login status:', login.status_code)
assert login.status_code == 200, f"Login failed: {login.text}"

endpoints = [
    # Core Application & Operations
    '/api/auth/me',
    '/api/admin/overview',
    '/api/products',
    '/api/categories',
    '/api/inventory/transactions',
    '/api/sales',
    '/api/forecasts',
    '/api/waste',
    '/api/reorders',
    '/api/purchase-orders',
    '/api/suppliers',
    '/api/analytics/suppliers',
    '/api/knowledge',
    '/api/models/runs',
    '/api/users',
    # Universal Reorders
    '/api/reorders/overview',
    '/api/reorders/catalog-search?q=bandage',
    # Receipts Ingestion
    '/api/receipts',
    # 38-Table Database System
    '/api/inventory-system/status',
    '/api/inventory-system/roles',
    '/api/inventory-system/permissions',
    '/api/inventory-system/users',
    '/api/inventory-system/sessions',
    '/api/inventory-system/business-types',
    '/api/inventory-system/businesses',
    '/api/inventory-system/master-catalog',
    '/api/inventory-system/business-products',
    '/api/inventory-system/suppliers',
    '/api/inventory-system/customers',
    '/api/inventory-system/inventory/batches',
    '/api/inventory-system/inventory/transactions',
    '/api/inventory-system/purchases',
    '/api/inventory-system/sales',
    '/api/inventory-system/ai/recommendations',
    '/api/inventory-system/reorders',
    '/api/inventory-system/receipt-imports',
    '/api/inventory-system/audit-logs',
    '/api/inventory-system/system-settings'
]

success = 0
failed = 0
for ep in endpoints:
    try:
        r = s.get('http://127.0.0.1:8000' + ep, timeout=30)
        print(f'{ep:45} : {r.status_code}')
        if r.status_code == 200:
            success += 1
        else:
            failed += 1
            print('   Error payload:', r.text[:160])
    except Exception as e:
        failed += 1
        print(f'{ep:45} : EXCEPTION ({e})')

print(f"\n=======================================================")
print(f"AUDIT COMPLETE: {success} succeeded, {failed} failed out of {len(endpoints)} endpoints.")
print(f"=======================================================")
