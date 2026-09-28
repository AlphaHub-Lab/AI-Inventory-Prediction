-- Transactional stock receipt. Call inside the API after validating each received line and batch.
DO $$ DECLARE k text; ns text; BEGIN
 FOREACH k IN ARRAY ARRAY['grocery','medical','food','stationery'] LOOP
  ns := k || '_local';
  EXECUTE format($f$
    CREATE OR REPLACE FUNCTION %I.receive_purchase_order(
      p_order_id uuid, p_item_id uuid, p_quantity numeric, p_batch_number text DEFAULT '',
      p_manufacturing_date date DEFAULT NULL, p_expiry_date date DEFAULT NULL, p_location text DEFAULT NULL
    ) RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $body$
    DECLARE po %I.purchase_orders%%ROWTYPE; line %I.purchase_order_items%%ROWTYPE; inv %I.inventory_items%%ROWTYPE;
      b_id uuid; before_qty numeric; after_qty numeric; received_all boolean;
    BEGIN
      IF p_quantity <= 0 THEN RAISE EXCEPTION 'received quantity must be positive'; END IF;
      SELECT * INTO po FROM %I.purchase_orders WHERE id=p_order_id FOR UPDATE;
      IF NOT FOUND OR po.status IN ('DRAFT','CANCELLED','RECEIVED') THEN RAISE EXCEPTION 'purchase order cannot receive stock'; END IF;
      IF auth.uid() IS NOT NULL AND NOT EXISTS (SELECT 1 FROM public.inventory_store_memberships WHERE store_id=po.store_id AND user_id=auth.uid()) THEN RAISE EXCEPTION 'store access denied'; END IF;
      SELECT * INTO line FROM %I.purchase_order_items WHERE id=p_item_id AND purchase_order_id=p_order_id FOR UPDATE;
      IF NOT FOUND OR line.quantity_received + p_quantity > line.quantity_ordered THEN RAISE EXCEPTION 'receipt exceeds open quantity'; END IF;
      SELECT * INTO inv FROM %I.inventory_items WHERE id=line.item_id AND store_id=po.store_id FOR UPDATE;
      IF NOT FOUND THEN RAISE EXCEPTION 'inventory item/store mismatch'; END IF;
      IF auth.uid() IS NOT NULL AND NOT EXISTS (SELECT 1 FROM public.inventory_store_memberships WHERE store_id=p_store_id AND user_id=auth.uid()) THEN RAISE EXCEPTION 'store access denied'; END IF;
      SELECT coalesce(sum(quantity),0) INTO before_qty FROM %I.inventory_batches WHERE item_id=inv.id;
      INSERT INTO %I.inventory_batches(item_id,batch_number,manufacturing_date,expiry_date,quantity)
        VALUES(inv.id,coalesce(p_batch_number,''),p_manufacturing_date,p_expiry_date,p_quantity)
        ON CONFLICT (item_id,batch_number,expiry_date) DO UPDATE SET quantity=%I.inventory_batches.quantity + EXCLUDED.quantity
        RETURNING id INTO b_id;
      after_qty := before_qty + p_quantity;
      UPDATE %I.purchase_order_items SET quantity_received=quantity_received+p_quantity WHERE id=p_item_id;
      SELECT bool_and(quantity_received=quantity_ordered) INTO received_all FROM %I.purchase_order_items WHERE purchase_order_id=p_order_id;
      UPDATE %I.purchase_orders SET status=CASE WHEN received_all THEN 'RECEIVED' ELSE 'PARTIALLY_RECEIVED' END, updated_at=now() WHERE id=p_order_id;
      UPDATE %I.inventory_items SET cost_price=line.unit_cost, supplier_id=po.supplier_id,
        storage_location=coalesce(p_location,storage_location), stock_status=CASE WHEN after_qty=0 THEN 'OUT_OF_STOCK' WHEN after_qty<=reorder_level THEN 'LOW_STOCK' ELSE 'IN_STOCK' END, updated_at=now()
        WHERE id=inv.id;
      INSERT INTO %I.inventory_transactions(store_id,item_id,batch_id,transaction_type,quantity_delta,previous_stock,new_stock,reference_id,created_by)
        VALUES(po.store_id,inv.id,b_id,'PURCHASE',p_quantity,before_qty,after_qty,p_order_id,auth.uid());
      RETURN b_id;
    END $body$;
  $f$, ns,ns,ns,ns,ns,ns,ns,ns,ns,ns,ns,ns,ns,ns);
 END LOOP;
END $$;

-- Authenticated clients may read catalog rows. Mutations should use the API's authenticated user/JWT
-- so store RLS still applies; never grant anon access to private inventory.


