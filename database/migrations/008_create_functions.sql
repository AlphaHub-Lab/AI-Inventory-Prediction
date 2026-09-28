-- ============================================================================
-- MIGRATION 008: BUSINESS LOGIC FUNCTIONS
-- ============================================================================
-- Atomic server-side functions for the critical workflows:
--   1. receive_purchase_order() – atomically receive stock from a PO
--   2. sell_stock()             – FEFO deduction with expired-batch guard
--   3. import_from_master()     – add/update local inventory from master
--   4. record_waste()           – waste write-off with transaction
--   5. adjust_stock()           – manual stock adjustment with audit trail
-- ============================================================================

DO $$
DECLARE
  kinds TEXT[] := ARRAY['grocery', 'medical', 'food', 'stationery'];
  kind  TEXT;
  ns    TEXT;
BEGIN
  FOREACH kind IN ARRAY kinds LOOP
    ns := kind || '_local';

    -- =================================================================
    -- 1. receive_purchase_order
    -- =================================================================
    EXECUTE format($f$
      CREATE OR REPLACE FUNCTION %I.receive_purchase_order(
        p_order_id          UUID,
        p_line_id           UUID,
        p_quantity           NUMERIC,
        p_batch_number      TEXT    DEFAULT '',
        p_manufacturing_date DATE   DEFAULT NULL,
        p_expiry_date        DATE   DEFAULT NULL,
        p_location           TEXT   DEFAULT NULL
      ) RETURNS UUID
      LANGUAGE plpgsql
      SECURITY DEFINER
      SET search_path = pg_catalog, public
      AS $body$
      DECLARE
        po            %I.purchase_orders%%ROWTYPE;
        line          %I.purchase_order_items%%ROWTYPE;
        inv           %I.inventory_items%%ROWTYPE;
        b_id          UUID;
        before_qty    NUMERIC;
        after_qty     NUMERIC;
        received_all  BOOLEAN;
      BEGIN
        -- Validate
        IF p_quantity <= 0 THEN
          RAISE EXCEPTION 'received quantity must be positive';
        END IF;

        -- Lock the purchase order
        SELECT * INTO po
          FROM %I.purchase_orders
          WHERE id = p_order_id
          FOR UPDATE;
        IF NOT FOUND THEN
          RAISE EXCEPTION 'purchase order not found';
        END IF;
        IF po.status IN ('DRAFT', 'CANCELLED', 'RECEIVED') THEN
          RAISE EXCEPTION 'purchase order status %% does not allow receipt', po.status;
        END IF;

        -- Verify caller membership
        IF auth.uid() IS NOT NULL AND NOT EXISTS (
          SELECT 1 FROM public.store_memberships
          WHERE store_id = po.store_id AND user_id = auth.uid()
        ) THEN
          RAISE EXCEPTION 'store access denied';
        END IF;

        -- Lock the PO line
        SELECT * INTO line
          FROM %I.purchase_order_items
          WHERE id = p_line_id AND purchase_order_id = p_order_id
          FOR UPDATE;
        IF NOT FOUND THEN
          RAISE EXCEPTION 'purchase order line not found';
        END IF;
        IF line.quantity_received + p_quantity > line.quantity_ordered THEN
          RAISE EXCEPTION 'receipt exceeds ordered quantity (ordered: %%, already received: %%, attempting: %%)',
            line.quantity_ordered, line.quantity_received, p_quantity;
        END IF;

        -- Lock inventory item
        SELECT * INTO inv
          FROM %I.inventory_items
          WHERE id = line.item_id AND store_id = po.store_id
          FOR UPDATE;
        IF NOT FOUND THEN
          RAISE EXCEPTION 'inventory item/store mismatch';
        END IF;

        -- Calculate before-stock
        SELECT COALESCE(SUM(quantity), 0) INTO before_qty
          FROM %I.inventory_batches WHERE item_id = inv.id;

        -- Upsert batch
        INSERT INTO %I.inventory_batches (
          item_id, batch_number, manufacturing_date, expiry_date, quantity
        ) VALUES (
          inv.id, COALESCE(p_batch_number, ''), p_manufacturing_date, p_expiry_date, p_quantity
        )
        ON CONFLICT (item_id, batch_number, expiry_date)
        DO UPDATE SET quantity = %I.inventory_batches.quantity + EXCLUDED.quantity
        RETURNING id INTO b_id;

        after_qty := before_qty + p_quantity;

        -- Update PO line
        UPDATE %I.purchase_order_items
          SET quantity_received = quantity_received + p_quantity
          WHERE id = p_line_id;

        -- Check if all lines fully received
        SELECT bool_and(quantity_received >= quantity_ordered) INTO received_all
          FROM %I.purchase_order_items
          WHERE purchase_order_id = p_order_id;

        -- Update PO status
        UPDATE %I.purchase_orders
          SET status = CASE WHEN received_all THEN 'RECEIVED' ELSE 'PARTIALLY_RECEIVED' END,
              updated_at = now()
          WHERE id = p_order_id;

        -- Update inventory item
        UPDATE %I.inventory_items
          SET cost_price       = line.unit_cost,
              supplier_id      = po.supplier_id,
              storage_location = COALESCE(p_location, storage_location),
              stock_status     = CASE
                WHEN after_qty = 0 THEN 'OUT_OF_STOCK'
                WHEN after_qty <= reorder_level THEN 'LOW_STOCK'
                ELSE 'IN_STOCK'
              END,
              updated_at = now()
          WHERE id = inv.id;

        -- Create inventory transaction
        INSERT INTO %I.inventory_transactions (
          store_id, item_id, batch_id, transaction_type,
          quantity_delta, previous_stock, new_stock,
          reference_id, reference_type, created_by
        ) VALUES (
          po.store_id, inv.id, b_id, 'PURCHASE',
          p_quantity, before_qty, after_qty,
          p_order_id, 'purchase_order', auth.uid()
        );

        -- Audit log
        INSERT INTO public.audit_log (
          store_id, user_id, action, entity, entity_id, new_value
        ) VALUES (
          po.store_id, auth.uid(), 'PURCHASE_ORDER_RECEIVED',
          'purchase_order_item', p_line_id::TEXT,
          jsonb_build_object(
            'order_id', p_order_id,
            'quantity', p_quantity,
            'batch', p_batch_number,
            'before_stock', before_qty,
            'after_stock', after_qty
          )
        );

        RETURN b_id;
      END $body$;
    $f$, ns, ns, ns, ns, ns, ns, ns, ns, ns, ns, ns, ns, ns, ns, ns);

    -- =================================================================
    -- 2. sell_stock (FEFO – First Expired, First Out)
    -- =================================================================
    EXECUTE format($f$
      CREATE OR REPLACE FUNCTION %I.sell_stock(
        p_store_id  UUID,
        p_item_id   UUID,
        p_quantity   NUMERIC,
        p_note       TEXT DEFAULT NULL
      ) RETURNS BOOLEAN
      LANGUAGE plpgsql
      SECURITY DEFINER
      SET search_path = pg_catalog, public
      AS $body$
      DECLARE
        inv          RECORD;
        b            RECORD;
        remaining    NUMERIC := p_quantity;
        take_qty     NUMERIC;
        before_qty   NUMERIC;
        running_qty  NUMERIC;
      BEGIN
        IF p_quantity <= 0 THEN
          RAISE EXCEPTION 'sale quantity must be positive';
        END IF;

        -- Lock inventory item
        SELECT * INTO inv
          FROM %I.inventory_items
          WHERE id = p_item_id AND store_id = p_store_id
          FOR UPDATE;
        IF NOT FOUND THEN
          RAISE EXCEPTION 'inventory item/store mismatch';
        END IF;

        -- Verify membership
        IF auth.uid() IS NOT NULL AND NOT EXISTS (
          SELECT 1 FROM public.store_memberships
          WHERE store_id = p_store_id AND user_id = auth.uid()
        ) THEN
          RAISE EXCEPTION 'store access denied';
        END IF;

        -- Current total
        SELECT COALESCE(SUM(quantity), 0) INTO before_qty
          FROM %I.inventory_batches WHERE item_id = p_item_id;

        IF before_qty - inv.reserved_stock < p_quantity THEN
          RAISE EXCEPTION 'insufficient available stock (available: %%, requested: %%)',
            before_qty - inv.reserved_stock, p_quantity;
        END IF;

        running_qty := before_qty;

        -- FEFO: deduct from earliest-expiring non-expired batches first
        FOR b IN
          SELECT id, quantity
          FROM %I.inventory_batches
          WHERE item_id = p_item_id
            AND quantity > 0
            AND (expiry_date IS NULL OR expiry_date >= CURRENT_DATE)
          ORDER BY expiry_date ASC NULLS LAST, created_at, id
          FOR UPDATE
        LOOP
          EXIT WHEN remaining = 0;
          take_qty := LEAST(remaining, b.quantity);

          UPDATE %I.inventory_batches
            SET quantity = quantity - take_qty
            WHERE id = b.id;

          INSERT INTO %I.inventory_transactions (
            store_id, item_id, batch_id, transaction_type,
            quantity_delta, previous_stock, new_stock,
            note, created_by
          ) VALUES (
            p_store_id, p_item_id, b.id, 'SALE',
            -take_qty, running_qty, running_qty - take_qty,
            p_note, auth.uid()
          );

          running_qty := running_qty - take_qty;
          remaining   := remaining - take_qty;
        END LOOP;

        IF remaining > 0 THEN
          RAISE EXCEPTION 'insufficient non-expired batch stock';
        END IF;

        -- Update stock status
        UPDATE %I.inventory_items
          SET stock_status = CASE
                WHEN running_qty = 0 THEN 'OUT_OF_STOCK'
                WHEN running_qty <= reorder_level THEN 'LOW_STOCK'
                ELSE 'IN_STOCK'
              END,
              updated_at = now()
          WHERE id = p_item_id;

        -- Audit
        INSERT INTO public.audit_log (
          store_id, user_id, action, entity, entity_id, new_value
        ) VALUES (
          p_store_id, auth.uid(), 'STOCK_SOLD',
          'inventory_item', p_item_id::TEXT,
          jsonb_build_object(
            'quantity', p_quantity,
            'before_stock', before_qty,
            'after_stock', running_qty
          )
        );

        RETURN TRUE;
      END $body$;
    $f$, ns, ns, ns, ns, ns, ns, ns);

    -- =================================================================
    -- 3. import_from_master – add master product to local inventory
    -- =================================================================
    EXECUTE format($f$
      CREATE OR REPLACE FUNCTION %I.import_from_master(
        p_store_id           UUID,
        p_master_product_id  UUID,
        p_quantity           NUMERIC DEFAULT 0,
        p_cost_price         NUMERIC DEFAULT 0,
        p_selling_price      NUMERIC DEFAULT 0,
        p_batch_number       TEXT    DEFAULT '',
        p_manufacturing_date DATE    DEFAULT NULL,
        p_expiry_date        DATE    DEFAULT NULL,
        p_storage_location   TEXT    DEFAULT NULL,
        p_supplier_id        UUID    DEFAULT NULL
      ) RETURNS UUID
      LANGUAGE plpgsql
      SECURITY DEFINER
      SET search_path = pg_catalog, public
      AS $body$
      DECLARE
        master_prod  RECORD;
        inv_id       UUID;
        b_id         UUID;
        before_qty   NUMERIC := 0;
        after_qty    NUMERIC;
        ms           TEXT := '%s_master';
      BEGIN
        -- Verify membership
        IF auth.uid() IS NOT NULL AND NOT EXISTS (
          SELECT 1 FROM public.store_memberships
          WHERE store_id = p_store_id AND user_id = auth.uid()
        ) THEN
          RAISE EXCEPTION 'store access denied';
        END IF;

        -- Fetch master product
        EXECUTE format(
          'SELECT * FROM %%I.products WHERE id = $1 AND is_active',
          ms
        ) INTO master_prod USING p_master_product_id;

        IF master_prod IS NULL THEN
          RAISE EXCEPTION 'master product not found or inactive';
        END IF;

        -- Upsert local inventory item (prevent duplicates)
        INSERT INTO %I.inventory_items (
          store_id, master_product_id, sku, barcode, product_name,
          brand, category, subcategory,
          cost_price, selling_price, mrp, gst_percentage,
          supplier_id, storage_location, stock_status
        ) VALUES (
          p_store_id, p_master_product_id, master_prod.sku,
          master_prod.barcode, master_prod.product_name,
          master_prod.brand, master_prod.category, master_prod.subcategory,
          COALESCE(NULLIF(p_cost_price, 0), master_prod.default_cost_price, 0),
          COALESCE(NULLIF(p_selling_price, 0), master_prod.default_selling_price, 0),
          master_prod.mrp, master_prod.gst_percentage,
          p_supplier_id, p_storage_location, 'OUT_OF_STOCK'
        )
        ON CONFLICT (store_id, master_product_id)
        DO UPDATE SET updated_at = now()
        RETURNING id INTO inv_id;

        -- If quantity > 0, add batch and create transaction
        IF p_quantity > 0 THEN
          SELECT COALESCE(SUM(quantity), 0) INTO before_qty
            FROM %I.inventory_batches WHERE item_id = inv_id;

          INSERT INTO %I.inventory_batches (
            item_id, batch_number, manufacturing_date, expiry_date, quantity
          ) VALUES (
            inv_id, COALESCE(p_batch_number, ''),
            p_manufacturing_date, p_expiry_date, p_quantity
          )
          ON CONFLICT (item_id, batch_number, expiry_date)
          DO UPDATE SET quantity = %I.inventory_batches.quantity + EXCLUDED.quantity
          RETURNING id INTO b_id;

          after_qty := before_qty + p_quantity;

          -- Update stock status
          UPDATE %I.inventory_items
            SET stock_status = CASE
                  WHEN after_qty = 0 THEN 'OUT_OF_STOCK'
                  WHEN after_qty <= reorder_level THEN 'LOW_STOCK'
                  ELSE 'IN_STOCK'
                END,
                updated_at = now()
            WHERE id = inv_id;

          -- Transaction record
          INSERT INTO %I.inventory_transactions (
            store_id, item_id, batch_id, transaction_type,
            quantity_delta, previous_stock, new_stock,
            reference_type, note, created_by
          ) VALUES (
            p_store_id, inv_id, b_id, 'PURCHASE',
            p_quantity, before_qty, after_qty,
            'master_import', 'Imported from master catalog',
            auth.uid()
          );

          -- Audit
          INSERT INTO public.audit_log (
            store_id, user_id, action, entity, entity_id, new_value
          ) VALUES (
            p_store_id, auth.uid(), 'PRODUCT_IMPORTED',
            'inventory_item', inv_id::TEXT,
            jsonb_build_object(
              'master_product_id', p_master_product_id,
              'quantity', p_quantity,
              'batch', p_batch_number
            )
          );
        ELSE
          -- Just audit the import (0 quantity)
          INSERT INTO public.audit_log (
            store_id, user_id, action, entity, entity_id, new_value
          ) VALUES (
            p_store_id, auth.uid(), 'PRODUCT_IMPORTED',
            'inventory_item', inv_id::TEXT,
            jsonb_build_object(
              'master_product_id', p_master_product_id,
              'quantity', 0
            )
          );
        END IF;

        RETURN inv_id;
      END $body$;
    $f$, ns, kind, ns, ns, ns, ns, ns, ns);

    -- =================================================================
    -- 4. record_waste – waste/spoilage/damage write-off
    -- =================================================================
    EXECUTE format($f$
      CREATE OR REPLACE FUNCTION %I.record_waste(
        p_store_id      UUID,
        p_item_id       UUID,
        p_quantity       NUMERIC,
        p_reason         TEXT,
        p_batch_id       UUID    DEFAULT NULL,
        p_notes          TEXT    DEFAULT NULL
      ) RETURNS UUID
      LANGUAGE plpgsql
      SECURITY DEFINER
      SET search_path = pg_catalog, public
      AS $body$
      DECLARE
        inv          RECORD;
        batch_rec    RECORD;
        waste_id     UUID;
        before_qty   NUMERIC;
        after_qty    NUMERIC;
        txn_type     TEXT;
      BEGIN
        IF p_quantity <= 0 THEN
          RAISE EXCEPTION 'waste quantity must be positive';
        END IF;
        IF p_reason NOT IN ('EXPIRED', 'DAMAGED', 'SPOILED', 'RETURNED', 'OTHER') THEN
          RAISE EXCEPTION 'invalid waste reason';
        END IF;

        -- Lock inventory item
        SELECT * INTO inv
          FROM %I.inventory_items
          WHERE id = p_item_id AND store_id = p_store_id
          FOR UPDATE;
        IF NOT FOUND THEN
          RAISE EXCEPTION 'inventory item/store mismatch';
        END IF;

        -- Verify membership
        IF auth.uid() IS NOT NULL AND NOT EXISTS (
          SELECT 1 FROM public.store_memberships
          WHERE store_id = p_store_id AND user_id = auth.uid()
        ) THEN
          RAISE EXCEPTION 'store access denied';
        END IF;

        SELECT COALESCE(SUM(quantity), 0) INTO before_qty
          FROM %I.inventory_batches WHERE item_id = p_item_id;

        -- If batch specified, deduct from that batch
        IF p_batch_id IS NOT NULL THEN
          SELECT * INTO batch_rec
            FROM %I.inventory_batches
            WHERE id = p_batch_id AND item_id = p_item_id
            FOR UPDATE;
          IF NOT FOUND OR batch_rec.quantity < p_quantity THEN
            RAISE EXCEPTION 'insufficient batch quantity for waste';
          END IF;
          UPDATE %I.inventory_batches
            SET quantity = quantity - p_quantity
            WHERE id = p_batch_id;
        ELSE
          -- Deduct from oldest batch
          DECLARE
            b RECORD; rem NUMERIC := p_quantity; tk NUMERIC;
          BEGIN
            FOR b IN
              SELECT id, quantity FROM %I.inventory_batches
              WHERE item_id = p_item_id AND quantity > 0
              ORDER BY expiry_date ASC NULLS LAST, created_at
              FOR UPDATE
            LOOP
              EXIT WHEN rem = 0;
              tk := LEAST(rem, b.quantity);
              UPDATE %I.inventory_batches SET quantity = quantity - tk WHERE id = b.id;
              rem := rem - tk;
            END LOOP;
            IF rem > 0 THEN
              RAISE EXCEPTION 'insufficient stock for waste write-off';
            END IF;
          END;
        END IF;

        after_qty := before_qty - p_quantity;
        txn_type := CASE p_reason
          WHEN 'EXPIRED' THEN 'EXPIRED'
          WHEN 'DAMAGED' THEN 'DAMAGE'
          WHEN 'RETURNED' THEN 'RETURN'
          ELSE 'ADJUSTMENT'
        END;

        -- Create waste record
        INSERT INTO %I.waste_records (
          store_id, item_id, batch_id, quantity, reason,
          batch_number, expiry_date, cost_loss, notes, created_by
        ) VALUES (
          p_store_id, p_item_id, p_batch_id, p_quantity, p_reason,
          COALESCE(batch_rec.batch_number, ''),
          batch_rec.expiry_date,
          p_quantity * inv.cost_price,
          p_notes, auth.uid()
        ) RETURNING id INTO waste_id;

        -- Transaction record
        INSERT INTO %I.inventory_transactions (
          store_id, item_id, batch_id, transaction_type,
          quantity_delta, previous_stock, new_stock,
          reference_id, reference_type, note, created_by
        ) VALUES (
          p_store_id, p_item_id, p_batch_id, txn_type,
          -p_quantity, before_qty, after_qty,
          waste_id, 'waste', p_notes, auth.uid()
        );

        -- Update stock status
        UPDATE %I.inventory_items
          SET stock_status = CASE
                WHEN after_qty = 0 THEN 'OUT_OF_STOCK'
                WHEN after_qty <= reorder_level THEN 'LOW_STOCK'
                ELSE 'IN_STOCK'
              END,
              updated_at = now()
          WHERE id = p_item_id;

        -- Audit
        INSERT INTO public.audit_log (
          store_id, user_id, action, entity, entity_id, new_value
        ) VALUES (
          p_store_id, auth.uid(), 'WASTE_RECORDED',
          'waste_record', waste_id::TEXT,
          jsonb_build_object(
            'item_id', p_item_id,
            'quantity', p_quantity,
            'reason', p_reason,
            'cost_loss', p_quantity * inv.cost_price
          )
        );

        RETURN waste_id;
      END $body$;
    $f$, ns, ns, ns, ns, ns, ns, ns, ns, ns, ns);

    -- =================================================================
    -- 5. adjust_stock – manual stock adjustment with audit
    -- =================================================================
    EXECUTE format($f$
      CREATE OR REPLACE FUNCTION %I.adjust_stock(
        p_store_id      UUID,
        p_item_id       UUID,
        p_quantity_delta NUMERIC,
        p_reason         TEXT DEFAULT 'Manual adjustment',
        p_batch_number   TEXT DEFAULT '',
        p_expiry_date    DATE DEFAULT NULL
      ) RETURNS UUID
      LANGUAGE plpgsql
      SECURITY DEFINER
      SET search_path = pg_catalog, public
      AS $body$
      DECLARE
        inv        RECORD;
        b_id       UUID;
        before_qty NUMERIC;
        after_qty  NUMERIC;
        txn_id     UUID;
      BEGIN
        IF p_quantity_delta = 0 THEN
          RAISE EXCEPTION 'adjustment quantity cannot be zero';
        END IF;

        SELECT * INTO inv
          FROM %I.inventory_items
          WHERE id = p_item_id AND store_id = p_store_id
          FOR UPDATE;
        IF NOT FOUND THEN
          RAISE EXCEPTION 'inventory item/store mismatch';
        END IF;

        IF auth.uid() IS NOT NULL AND NOT EXISTS (
          SELECT 1 FROM public.store_memberships
          WHERE store_id = p_store_id AND user_id = auth.uid()
        ) THEN
          RAISE EXCEPTION 'store access denied';
        END IF;

        SELECT COALESCE(SUM(quantity), 0) INTO before_qty
          FROM %I.inventory_batches WHERE item_id = p_item_id;

        IF p_quantity_delta > 0 THEN
          -- Positive adjustment: add to batch
          INSERT INTO %I.inventory_batches (item_id, batch_number, expiry_date, quantity)
          VALUES (p_item_id, COALESCE(p_batch_number, ''), p_expiry_date, p_quantity_delta)
          ON CONFLICT (item_id, batch_number, expiry_date)
          DO UPDATE SET quantity = %I.inventory_batches.quantity + EXCLUDED.quantity
          RETURNING id INTO b_id;
        ELSE
          -- Negative adjustment: deduct from oldest batch
          DECLARE
            b RECORD; rem NUMERIC := ABS(p_quantity_delta); tk NUMERIC;
          BEGIN
            FOR b IN
              SELECT id, quantity FROM %I.inventory_batches
              WHERE item_id = p_item_id AND quantity > 0
              ORDER BY expiry_date ASC NULLS LAST, created_at
              FOR UPDATE
            LOOP
              EXIT WHEN rem = 0;
              tk := LEAST(rem, b.quantity);
              UPDATE %I.inventory_batches SET quantity = quantity - tk WHERE id = b.id;
              b_id := b.id;
              rem := rem - tk;
            END LOOP;
            IF rem > 0 THEN
              RAISE EXCEPTION 'insufficient stock for negative adjustment';
            END IF;
          END;
        END IF;

        after_qty := before_qty + p_quantity_delta;

        INSERT INTO %I.inventory_transactions (
          store_id, item_id, batch_id, transaction_type,
          quantity_delta, previous_stock, new_stock,
          reference_type, note, created_by
        ) VALUES (
          p_store_id, p_item_id, b_id, 'ADJUSTMENT',
          p_quantity_delta, before_qty, after_qty,
          'manual', p_reason, auth.uid()
        ) RETURNING id INTO txn_id;

        UPDATE %I.inventory_items
          SET stock_status = CASE
                WHEN after_qty = 0 THEN 'OUT_OF_STOCK'
                WHEN after_qty <= reorder_level THEN 'LOW_STOCK'
                ELSE 'IN_STOCK'
              END,
              updated_at = now()
          WHERE id = p_item_id;

        INSERT INTO public.audit_log (
          store_id, user_id, action, entity, entity_id,
          old_value, new_value
        ) VALUES (
          p_store_id, auth.uid(), 'STOCK_ADJUSTED',
          'inventory_item', p_item_id::TEXT,
          jsonb_build_object('stock', before_qty),
          jsonb_build_object('stock', after_qty, 'delta', p_quantity_delta, 'reason', p_reason)
        );

        RETURN txn_id;
      END $body$;
    $f$, ns, ns, ns, ns, ns, ns, ns, ns, ns);

  END LOOP;
