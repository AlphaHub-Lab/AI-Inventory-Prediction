# Multi-store inventory database (Supabase PostgreSQL)

This database layer adds eight logical catalogs in one Supabase database: `grocery_master/local`, `medical_master/local`, `food_master/local`, and `stationery_master/local`. It is additive and does not modify the existing FastAPI application's `public.products` tables.

## Architecture

```text
Supabase PostgreSQL
├── grocery_master ── catalog, suppliers, product_suppliers
├── grocery_local  ── store inventory, batches, transactions, POs
├── medical_master ── catalog + medical_product_details
├── medical_local  ── store inventory + medical_batch_details
├── food_master    ── catalog + food_product_details
├── food_local     ── store inventory + food_batch_details
├── stationery_master ─ catalog + stationery_product_details
└── stationery_local  ─ store inventory, batches, transactions, POs

public.inventory_stores ──< public.inventory_store_memberships >── auth.users
```

Each local inventory item refers to its corresponding master product. Catalog records can exist without any local inventory row. A local item is unique by `(store_id, master_product_id)` and SKU. Batch quantities carry expiry/manufacturing dates; `inventory_stock` aggregates the batches. Purchase order lines track ordered and received quantities. Every receipt writes an immutable stock transaction.

## Migrations and seeding

Apply in numeric order from Supabase SQL Editor or `psql` using a trusted operator connection:

1. `database/migrations/001_store_memberships.sql`
2. `database/migrations/002_logical_store_schemas.sql`
3. `database/migrations/003_purchase_receiving.sql`
4. Optional demo catalog: `database/seeds/001_demo_catalog.sql`

The migration scripts are additive and use `CREATE ... IF NOT EXISTS` for the schemas and base membership objects. Do not run against production without first reviewing the SQL and taking the normal database backup. No destructive statements are included. Rerunning migration 002/003 is not guaranteed because named table constraints/policies are deliberately migration-managed; use Supabase migration history for repeatable deployment. Seed inserts are idempotent by SKU.

Provision each store in `public.inventory_stores` and assign its owner/staff in `public.inventory_store_memberships` from a trusted backend using a service role. Never expose the service-role key in the browser. Supabase API settings must expose the eight schemas if clients call them directly; the preferred setup is a backend API using authenticated user JWTs. Grant/RLS policies are provided for authenticated roles. Master catalog rows are readable to authenticated users; catalog writes belong to trusted catalog administrators.

## Environment

Copy `.env.example` to `.env`, set `DATABASE_URL` to the Supabase connection string from your secret manager/dashboard and keep `.env` out of Git. The supplied credential is not copied into the repository. Use Supabase's pooled connection endpoint for serverless workloads where appropriate. Rotate any credential that has been pasted into an untrusted location. Use `postgresql+psycopg://...` for SQLAlchemy.

## Core structures

All four master schemas have:

- `suppliers`: wholesaler identity/contact and payment details.
- `products`: UUID PK, unique SKU, barcode, product naming/category, unit/pack, MRP/prices/GST, default supplier, active flag and timestamps.
- `product_suppliers`: many-to-many supplier offers, cost, supplier SKU, lead time and preferred flag.

Each local schema has:

- `suppliers`: store-scoped wholesaler records.
- `products`: local schema catalog metadata (catalog access is normally through the master schema).
- `inventory_items`: store-scoped product and pricing/reorder/location settings; optional link to master product.
- `inventory_batches`: on-hand batch quantity and dates.
- `inventory_stock`: aggregate current and available stock view.
- `inventory_transactions`: quantity delta and before/after audit history.
- `purchase_orders`, `purchase_order_items`: full status lifecycle and partial receiving quantities.
- Medical batch details (storage/regulatory attributes entered by the business); food batch details (best-before/storage attributes).

RLS policies scope local rows to a `store_id` membership for `auth.uid()`. The API must still enforce role/status transitions and ensure business flows use a signed-in user's JWT. Backend service-role operations bypass RLS and must perform explicit store authorization. Expired batches are excluded by the audited FEFO sale RPC; the database does not encode jurisdictional medicine compliance rules.

## Typical flow

1. Search local `*_local.inventory_stock` by name/SKU/barcode. If absent, search `*_master.products` and `product_suppliers`.
2. Create one local `inventory_items` row linked to the master UUID (upsert on `(store_id, master_product_id)`), and create a PO plus PO line in one transaction.
3. On receipt, call `schema.receive_purchase_order(order_id, line_id, quantity, batch, mfg_date, expiry_date, location)`. The security-definer routine checks the caller membership, locks the PO and line, rejects over-receipt/invalid status, increments/creates the batch, updates PO lifecycle and writes a `PURCHASE` transaction atomically.
4. Sales should call `schema.sell_stock(store_id,item_id,quantity,note)`. It locks the item, allocates FEFO from non-expired batches, refuses insufficient/expired stock, and records stock deltas. Returns, damage, expiry write-offs and adjustments must update batches and append corresponding transaction rows in the same database transaction. Never directly edit batch quantity outside a controlled API/RPC.

## Example SQL