DO $$ DECLARE k text; ns text; BEGIN
 FOREACH k IN ARRAY ARRAY['grocery','medical','food','stationery'] LOOP
  ns := k || '_local';
  EXECUTE format($f$
    CREATE OR REPLACE FUNCTION %I.sell_stock(p_store_id uuid,p_item_id uuid,p_quantity numeric,p_note text DEFAULT NULL)
    RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $body$
    DECLARE inv record; b record; remaining numeric:=p_quantity; take_qty numeric; before_qty numeric; current_qty numeric;
    BEGIN
      IF p_quantity <= 0 THEN RAISE EXCEPTION 'sale quantity must be positive'; END IF;
      SELECT * INTO inv FROM %I.inventory_items WHERE id=p_item_id AND store_id=p_store_id FOR UPDATE;
      IF NOT FOUND THEN RAISE EXCEPTION 'inventory item/store mismatch'; END IF;
      IF auth.uid() IS NOT NULL AND NOT EXISTS (SELECT 1 FROM public.inventory_store_memberships WHERE store_id=p_store_id AND user_id=auth.uid()) THEN RAISE EXCEPTION 'store access denied'; END IF;
      SELECT coalesce(sum(quantity),0) INTO current_qty FROM %I.inventory_batches WHERE item_id=p_item_id;
      IF current_qty-inv.reserved_stock < p_quantity THEN RAISE EXCEPTION 'insufficient available stock'; END IF;
      before_qty:=current_qty;
      FOR b IN SELECT id,quantity FROM %I.inventory_batches
        WHERE item_id=p_item_id AND quantity>0 AND (expiry_date IS NULL OR expiry_date>=CURRENT_DATE)
        ORDER BY expiry_date ASC NULLS LAST,created_at,id FOR UPDATE
      LOOP
        EXIT WHEN remaining=0;
        take_qty:=least(remaining,b.quantity);
        UPDATE %I.inventory_batches SET quantity=quantity-take_qty WHERE id=b.id;
        INSERT INTO %I.inventory_transactions(store_id,item_id,batch_id,transaction_type,quantity_delta,previous_stock,new_stock,note,created_by)
          VALUES(p_store_id,p_item_id,b.id,'SALE',-take_qty,before_qty,before_qty-take_qty,p_note,auth.uid());
        before_qty:=before_qty-take_qty;
        remaining:=remaining-take_qty;
      END LOOP;
      IF remaining>0 THEN RAISE EXCEPTION 'insufficient non-expired batch stock'; END IF;
      UPDATE %I.inventory_items SET stock_status=CASE WHEN before_qty=0 THEN 'OUT_OF_STOCK' WHEN before_qty<=reorder_level THEN 'LOW_STOCK' ELSE 'IN_STOCK' END,updated_at=now() WHERE id=p_item_id;
      RETURN true;
    END $body$;
  $f$,ns,ns,ns,ns,ns,ns,ns);
 END LOOP;
END $$;
GRANT EXECUTE ON FUNCTION grocery_local.sell_stock(uuid,uuid,numeric,text),medical_local.sell_stock(uuid,uuid,numeric,text),food_local.sell_stock(uuid,uuid,numeric,text),stationery_local.sell_stock(uuid,uuid,numeric,text) TO authenticated,service_role;

REVOKE INSERT,UPDATE,DELETE ON grocery_local.inventory_batches,grocery_local.inventory_transactions,medical_local.inventory_batches,medical_local.inventory_transactions,food_local.inventory_batches,food_local.inventory_transactions,stationery_local.inventory_batches,stationery_local.inventory_transactions FROM authenticated;
GRANT SELECT ON grocery_local.inventory_batches,grocery_local.inventory_transactions,medical_local.inventory_batches,medical_local.inventory_transactions,food_local.inventory_batches,food_local.inventory_transactions,stationery_local.inventory_batches,stationery_local.inventory_transactions TO authenticated;

REVOKE ALL ON FUNCTION grocery_local.receive_purchase_order(uuid,uuid,numeric,text,date,date,text),medical_local.receive_purchase_order(uuid,uuid,numeric,text,date,date,text),food_local.receive_purchase_order(uuid,uuid,numeric,text,date,date,text),stationery_local.receive_purchase_order(uuid,uuid,numeric,text,date,date,text),grocery_local.sell_stock(uuid,uuid,numeric,text),medical_local.sell_stock(uuid,uuid,numeric,text),food_local.sell_stock(uuid,uuid,numeric,text),stationery_local.sell_stock(uuid,uuid,numeric,text) FROM PUBLIC,anon;
GRANT EXECUTE ON FUNCTION grocery_local.receive_purchase_order(uuid,uuid,numeric,text,date,date,text),medical_local.receive_purchase_order(uuid,uuid,numeric,text,date,date,text),food_local.receive_purchase_order(uuid,uuid,numeric,text,date,date,text),stationery_local.receive_purchase_order(uuid,uuid,numeric,text,date,date,text),grocery_local.sell_stock(uuid,uuid,numeric,text),medical_local.sell_stock(uuid,uuid,numeric,text),food_local.sell_stock(uuid,uuid,numeric,text),stationery_local.sell_stock(uuid,uuid,numeric,text) TO authenticated,service_role;
