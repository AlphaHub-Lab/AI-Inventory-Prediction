-- ============================================================================
-- EXAMPLE QUERIES: Complete workflow demonstrations
-- ============================================================================
-- Replace :store_id, :query, and UUIDs with actual values from your database.
-- These are parameterised query templates for a backend API.
-- ============================================================================


-- =====================================================================
-- 1. SEARCH LOCAL INVENTORY
-- =====================================================================

-- Search by product name (partial match)
SELECT sku, product_name, brand, current_stock, available_stock,
       selling_price, mrp, stock_status
FROM grocery_local.inventory_stock
WHERE store_id = :store_id
  AND product_name ILIKE '%' || :query || '%'
ORDER BY product_name
LIMIT 50;

-- Search by exact SKU
SELECT * FROM grocery_local.inventory_stock
WHERE store_id = :store_id AND sku = :sku;

-- Search by barcode
SELECT * FROM grocery_local.inventory_stock
WHERE store_id = :store_id AND barcode = :barcode;

-- Full-text search (name + brand + category)
SELECT * FROM grocery_local.search_local(:store_id, 'Parle biscuit');


-- =====================================================================
-- 2. SEARCH MASTER CATALOG
-- =====================================================================

-- Search master catalog by product name
SELECT id, sku, barcode, product_name, brand, category,
       pack_size, mrp, default_cost_price, default_selling_price
FROM grocery_master.products
WHERE is_active
  AND product_name ILIKE '%' || :query || '%'
ORDER BY product_name
LIMIT 50;

-- Using the search function
SELECT * FROM grocery_master.search_catalog('basmati rice');

-- Search with full-text GIN index
SELECT * FROM grocery_master.products
WHERE is_active
  AND to_tsvector('simple',
        coalesce(product_name, '') || ' ' ||
        coalesce(brand, '') || ' ' ||
        coalesce(category, '') || ' ' || sku
      ) @@ plainto_tsquery('simple', :query);


-- =====================================================================
-- 3. FIND PRODUCTS MISSING FROM LOCAL INVENTORY
-- =====================================================================

-- Master products NOT yet in this store's local inventory
SELECT m.id, m.sku, m.product_name, m.brand, m.category,
       m.pack_size, m.mrp, m.default_cost_price
FROM grocery_master.products m
WHERE m.is_active
  AND NOT EXISTS (
    SELECT 1 FROM grocery_local.inventory_items i
    WHERE i.store_id = :store_id
      AND i.master_product_id = m.id
  )
ORDER BY m.category, m.product_name;


-- =====================================================================
-- 4. IMPORT PRODUCT FROM MASTER TO LOCAL
-- =====================================================================

-- Option A: Import with initial stock
SELECT grocery_local.import_from_master(
  p_store_id           := :store_id,
  p_master_product_id  := :master_product_id,
  p_quantity           := 50,
  p_cost_price         := 380.00,
  p_selling_price      := 420.00,
  p_batch_number       := 'LOT-2026-09',
  p_manufacturing_date := '2026-08-15',
  p_expiry_date        := '2027-08-15',
  p_storage_location   := 'Aisle A, Shelf 3'
);

-- Option B: Import without stock (just add to catalog)
SELECT grocery_local.import_from_master(
  p_store_id           := :store_id,
  p_master_product_id  := :master_product_id
);


-- =====================================================================
-- 5. CREATE PURCHASE ORDER
-- =====================================================================

-- Step 1: Ensure local inventory item exists (via import or direct insert)
INSERT INTO grocery_local.inventory_items (
  store_id, master_product_id, sku, barcode, product_name,
  brand, category, cost_price, selling_price, mrp,
  supplier_id, stock_status
)
SELECT
  :store_id, p.id, p.sku, p.barcode, p.product_name,
  p.brand, p.category, :cost_price, :selling_price, p.mrp,
  :local_supplier_id, 'OUT_OF_STOCK'
FROM grocery_master.products p
WHERE p.id = :master_product_id
ON CONFLICT (store_id, master_product_id) DO UPDATE
  SET updated_at = now()
RETURNING id AS item_id;

-- Step 2: Create purchase order
INSERT INTO grocery_local.purchase_orders (
  store_id, supplier_id, status,
  expected_delivery_date, created_by
) VALUES (
  :store_id, :local_supplier_id, 'PENDING',
  CURRENT_DATE + 7, auth.uid()
) RETURNING id AS po_id;

-- Step 3: Add line items
INSERT INTO grocery_local.purchase_order_items (
  purchase_order_id, item_id, quantity_ordered, unit_cost
) VALUES (
  :po_id, :item_id, 20, 380.00
);

-- Step 4: Update PO total
UPDATE grocery_local.purchase_orders po
SET total_amount = (
  SELECT SUM(line_total)
  FROM grocery_local.purchase_order_items
  WHERE purchase_order_id = po.id
)
WHERE po.id = :po_id;


