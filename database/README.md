# Multi-Store Inventory Database — Supabase PostgreSQL

> Production-grade database architecture for a multi-store inventory and business management platform
> supporting **Grocery**, **Medical**, **Food**, and **Stationery** stores.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Schema Map](#schema-map)
- [Setup Instructions](#setup-instructions)
- [Migration Files](#migration-files)
- [Core Tables](#core-tables)
- [Business Logic Functions](#business-logic-functions)
- [Search Architecture](#search-architecture)
- [Purchase Order Workflow](#purchase-order-workflow)
- [Master → Local Import](#master--local-import)
- [Inventory Transactions](#inventory-transactions)
- [Expiry Management](#expiry-management)
- [Waste Management](#waste-management)
- [Row Level Security (RLS)](#row-level-security)
- [Seed Data](#seed-data)
- [Example Queries](#example-queries)
- [API Mapping](#api-mapping)
- [Business Rules](#business-rules)
- [AI/Analytics Compatibility](#aianalytics-compatibility)
- [Assumptions & Limitations](#assumptions--limitations)

---

## Architecture Overview

```
                    SUPABASE POSTGRESQL (single database)
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
     GROCERY            MEDICAL             FOOD
        │                  │                  │
   ┌────┴────┐        ┌────┴────┐        ┌────┴────┐
   │         │        │         │        │         │
 LOCAL     MASTER    LOCAL     MASTER    LOCAL    MASTER
   │         │        │         │        │         │
   └────┬────┘        └────┬────┘        └────┬────┘
        │                  │                  │
        └──────────────────┼──────────────────┘
                           │
                     STATIONERY
                           │
                      ┌────┴────┐
                      │         │
                    LOCAL     MASTER

+ public schema:
  ├── stores
  ├── store_memberships
  └── audit_log
```

Eight logical databases are implemented as **PostgreSQL schemas** inside one Supabase database:

| Schema | Purpose |
|---|---|
| `grocery_master` | Global grocery product catalog |
| `grocery_local` | Per-store grocery inventory, POs, transactions |
| `medical_master` | Global pharmacy product catalog + medical details |
| `medical_local` | Per-store pharmacy inventory + batch medical details |
| `food_master` | Global food product catalog + food details |
| `food_local` | Per-store food inventory + batch food details |
| `stationery_master` | Global stationery product catalog + stationery details |
| `stationery_local` | Per-store stationery inventory |

---

## Schema Map

```
public
├── stores                    — Registered businesses/shops
├── store_memberships         — User ↔ Store authorization (RLS boundary)
└── audit_log                 — System-wide audit trail

{type}_master (grocery, medical, food, stationery)
├── suppliers                 — Wholesaler directory
├── products                  — Product catalog (SKU, barcode, pricing, GST)
├── product_suppliers         — M:N product ↔ supplier mapping
├── medical_product_details   — (medical only) Generic name, dosage, strength
├── food_product_details      — (food only) Food type, storage, best-before
└── stationery_product_details — (stationery only) Color, size, material

{type}_local
├── suppliers                 — Store-scoped suppliers (with store_id)
├── inventory_items           — Per-store products (linked to master_product_id)
├── inventory_batches         — Batch-level quantities + expiry dates
├── inventory_stock           — VIEW: aggregated current_stock, available_stock
├── inventory_transactions    — Immutable stock change history
├── purchase_orders           — PO headers with lifecycle status
├── purchase_order_items      — PO line items with received tracking
├── waste_records             — Waste/spoilage/damage records
├── medical_batch_details     — (medical only) Per-batch regulatory info
├── food_batch_details        — (food only) Per-batch best-before, storage
├── expiring_batches          — VIEW: batches by expiry urgency
└── low_stock_items           — VIEW: items at/below reorder level
```

---

## Setup Instructions

### Prerequisites

- Supabase project (or any PostgreSQL 14+ instance)
- `psycopg2-binary` Python package (for the migration runner)
- Or access to the Supabase SQL Editor

### Option 1: Migration Runner Script

```bash
# 1. Install dependency
pip install psycopg2-binary

# 2. Copy and configure environment
cp .env.example .env
# Edit .env and set DATABASE_URL

# 3. Run migrations only
python database/run_migrations.py

# 4. Run migrations + seed data
python database/run_migrations.py --seed

# 5. Preview what would run
python database/run_migrations.py --dry-run --seed
```

### Option 2: Supabase SQL Editor

Run each file in order from the Supabase Dashboard → SQL Editor:

1. `database/migrations/001_create_schemas.sql`
2. `database/migrations/002_create_suppliers.sql`
3. `database/migrations/003_create_master_products.sql`
4. `database/migrations/004_create_local_inventory.sql`
5. `database/migrations/005_create_inventory_transactions.sql`
6. `database/migrations/006_create_purchase_orders.sql`
7. `database/migrations/007_create_waste_management.sql`
8. `database/migrations/008_create_functions.sql`
9. `database/migrations/009_create_search_functions.sql`
10. `database/migrations/010_enterprise_standards.sql`

Then optionally run seed data:

1. `database/seeds/001_seed_grocery.sql`
2. `database/seeds/002_seed_medical.sql`
3. `database/seeds/003_seed_food.sql`
4. `database/seeds/004_seed_stationery.sql`

### Option 3: psql CLI

```bash
psql "$DATABASE_URL" -f database/migrations/001_create_schemas.sql
psql "$DATABASE_URL" -f database/migrations/002_create_suppliers.sql
# ... (continue in order)
```

### Post-Setup: Create a Store

```sql
-- Create a store
INSERT INTO public.stores (store_name, business_type, address, city, state, pincode)
VALUES ('My Kirana Shop', 'grocery', '123 Main Road', 'Mumbai', 'Maharashtra', '400001')
RETURNING id;

-- Assign a user to the store (use the store ID from above)
INSERT INTO public.store_memberships (store_id, user_id, role)
VALUES ('<store_id>', '<auth_user_id>', 'owner');
```

---

## Migration Files

| File | Description |
|---|---|
| `001_create_schemas.sql` | Creates 8 schemas, `stores`, `store_memberships`, `audit_log`, business_type enum, RLS |
| `002_create_suppliers.sql` | Creates `suppliers` table in all 8 schemas (local = store-scoped, master = catalog) |
| `003_create_master_products.sql` | Creates `products`, `product_suppliers` in master schemas + type-specific extensions |
| `004_create_local_inventory.sql` | Creates `inventory_items`, `inventory_batches`, `inventory_stock` view in local schemas |
| `005_create_inventory_transactions.sql` | Creates immutable `inventory_transactions` tables |
| `006_create_purchase_orders.sql` | Creates `purchase_orders` + `purchase_order_items` with full lifecycle |
| `007_create_waste_management.sql` | Creates `waste_records` for spoilage/damage tracking |
| `008_create_functions.sql` | Atomic business logic: receive_purchase_order, sell_stock, import_from_master, record_waste, adjust_stock |
| `009_create_search_functions.sql` | Search functions, expiring_batches view, low_stock_items view |

---

## Core Tables

### Products (Master)

```
id, sku (UNIQUE), barcode, product_name, brand, category, subcategory,
description, unit, pack_size, mrp, default_cost_price, default_selling_price,
gst_percentage, supplier_id, is_active, created_at, updated_at
```

### Inventory Items (Local)

```
id, store_id, master_product_id (FK→master.products), sku, barcode,
product_name, brand, category, subcategory, reserved_stock, reorder_level,
minimum_stock, maximum_stock, cost_price, selling_price, mrp, gst_percentage,
supplier_id, storage_location, stock_status, created_at, updated_at

UNIQUE(store_id, sku), UNIQUE(store_id, master_product_id)
```

### Inventory Batches (Local)

```
id, item_id (FK→inventory_items), batch_number, manufacturing_date,
expiry_date, quantity, created_at

UNIQUE(item_id, batch_number, expiry_date)
```

**Key design**: `current_stock` is calculated by summing batch quantities, not stored as a single field. This enables precise batch-level expiry and FEFO tracking.

---

## Business Logic Functions

All functions are `SECURITY DEFINER` with `SET search_path = pg_catalog, public` for safety. They verify store membership, use `FOR UPDATE` row locking, and write audit logs.

| Function | Purpose |
|---|---|
| `{schema}.receive_purchase_order(...)` | Atomically receive stock from a PO line |
| `{schema}.sell_stock(...)` | FEFO deduction from non-expired batches |
| `{schema}.import_from_master(...)` | Add/update local inventory from master catalog |
| `{schema}.record_waste(...)` | Write off waste with transaction record |
| `{schema}.adjust_stock(...)` | Manual stock adjustment with audit trail |
| `{schema}.search_local(...)` | Search store's local inventory |
| `{schema}.search_catalog(...)` | Search master product catalog |

---

## Search Architecture

```
Seller searches "Parle biscuits"
        │
        ▼
Step 1: Search LOCAL inventory
        │
   ┌────┴────┐
   │         │
  Found    Not Found
   │         │
   ▼         ▼
Show stock  Step 2: Search MASTER catalog
   │         │
   │         ▼
   │    Show matching products
   │    (name, brand, SKU, category, pack size, MRP, supplier)
   │         │
   │         ▼
   │    Import to Local / Create PO
```

**Search supports:** Exact SKU, barcode, product name (partial), brand, category, full-text search via GIN index.

```sql
-- Local search
SELECT * FROM grocery_local.search_local(:store_id, 'Parle');

-- Master search
SELECT * FROM grocery_master.search_catalog('basmati rice');
```

---

## Purchase Order Workflow

```
Seller searches → Not in Local → Found in Master
        │
        ▼
Select product from Master
        │
        ▼
Import to Local inventory (0 stock)
        │
        ▼
Select supplier + enter quantity
        │
        ▼
Create Purchase Order (PENDING)
        │
        ▼
Supplier confirms → (CONFIRMED)
        │
        ▼
Goods dispatched → (SHIPPED)
        │
        ▼
Seller receives goods
        │
        ▼
Call receive_purchase_order() → ATOMICALLY:
  1. Verify PO status
  2. Check quantity limits
  3. Create/update batch
  4. Update PO line (quantity_received)
  5. Update PO status (RECEIVED or PARTIALLY_RECEIVED)
  6. Update inventory item stock_status
  7. Create inventory transaction
  8. Write audit log
        │
        ▼
Stock available for sale
```

**PO Status Lifecycle:**
```
DRAFT → PENDING → CONFIRMED → SHIPPED → RECEIVED
                                      → PARTIALLY_RECEIVED
Any state → CANCELLED
```

---

## Master → Local Import

```sql
-- Import with initial stock
SELECT grocery_local.import_from_master(
  p_store_id           := :store_id,
  p_master_product_id  := :master_product_id,
  p_quantity           := 50,
  p_cost_price         := 380.00,
  p_selling_price      := 420.00,
  p_batch_number       := 'LOT-2026-09',
  p_expiry_date        := '2027-09-01'
);
```

**Rules:**
- If product already exists in local → **updates** (no duplicate)
- If quantity > 0 → creates batch, creates transaction, updates stock status
- If quantity = 0 → just adds to local catalog (OUT_OF_STOCK)

---

## Inventory Transactions

Every stock change creates an immutable transaction record:

| Type | When |
|---|---|
| `PURCHASE` | Stock received from PO or master import |
| `SALE` | Stock sold (FEFO deduction) |
| `RETURN` | Customer return |
| `DAMAGE` | Damaged goods write-off |
| `EXPIRED` | Expired goods write-off |
| `ADJUSTMENT` | Manual stock count correction |
| `TRANSFER_IN` | Stock transferred in from another location |
| `TRANSFER_OUT` | Stock transferred out |

Each record captures: `quantity_delta`, `previous_stock`, `new_stock`, `reference_id`, `created_by`.

---

## Expiry Management

```sql
-- View all expiring batches with urgency status
SELECT * FROM grocery_local.expiring_batches
WHERE store_id = :store_id;
```

| Status | Condition |
|---|---|
| `EXPIRED` | expiry_date < today |
| `EXPIRING_TODAY` | expiry_date = today |
| `EXPIRING_7_DAYS` | ≤ 7 days remaining |
| `EXPIRING_30_DAYS` | ≤ 30 days remaining |
| `EXPIRING_60_DAYS` | ≤ 60 days remaining |
| `OK` | > 60 days remaining |

**Medical products**: The `sell_stock()` function **refuses to sell expired batches**. It uses FEFO (First Expired, First Out) to deduct from earliest-expiring non-expired batches first.

---

## Waste Management

```sql
SELECT grocery_local.record_waste(
  p_store_id := :store_id,
  p_item_id  := :item_id,
  p_quantity := 10,
  p_reason   := 'EXPIRED',
  p_batch_id := :batch_id,
  p_notes    := 'Batch expired, removing from shelf'
);
```

**Reasons:** `EXPIRED`, `DAMAGED`, `SPOILED`, `RETURNED`, `OTHER`

Each waste record tracks `cost_loss` (quantity × cost_price) for analytics.

---

## Row Level Security

| Table | Policy |
|---|---|
| `public.stores` | Users see only stores they belong to |
| `public.store_memberships` | Users see only their own memberships |
| `public.audit_log` | Users see audit entries for their stores |
| `*_local.inventory_items` | Scoped by `store_id` membership |
| `*_local.inventory_batches` | Scoped via parent item's store_id |
| `*_local.inventory_transactions` | Scoped by `store_id` membership |
| `*_local.purchase_orders` | Scoped by `store_id` membership |
| `*_local.purchase_order_items` | Scoped via parent PO's store_id |
| `*_local.suppliers` | Scoped by `store_id` membership |
| `*_local.waste_records` | Scoped by `store_id` membership |
| `*_master.products` | Read-only for authenticated (active products only) |
| `*_master.suppliers` | Read-only for authenticated (active suppliers only) |

**Seller A can ONLY access Store A's local inventory. Seller B cannot see Store A's data.**

---

## Seed Data

| File | Store Type | Products |
|---|---|---|
| `001_seed_grocery.sql` | Grocery | 126 products (Staples, Spices, Snacks, Beverages, Dairy, Oil, Personal Care, Household, Sauces) |
| `002_seed_medical.sql` | Medical | 110+ products (OTC, First Aid, Vitamins, Devices, Skin Care, Hygiene, Ayurvedic, Baby Care) |
| `003_seed_food.sql` | Food | 115 products (Raw, Packaged, Ready-to-Eat, Frozen, Bakery, Beverages, Dairy, Produce, Meat) |
| `004_seed_stationery.sql` | Stationery | 115 products (Writing, Paper/Notebooks, Files, Adhesives, Erasers, Office, Geometry, Art) |

All products use **realistic Indian brands**: Amul, Tata, Parle, Haldiram, Everest, MDH, Classmate, Camlin, Faber-Castell, etc.

Each store type includes 5 supplier records.

> **Note:** Medical seed data is illustrative catalog information only. Prescription schedules, drug compositions, and regulatory classifications should not be used for actual pharmaceutical compliance.

---

## Example Queries

See `database/queries/example_queries.sql` for complete working examples:

1. Search local inventory (by name, SKU, barcode)
2. Search master catalog (full-text)
3. Find products missing from local
4. Import product from master to local
5. Create purchase order
6. Receive stock (atomic)
7. Sell stock (FEFO)
8. Low stock report
9. Expiring products report
10. Inventory transaction history
11. Out of stock report
12. Stock adjustments
13. Waste recording
14. PO lifecycle queries
15. Medical-specific queries
16. Audit log queries
17. AI/analytics-ready aggregation queries

---

## API Mapping

| Endpoint | Method | Description |
|---|---|---|
| `/products/local` | GET | Search local inventory |
| `/products/master` | GET | Search master catalog |
| `/products/search` | GET | Unified search (local → master fallback) |
| `/products/:sku` | GET | Get product by SKU |
| `/purchase-orders` | POST | Create purchase order |
| `/purchase-orders` | GET | List purchase orders |
| `/purchase-orders/:id` | GET | Get PO details |
| `/purchase-orders/:id/receive` | POST | Receive stock from PO |
| `/inventory/adjust` | POST | Manual stock adjustment |
| `/inventory/transactions` | GET | Transaction history |
| `/inventory/low-stock` | GET | Low stock items |
| `/inventory/expiring` | GET | Expiring batches |
| `/inventory/out-of-stock` | GET | Out of stock items |

---

## Business Rules

| # | Rule |
|---|---|
| 1 | A product can exist in Master without existing in Local |
| 2 | A product cannot be sold from Local if available stock is zero |
| 3 | Receiving stock increases Local inventory |
| 4 | Receiving stock MUST create an inventory transaction |
| 5 | Duplicate products must not be created in Local (UNIQUE on store_id + master_product_id) |
| 6 | If a product already exists in Local, received stock increases quantity |
| 7 | Medical products with expired batches must not be sold (enforced by sell_stock) |
| 8 | Expiry tracked at batch level |
| 9 | Every inventory modification is auditable (audit_log + inventory_transactions) |
| 10 | Purchase orders maintain complete lifecycle |

---

## AI/Analytics Compatibility

The schema stores clean historical data for ML consumption:

| Use Case | Data Source |
|---|---|
| Demand forecasting | `inventory_transactions` (daily SALE aggregates) |
| Reorder prediction | `inventory_stock` + transaction history |
| Safety stock calculation | Transaction velocity + lead time data |
| Expiry prediction | `inventory_batches.expiry_date` + sales velocity |
| Waste prediction | `waste_records` (reason, quantity, cost_loss) |
| Sales forecasting | Transaction history + seasonal patterns |
| Supplier analysis | `purchase_orders` (delivery times, amounts) |
| Inventory optimization | Stock levels + reorder_level + turnover |

---

## SKU System

Store-specific prefixes ensure unique identification:

```
GRO-RICE-000001    (Grocery)
MED-PARA-000001    (Medical)
FOOD-MILK-000001   (Food)
STA-PEN-000001     (Stationery)
```

---

## Database Relationships

```
public.stores ←──── public.store_memberships ────→ auth.users
      │
      ├── {type}_local.inventory_items ────→ {type}_master.products
      │         │
      │         ├── inventory_batches
      │         │         │
      │         │         └── medical_batch_details (medical only)
      │         │         └── food_batch_details (food only)
      │         │
      │         └── inventory_transactions
      │
      ├── {type}_local.purchase_orders
      │         │
      │         └── purchase_order_items ────→ inventory_items
      │
      ├── {type}_local.waste_records ────→ inventory_items
      │
      └── {type}_local.suppliers

{type}_master.products
      │
      ├── product_suppliers ────→ suppliers
      │
      ├── medical_product_details (medical only)
      ├── food_product_details (food only)
      └── stationery_product_details (stationery only)
```

---

## Assumptions & Limitations

1. **Eight schemas are logical namespaces** in one PostgreSQL database, not separate database instances.
2. **`store_type` in `public.stores`** maps to exactly one pair of schemas; the backend selects the correct schema based on the store's type.
3. **Batch rows are the source of truth** for current stock. The `inventory_stock` view calculates `current_stock` by summing batches; `reserved_stock` is subtracted for availability.
4. **Medical seed data is illustrative only** — it does not assert prescription status, drug schedules, or clinical/regulatory facts.
5. **RLS membership assignment** is an administrative operation (service_role). Ordinary authenticated clients use SECURITY DEFINER RPCs.
6. **Catalog/supplier maintenance** in master schemas requires service_role. Authenticated users have read-only access.
7. **The sell_stock function** enforces FEFO and refuses expired batches but does not encode jurisdiction-specific medicine compliance rules.
8. Migrations are designed for a **fresh Supabase PostgreSQL project**. Running against an existing production database requires careful review.
9. The `auth.users` reference requires Supabase Auth to be configured.
