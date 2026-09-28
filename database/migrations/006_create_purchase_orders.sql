-- ============================================================================
-- MIGRATION 006: PURCHASE ORDER TABLES (all 4 local schemas)
-- ============================================================================
-- Complete PO lifecycle:
--   DRAFT → PENDING → CONFIRMED → SHIPPED → RECEIVED / PARTIALLY_RECEIVED
--   Any state → CANCELLED
-- ============================================================================

DO $$
DECLARE
  kinds TEXT[] := ARRAY['grocery', 'medical', 'food', 'stationery'];
  kind  TEXT;
  ns    TEXT;
BEGIN
  FOREACH kind IN ARRAY kinds LOOP
    ns := kind || '_local';

    -- -----------------------------------------------------------------
    -- purchase_orders: header
    -- -----------------------------------------------------------------
    EXECUTE format($sql$
      CREATE TABLE IF NOT EXISTS %I.purchase_orders (
        id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        store_id               UUID NOT NULL REFERENCES public.stores(id),
        supplier_id            UUID NOT NULL REFERENCES %I.suppliers(id),
        order_number           TEXT,
        order_date             TIMESTAMPTZ NOT NULL DEFAULT now(),
        expected_delivery_date DATE,
        status                 TEXT NOT NULL DEFAULT 'PENDING'
                               CHECK (status IN (
                                 'DRAFT','PENDING','CONFIRMED','SHIPPED',
                                 'RECEIVED','CANCELLED','PARTIALLY_RECEIVED'
                               )),
        total_amount           NUMERIC(14,2) NOT NULL DEFAULT 0,
        notes                  TEXT,
        created_by             UUID REFERENCES auth.users(id),
        created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at             TIMESTAMPTZ NOT NULL DEFAULT now()
      )
    $sql$, ns, ns);

    -- Indexes on purchase_orders
    EXECUTE format(
      'CREATE INDEX IF NOT EXISTS %I ON %I.purchase_orders(store_id, status)',
      'ix_' || ns || '_po_status', ns
    );
    EXECUTE format(
      'CREATE INDEX IF NOT EXISTS %I ON %I.purchase_orders(supplier_id)',
      'ix_' || ns || '_po_supplier', ns
    );
    EXECUTE format(
      'CREATE INDEX IF NOT EXISTS %I ON %I.purchase_orders(order_date DESC)',
      'ix_' || ns || '_po_date', ns
    );

    -- -----------------------------------------------------------------
    -- purchase_order_items: line items
    -- -----------------------------------------------------------------
    EXECUTE format($sql$
      CREATE TABLE IF NOT EXISTS %I.purchase_order_items (
        id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        purchase_order_id UUID NOT NULL REFERENCES %I.purchase_orders(id) ON DELETE RESTRICT,
        item_id           UUID NOT NULL REFERENCES %I.inventory_items(id),
        master_product_id UUID,
        quantity_ordered  NUMERIC(14,3) NOT NULL CHECK (quantity_ordered > 0),
        quantity_received NUMERIC(14,3) NOT NULL DEFAULT 0
                          CHECK (quantity_received >= 0),
        unit_cost         NUMERIC(12,2) NOT NULL CHECK (unit_cost >= 0),
        line_total        NUMERIC(14,2) GENERATED ALWAYS AS (quantity_ordered * unit_cost) STORED,
        notes             TEXT,
        UNIQUE (purchase_order_id, item_id)
      )
    $sql$, ns, ns, ns);

    -- -----------------------------------------------------------------
    -- RLS on purchase_orders
    -- -----------------------------------------------------------------
    EXECUTE format('ALTER TABLE %I.purchase_orders ENABLE ROW LEVEL SECURITY', ns);
    EXECUTE format('DROP POLICY IF EXISTS tenant_po ON %I.purchase_orders', ns);
    EXECUTE format($p$
      CREATE POLICY tenant_po ON %I.purchase_orders
        USING (store_id IN (
          SELECT store_id FROM public.store_memberships WHERE user_id = auth.uid()
        ))
        WITH CHECK (store_id IN (
          SELECT store_id FROM public.store_memberships WHERE user_id = auth.uid()
        ))
    $p$, ns);

    -- RLS on purchase_order_items
    EXECUTE format('ALTER TABLE %I.purchase_order_items ENABLE ROW LEVEL SECURITY', ns);
    EXECUTE format('DROP POLICY IF EXISTS tenant_poi ON %I.purchase_order_items', ns);
    EXECUTE format($p$
      CREATE POLICY tenant_poi ON %I.purchase_order_items
        USING (
          EXISTS (
            SELECT 1 FROM %I.purchase_orders po
            JOIN public.store_memberships m ON m.store_id = po.store_id
            WHERE po.id = purchase_order_id AND m.user_id = auth.uid()
          )
        )
        WITH CHECK (
          EXISTS (
            SELECT 1 FROM %I.purchase_orders po
            JOIN public.store_memberships m ON m.store_id = po.store_id
            WHERE po.id = purchase_order_id AND m.user_id = auth.uid()
          )
        )
    $p$, ns, ns, ns);

    -- Grants
    EXECUTE format(
      'GRANT SELECT, INSERT, UPDATE ON %I.purchase_orders TO authenticated, service_role', ns
    );
    EXECUTE format(
      'GRANT SELECT, INSERT, UPDATE ON %I.purchase_order_items TO authenticated, service_role', ns
    );

  END LOOP;
END $$;