-- =====================================================================
-- 6. RECEIVE STOCK (ATOMIC)
-- =====================================================================

-- Receive 20 units from PO line, creating batch with expiry
SELECT grocery_local.receive_purchase_order(
  p_order_id           := :po_id,
  p_line_id            := :po_line_id,
  p_quantity           := 20,
  p_batch_number       := 'LOT-2026-09-A',
  p_manufacturing_date := '2026-09-01',
  p_expiry_date        := '2027-09-01',
  p_location           := 'Aisle A, Shelf 3'
);

-- Partial receipt (receive 10 out of 20)
SELECT grocery_local.receive_purchase_order(
  p_order_id := :po_id,
  p_line_id  := :po_line_id,
  p_quantity := 10,
  p_batch_number := 'LOT-2026-09-B'
);


-- =====================================================================
-- 7. SELL STOCK (FEFO)
-- =====================================================================

-- Sell 5 units using First-Expired-First-Out
SELECT grocery_local.sell_stock(
  p_store_id := :store_id,
  p_item_id  := :item_id,
  p_quantity := 5,
  p_note     := 'Invoice INV-2026-1001'
);


-- =====================================================================
-- 8. LOW STOCK REPORT
-- =====================================================================

-- Products at or below reorder level
SELECT sku, product_name, brand, current_stock, reorder_level,
       available_stock, stock_status, stock_alert
FROM grocery_local.low_stock_items
WHERE store_id = :store_id
ORDER BY current_stock ASC;

-- Alternative: custom query
SELECT s.sku, s.product_name, s.current_stock, s.reorder_level
FROM grocery_local.inventory_stock s
WHERE s.store_id = :store_id
  AND s.current_stock <= s.reorder_level
ORDER BY s.current_stock ASC;


-- =====================================================================
-- 9. EXPIRING PRODUCTS
-- =====================================================================

-- All expiry statuses
SELECT sku, product_name, batch_number, quantity,
       expiry_date, expiry_status, days_until_expiry
FROM grocery_local.expiring_batches
WHERE store_id = :store_id
ORDER BY expiry_date ASC;

-- Products expiring within 30 days
SELECT i.sku, i.product_name, b.batch_number, b.quantity,
       b.expiry_date,
       b.expiry_date - CURRENT_DATE AS days_remaining
FROM grocery_local.inventory_items i
JOIN grocery_local.inventory_batches b ON b.item_id = i.id
WHERE i.store_id = :store_id
  AND b.quantity > 0
  AND b.expiry_date IS NOT NULL
  AND b.expiry_date <= CURRENT_DATE + INTERVAL '30 days'
ORDER BY b.expiry_date ASC;

-- Already expired products
SELECT i.sku, i.product_name, b.batch_number, b.quantity, b.expiry_date
FROM grocery_local.inventory_items i
JOIN grocery_local.inventory_batches b ON b.item_id = i.id
WHERE i.store_id = :store_id
  AND b.quantity > 0
  AND b.expiry_date < CURRENT_DATE;


-- =====================================================================
-- 10. INVENTORY TRANSACTION HISTORY
-- =====================================================================

-- All transactions for a specific product
SELECT t.transaction_type, t.quantity_delta,
       t.previous_stock, t.new_stock,
       t.note, t.created_at
FROM grocery_local.inventory_transactions t
JOIN grocery_local.inventory_items i ON i.id = t.item_id
WHERE t.store_id = :store_id
  AND i.sku = :sku
ORDER BY t.created_at DESC;

-- Recent transactions across all products
SELECT i.sku, i.product_name, t.transaction_type,
       t.quantity_delta, t.new_stock, t.created_at
FROM grocery_local.inventory_transactions t
JOIN grocery_local.inventory_items i ON i.id = t.item_id
WHERE t.store_id = :store_id
ORDER BY t.created_at DESC
LIMIT 100;


-- =====================================================================
-- 11. OUT OF STOCK REPORT
-- =====================================================================

SELECT sku, product_name, brand, category
FROM grocery_local.inventory_stock
WHERE store_id = :store_id
  AND current_stock = 0
ORDER BY product_name;


-- =====================================================================
-- 12. STOCK ADJUSTMENT
-- =====================================================================

-- Positive adjustment (found extra stock during audit)
SELECT grocery_local.adjust_stock(
  p_store_id      := :store_id,
  p_item_id       := :item_id,
  p_quantity_delta := 5,
  p_reason         := 'Physical count correction - found extra units'
);

-- Negative adjustment (damage/loss)
SELECT grocery_local.adjust_stock(
  p_store_id      := :store_id,
  p_item_id       := :item_id,
  p_quantity_delta := -3,
  p_reason         := 'Damaged during handling'
);


-- =====================================================================
-- 13. WASTE RECORDING
-- =====================================================================