Replace `:store_id`, `:query`, and IDs with bound parameters from your application. `:query` examples are pseudocode placeholders for prepared statements.

```sql
-- Local stock search
SELECT sku, product_name, current_stock, available_stock, selling_price, stock_status
FROM grocery_local.inventory_stock
WHERE store_id = :store_id AND product_name ILIKE '%' || :query || '%'
ORDER BY product_name LIMIT 50;

-- Master search by name, SKU or barcode
SELECT id, sku, barcode, product_name, brand, category, pack_size, mrp, supplier_id
FROM grocery_master.products
WHERE is_active AND (product_name ILIKE '%' || :query || '%' OR sku ILIKE :query || '%'
  OR barcode = :query OR to_tsvector('simple',coalesce(product_name,'')||' '||coalesce(brand,'')||' '||coalesce(category,'')) @@ plainto_tsquery('simple',:query))
ORDER BY product_name LIMIT 50;

-- Catalog entries not yet in a store's local assortment
SELECT m.* FROM grocery_master.products m
WHERE m.is_active AND NOT EXISTS (
 SELECT 1 FROM grocery_local.inventory_items i WHERE i.store_id=:store_id AND i.master_product_id=m.id);

-- Create or reuse local item, then create a pending purchase order + line in one transaction
INSERT INTO grocery_local.inventory_items(store_id,master_product_id,sku,barcode,product_name,category,
 cost_price,selling_price,mrp,supplier_id,stock_status)
SELECT :store_id,p.id,p.sku,p.barcode,p.product_name,p.category,:cost,:price,p.mrp,:supplier,'OUT_OF_STOCK'
FROM grocery_master.products p WHERE p.id=:master_product_id
ON CONFLICT(store_id,master_product_id) DO UPDATE SET updated_at=now() RETURNING id;
INSERT INTO grocery_local.purchase_orders(store_id,supplier_id,status,expected_delivery_date,created_by)
VALUES(:store_id,:supplier,'PENDING',:expected_date,auth.uid()) RETURNING id;
INSERT INTO grocery_local.purchase_order_items(purchase_order_id,item_id,quantity_ordered,unit_cost)
VALUES(:po_id,:item_id,20,250.00);
UPDATE grocery_local.purchase_orders po SET total_amount=(SELECT sum(line_total) FROM grocery_local.purchase_order_items WHERE purchase_order_id=po.id)
WHERE po.id=:po_id;

-- Atomic receipt (20 units, batch and expiry tracked)
SELECT grocery_local.receive_purchase_order(:po_id,:line_id,20,'LOT-2026-09',CURRENT_DATE,CURRENT_DATE+365,'A-01');

-- Sell only available, non-expired stock (FEFO); all batch deductions are audited
SELECT grocery_local.sell_stock(:store_id,:item_id,2,'Invoice INV-1001');

-- Low stock, expiring batches, and SKU history
SELECT * FROM grocery_local.inventory_stock WHERE store_id=:store_id AND current_stock <= reorder_level;
SELECT i.sku,i.product_name,b.batch_number,b.quantity,b.expiry_date FROM grocery_local.inventory_items i
JOIN grocery_local.inventory_batches b ON b.item_id=i.id
WHERE i.store_id=:store_id AND b.quantity>0 AND b.expiry_date <= CURRENT_DATE + interval '30 days';
SELECT t.* FROM grocery_local.inventory_transactions t JOIN grocery_local.inventory_items i ON i.id=t.item_id
WHERE t.store_id=:store_id AND i.sku=:sku ORDER BY t.created_at DESC;
```

For other business types substitute the schema prefix. Use bound parameters rather than interpolating input. The receive function takes line UUID as its second argument.

## API mapping

Suggested backend endpoints: `GET /products/local`, `/products/master`, `/products/search`, `/products/{sku}`; `POST/GET /purchase-orders`, `GET /purchase-orders/{id}`, `POST /purchase-orders/{id}/receive`; `POST /inventory/adjust`; `GET /inventory/transactions`, `/inventory/low-stock`, `/inventory/expiring`, `/inventory/out-of-stock`. Determine the store from the authenticated membership, not a client-supplied store ID alone. Return no connection details/secrets.

## Assumptions and boundaries

- Eight schemas are logical namespaces in one PostgreSQL database, not separate database instances.
- `inventory_stores.store_type` enforces the four supported types; schema choice is fixed by the backend.
- Batch rows are the source of truth for current stock. The view calculates `current_stock`; reserved stock is subtracted for availability.
- Demo seed creates 100 sample catalog records per type. Medical entries are illustrative catalog labels only; they do not assert composition, prescription status, schedule, or clinical/regulatory facts.
- RLS membership assignment and catalog/supplier maintenance are administrative operations. Ordinary authenticated clients have read-only batch/transaction access and use security-definer receive/sale RPCs that verify store membership; service-role calls bypass RLS and require application-side store authorization. Review grants and policies against the exact Supabase API exposure before production.
- The migration revokes direct batch/transaction writes from authenticated clients. Trusted service-role or database-owner operations can still bypass audit workflows and must be tightly controlled.