END $$;

-- ---------------------------------------------------------------------------
-- Grant execute on all functions
-- ---------------------------------------------------------------------------
DO $$
DECLARE
  kinds TEXT[] := ARRAY['grocery', 'medical', 'food', 'stationery'];
  kind TEXT; ns TEXT;
BEGIN
  FOREACH kind IN ARRAY kinds LOOP
    ns := kind || '_local';

    -- Revoke from public/anon
    EXECUTE format('REVOKE ALL ON FUNCTION %I.receive_purchase_order(UUID,UUID,NUMERIC,TEXT,DATE,DATE,TEXT) FROM PUBLIC, anon', ns);
    EXECUTE format('REVOKE ALL ON FUNCTION %I.sell_stock(UUID,UUID,NUMERIC,TEXT) FROM PUBLIC, anon', ns);
    EXECUTE format('REVOKE ALL ON FUNCTION %I.import_from_master(UUID,UUID,NUMERIC,NUMERIC,NUMERIC,TEXT,DATE,DATE,TEXT,UUID) FROM PUBLIC, anon', ns);
    EXECUTE format('REVOKE ALL ON FUNCTION %I.record_waste(UUID,UUID,NUMERIC,TEXT,UUID,TEXT) FROM PUBLIC, anon', ns);
    EXECUTE format('REVOKE ALL ON FUNCTION %I.adjust_stock(UUID,UUID,NUMERIC,TEXT,TEXT,DATE) FROM PUBLIC, anon', ns);

    -- Grant to authenticated + service_role
    EXECUTE format('GRANT EXECUTE ON FUNCTION %I.receive_purchase_order(UUID,UUID,NUMERIC,TEXT,DATE,DATE,TEXT) TO authenticated, service_role', ns);
    EXECUTE format('GRANT EXECUTE ON FUNCTION %I.sell_stock(UUID,UUID,NUMERIC,TEXT) TO authenticated, service_role', ns);
    EXECUTE format('GRANT EXECUTE ON FUNCTION %I.import_from_master(UUID,UUID,NUMERIC,NUMERIC,NUMERIC,TEXT,DATE,DATE,TEXT,UUID) TO authenticated, service_role', ns);
    EXECUTE format('GRANT EXECUTE ON FUNCTION %I.record_waste(UUID,UUID,NUMERIC,TEXT,UUID,TEXT) TO authenticated, service_role', ns);
    EXECUTE format('GRANT EXECUTE ON FUNCTION %I.adjust_stock(UUID,UUID,NUMERIC,TEXT,TEXT,DATE) TO authenticated, service_role', ns);
  END LOOP;
END $$;
