DO $$
DECLARE kind text; side text; ns text; policy_expr text;
BEGIN
  FOREACH kind IN ARRAY ARRAY['grocery','medical','food','stationery'] LOOP
    FOREACH side IN ARRAY ARRAY['master','local'] LOOP
      ns := kind || '_' || side;
      EXECUTE format('CREATE SCHEMA IF NOT EXISTS %I', ns);
      EXECUTE format('CREATE TABLE %I.suppliers (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(), supplier_code text NOT NULL UNIQUE, supplier_name text NOT NULL,
        contact_person text, phone text, email text, address text, city text, state text, pincode text, gst_number text,
        payment_terms text, is_active boolean NOT NULL DEFAULT true, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now())', ns);
      EXECUTE format('CREATE TABLE %I.products (
        id uuid PRIMARY KEY DEFAULT gen_random_uuid(), sku text NOT NULL UNIQUE, barcode text,
        product_name text NOT NULL, brand text, category text, subcategory text, description text,
        unit text NOT NULL DEFAULT ''unit'', pack_size text, mrp numeric(12,2) CHECK (mrp >= 0),
        default_cost_price numeric(12,2) CHECK (default_cost_price >= 0), default_selling_price numeric(12,2) CHECK (default_selling_price >= 0),
        gst_percentage numeric(5,2) NOT NULL DEFAULT 0 CHECK(gst_percentage BETWEEN 0 AND 100), supplier_id uuid REFERENCES %I.suppliers(id),
        is_active boolean NOT NULL DEFAULT true, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now())', ns,ns);
      EXECUTE format('CREATE INDEX %I ON %I.products(product_name)', 'ix_'||ns||'_name',ns);
      EXECUTE format('CREATE INDEX %I ON %I.products(barcode) WHERE barcode IS NOT NULL', 'ix_'||ns||'_barcode',ns);
      EXECUTE format('CREATE INDEX %I ON %I.products USING gin(to_tsvector(''simple'', coalesce(product_name,'''') || '' '' || coalesce(brand,'''') || '' '' || coalesce(category,'''') || '' '' || sku))', 'ix_'||ns||'_search',ns);
      EXECUTE format('CREATE TABLE %I.product_suppliers (
        product_id uuid NOT NULL REFERENCES %I.products(id) ON DELETE CASCADE, supplier_id uuid NOT NULL REFERENCES %I.suppliers(id),
        supplier_sku text, cost_price numeric(12,2) CHECK(cost_price >= 0), lead_time_days integer CHECK(lead_time_days >= 0),
        is_preferred boolean NOT NULL DEFAULT false, PRIMARY KEY(product_id,supplier_id))',ns,ns,ns);
      IF side='master' THEN
        IF kind='medical' THEN EXECUTE format('CREATE TABLE %I.medical_product_details (product_id uuid PRIMARY KEY REFERENCES %I.products(id) ON DELETE CASCADE, generic_name text, drug_type text, dosage_form text, strength text, manufacturer text, prescription_required boolean, schedule text, storage_conditions text)',ns,ns); END IF;
        IF kind='food' THEN EXECUTE format('CREATE TABLE %I.food_product_details (product_id uuid PRIMARY KEY REFERENCES %I.products(id) ON DELETE CASCADE, food_type text, storage_type text, best_before_days integer CHECK(best_before_days IS NULL OR best_before_days >= 0))',ns,ns); END IF;
        IF kind='stationery' THEN EXECUTE format('CREATE TABLE %I.stationery_product_details (product_id uuid PRIMARY KEY REFERENCES %I.products(id) ON DELETE CASCADE, color text, size text, material text)',ns,ns); END IF;
      ELSE
        EXECUTE format('CREATE TABLE %I.inventory_items (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(), store_id uuid NOT NULL REFERENCES public.inventory_stores(id), master_product_id uuid,
          sku text NOT NULL, barcode text, product_name text NOT NULL, category text, subcategory text,
          reserved_stock numeric(14,3) NOT NULL DEFAULT 0 CHECK(reserved_stock >= 0), reorder_level numeric(14,3) NOT NULL DEFAULT 0 CHECK(reorder_level >= 0),
          minimum_stock numeric(14,3) NOT NULL DEFAULT 0, maximum_stock numeric(14,3), cost_price numeric(12,2) NOT NULL DEFAULT 0,
          selling_price numeric(12,2) NOT NULL DEFAULT 0, mrp numeric(12,2), gst_percentage numeric(5,2) NOT NULL DEFAULT 0,
          supplier_id uuid REFERENCES %I.suppliers(id), storage_location text, stock_status text NOT NULL DEFAULT ''OUT_OF_STOCK'' CHECK(stock_status IN (''IN_STOCK'',''LOW_STOCK'',''OUT_OF_STOCK'',''EXPIRED'',''DAMAGED'',''BLOCKED'')),
          created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(), UNIQUE(store_id,sku),
          UNIQUE(store_id,master_product_id))',ns,ns);
        EXECUTE format('CREATE TABLE %I.inventory_batches (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(), item_id uuid NOT NULL REFERENCES %I.inventory_items(id), batch_number text NOT NULL DEFAULT '''',
          manufacturing_date date, expiry_date date, quantity numeric(14,3) NOT NULL DEFAULT 0 CHECK(quantity >= 0),
          created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(item_id,batch_number,expiry_date), CHECK(expiry_date IS NULL OR manufacturing_date IS NULL OR expiry_date >= manufacturing_date))',ns,ns);
        EXECUTE format('CREATE INDEX %I ON %I.inventory_batches(expiry_date) WHERE quantity > 0', 'ix_'||ns||'_expiry',ns);
        EXECUTE format('CREATE VIEW %I.inventory_stock WITH (security_invoker=true) AS SELECT i.*, coalesce(sum(b.quantity),0) AS current_stock, coalesce(sum(b.quantity),0)-i.reserved_stock AS available_stock FROM %I.inventory_items i LEFT JOIN %I.inventory_batches b ON b.item_id=i.id GROUP BY i.id',ns,ns,ns);
        EXECUTE format('CREATE TABLE %I.inventory_transactions (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(), store_id uuid NOT NULL REFERENCES public.inventory_stores(id), item_id uuid NOT NULL REFERENCES %I.inventory_items(id), batch_id uuid REFERENCES %I.inventory_batches(id),
          transaction_type text NOT NULL CHECK(transaction_type IN (''PURCHASE'',''SALE'',''RETURN'',''DAMAGE'',''EXPIRED'',''ADJUSTMENT'',''TRANSFER_IN'',''TRANSFER_OUT'')),
          quantity_delta numeric(14,3) NOT NULL CHECK(quantity_delta <> 0), previous_stock numeric(14,3) NOT NULL, new_stock numeric(14,3) NOT NULL,
          reference_id uuid, note text, created_by uuid REFERENCES auth.users(id), created_at timestamptz NOT NULL DEFAULT now())',ns,ns,ns);
        EXECUTE format('CREATE INDEX %I ON %I.inventory_transactions(item_id,created_at DESC)', 'ix_'||ns||'_txn_item',ns);
        EXECUTE format('CREATE TABLE %I.purchase_orders (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(), store_id uuid NOT NULL REFERENCES public.inventory_stores(id), supplier_id uuid NOT NULL REFERENCES %I.suppliers(id),
          order_date timestamptz NOT NULL DEFAULT now(), expected_delivery_date date, status text NOT NULL DEFAULT ''PENDING'' CHECK(status IN (''DRAFT'',''PENDING'',''CONFIRMED'',''SHIPPED'',''RECEIVED'',''CANCELLED'',''PARTIALLY_RECEIVED'')),
          total_amount numeric(14,2) NOT NULL DEFAULT 0, created_by uuid REFERENCES auth.users(id), created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now())',ns,ns);
        EXECUTE format('CREATE TABLE %I.purchase_order_items (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(), purchase_order_id uuid NOT NULL REFERENCES %I.purchase_orders(id) ON DELETE RESTRICT,
          item_id uuid NOT NULL REFERENCES %I.inventory_items(id), quantity_ordered numeric(14,3) NOT NULL CHECK(quantity_ordered > 0),
          quantity_received numeric(14,3) NOT NULL DEFAULT 0 CHECK(quantity_received >= 0 AND quantity_received <= quantity_ordered),
          unit_cost numeric(12,2) NOT NULL CHECK(unit_cost >= 0), line_total numeric(14,2) GENERATED ALWAYS AS (quantity_ordered*unit_cost) STORED, UNIQUE(purchase_order_id,item_id))',ns,ns,ns);
        FOREACH side IN ARRAY ARRAY['inventory_items','inventory_batches','inventory_transactions','purchase_orders','purchase_order_items'] LOOP
          EXECUTE format('ALTER TABLE %I.%I ENABLE ROW LEVEL SECURITY',ns,side);
          policy_expr := CASE side
            WHEN 'inventory_items' THEN 'store_id IN (SELECT store_id FROM public.inventory_store_memberships WHERE user_id=auth.uid())'
            WHEN 'inventory_batches' THEN format('EXISTS (SELECT 1 FROM %I.inventory_items i JOIN public.inventory_store_memberships m ON m.store_id=i.store_id WHERE i.id=item_id AND m.user_id=auth.uid())',ns)
            WHEN 'inventory_transactions' THEN 'store_id IN (SELECT store_id FROM public.inventory_store_memberships WHERE user_id=auth.uid())'
            WHEN 'purchase_orders' THEN 'store_id IN (SELECT store_id FROM public.inventory_store_memberships WHERE user_id=auth.uid())'
            ELSE format('EXISTS (SELECT 1 FROM %I.purchase_orders p JOIN public.inventory_store_memberships m ON m.store_id=p.store_id WHERE p.id=purchase_order_id AND m.user_id=auth.uid())',ns)
          END;
          EXECUTE format('CREATE POLICY %I ON %I.%I USING (%s) WITH CHECK (%s)','tenant_'||side,ns,side,policy_expr,policy_expr);
        END LOOP;
        EXECUTE format('ALTER TABLE %I.suppliers ENABLE ROW LEVEL SECURITY',ns);
        EXECUTE format('ALTER TABLE %I.suppliers ADD COLUMN store_id uuid NOT NULL REFERENCES public.inventory_stores(id)',ns);
        EXECUTE format('ALTER TABLE %I.suppliers ENABLE ROW LEVEL SECURITY',ns);
        EXECUTE format('CREATE POLICY tenant_suppliers ON %I.suppliers USING (store_id IN (SELECT store_id FROM public.inventory_store_memberships WHERE user_id=auth.uid())) WITH CHECK (store_id IN (SELECT store_id FROM public.inventory_store_memberships WHERE user_id=auth.uid()))',ns);
      ELSE
        EXECUTE format('ALTER TABLE %I.products ENABLE ROW LEVEL SECURITY',ns);
        EXECUTE format('CREATE POLICY catalog_read ON %I.products FOR SELECT TO authenticated USING (is_active)',ns);
        EXECUTE format('ALTER TABLE %I.suppliers ENABLE ROW LEVEL SECURITY',ns);
        EXECUTE format('CREATE POLICY catalog_suppliers_read ON %I.suppliers FOR SELECT TO authenticated USING (is_active)',ns);
      END IF;
    END LOOP;
    EXECUTE format('ALTER TABLE %I.inventory_items ADD CONSTRAINT fk_master_product FOREIGN KEY(master_product_id) REFERENCES %I.products(id)',kind||'_local',kind||'_master');
    IF kind='medical' THEN EXECUTE 'CREATE TABLE medical_local.medical_batch_details (batch_id uuid PRIMARY KEY REFERENCES medical_local.inventory_batches(id) ON DELETE CASCADE, manufacturer text, storage_conditions text, prescription_required boolean, schedule text)'; END IF;
    IF kind='food' THEN EXECUTE 'CREATE TABLE food_local.food_batch_details (batch_id uuid PRIMARY KEY REFERENCES food_local.inventory_batches(id) ON DELETE CASCADE, best_before date, storage_type text)'; END IF;
  END LOOP;
END $$;

GRANT USAGE ON SCHEMA grocery_master,grocery_local,medical_master,medical_local,food_master,food_local,stationery_master,stationery_local TO authenticated, service_role;
GRANT SELECT ON ALL TABLES IN SCHEMA grocery_master,medical_master,food_master,stationery_master TO authenticated;
GRANT SELECT,INSERT,UPDATE,DELETE ON grocery_local.suppliers,grocery_local.inventory_items,grocery_local.inventory_batches,grocery_local.inventory_transactions,grocery_local.purchase_orders,grocery_local.purchase_order_items,medical_local.suppliers,medical_local.inventory_items,medical_local.inventory_batches,medical_local.inventory_transactions,medical_local.purchase_orders,medical_local.purchase_order_items,food_local.suppliers,food_local.inventory_items,food_local.inventory_batches,food_local.inventory_transactions,food_local.purchase_orders,food_local.purchase_order_items,stationery_local.suppliers,stationery_local.inventory_items,stationery_local.inventory_batches,stationery_local.inventory_transactions,stationery_local.purchase_orders,stationery_local.purchase_order_items TO authenticated, service_role;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA grocery_local,medical_local,food_local,stationery_local TO authenticated, service_role;