-- Record expired waste
SELECT grocery_local.record_waste(
  p_store_id := :store_id,
  p_item_id  := :item_id,
  p_quantity := 10,
  p_reason   := 'EXPIRED',
  p_batch_id := :batch_id,
  p_notes    := 'Batch expired on 2026-09-15'
);


-- =====================================================================
-- 14. PURCHASE ORDER LIFECYCLE
-- =====================================================================

-- List all POs for a store
SELECT po.id, po.order_number, po.status, po.order_date,
       po.expected_delivery_date, po.total_amount,
       s.supplier_name
FROM grocery_local.purchase_orders po
JOIN grocery_local.suppliers s ON s.id = po.supplier_id
WHERE po.store_id = :store_id
ORDER BY po.order_date DESC;

-- PO details with line items
SELECT poi.id AS line_id, i.sku, i.product_name,
       poi.quantity_ordered, poi.quantity_received,
       poi.unit_cost, poi.line_total,
       CASE
         WHEN poi.quantity_received = 0 THEN 'PENDING'
         WHEN poi.quantity_received < poi.quantity_ordered THEN 'PARTIAL'
         ELSE 'COMPLETE'
       END AS line_status
FROM grocery_local.purchase_order_items poi
JOIN grocery_local.inventory_items i ON i.id = poi.item_id
WHERE poi.purchase_order_id = :po_id;


-- =====================================================================
-- 15. MEDICAL-SPECIFIC QUERIES
-- =====================================================================

-- Search medical products with prescription info
SELECT p.*, d.generic_name, d.dosage_form, d.strength,
       d.manufacturer, d.prescription_required, d.schedule
FROM medical_master.products p
LEFT JOIN medical_master.medical_product_details d ON d.product_id = p.id
WHERE p.is_active
  AND p.product_name ILIKE '%paracetamol%';

-- Find prescription-required products
SELECT p.sku, p.product_name, d.generic_name,
       d.prescription_required, d.schedule
FROM medical_master.products p
JOIN medical_master.medical_product_details d ON d.product_id = p.id
WHERE d.prescription_required = TRUE;


-- =====================================================================
-- 16. AUDIT LOG QUERIES
-- =====================================================================

-- Recent audit events for a store
SELECT action, entity, entity_id, old_value, new_value, created_at
FROM public.audit_log
WHERE store_id = :store_id
ORDER BY created_at DESC
LIMIT 50;

-- All price changes
SELECT entity_id, old_value, new_value, created_at
FROM public.audit_log
WHERE store_id = :store_id
  AND action = 'PRICE_CHANGED'
ORDER BY created_at DESC;


-- =====================================================================
-- 17. ANALYTICS / AI-READY QUERIES
-- =====================================================================

-- Daily stock movement summary (for demand forecasting)
SELECT
  DATE(t.created_at) AS date,
  i.sku,
  i.product_name,
  i.category,
  SUM(CASE WHEN t.transaction_type = 'SALE' THEN ABS(t.quantity_delta) ELSE 0 END) AS units_sold,
  SUM(CASE WHEN t.transaction_type = 'PURCHASE' THEN t.quantity_delta ELSE 0 END) AS units_purchased,
  SUM(CASE WHEN t.transaction_type IN ('EXPIRED','DAMAGE') THEN ABS(t.quantity_delta) ELSE 0 END) AS units_wasted
FROM grocery_local.inventory_transactions t
JOIN grocery_local.inventory_items i ON i.id = t.item_id
WHERE t.store_id = :store_id
  AND t.created_at >= CURRENT_DATE - INTERVAL '90 days'
GROUP BY DATE(t.created_at), i.sku, i.product_name, i.category
ORDER BY date DESC, units_sold DESC;

-- Waste analysis by reason (for waste reduction AI)
SELECT
  reason,
  COUNT(*) AS incidents,
  SUM(quantity) AS total_quantity,
  SUM(cost_loss) AS total_cost_loss
FROM grocery_local.waste_records
WHERE store_id = :store_id
  AND created_at >= CURRENT_DATE - INTERVAL '90 days'
GROUP BY reason
ORDER BY total_cost_loss DESC;

-- Supplier performance (for supplier analysis)
SELECT
  s.supplier_name,
  COUNT(DISTINCT po.id) AS total_orders,
  AVG(EXTRACT(DAY FROM
    (SELECT MIN(t.created_at) FROM grocery_local.inventory_transactions t
     WHERE t.reference_id = po.id) - po.order_date
  )) AS avg_delivery_days,
  SUM(po.total_amount) AS total_spend
FROM grocery_local.purchase_orders po
JOIN grocery_local.suppliers s ON s.id = po.supplier_id
WHERE po.store_id = :store_id
  AND po.status = 'RECEIVED'
GROUP BY s.supplier_name
ORDER BY total_spend DESC;
