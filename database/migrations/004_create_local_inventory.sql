-- ============================================================================
-- MIGRATION 004: LOCAL INVENTORY TABLES (all 4 local schemas)
-- ============================================================================
-- Creates:
--   inventory_items   – per-store product records (linked to master_product_id)
--   inventory_batches – batch-level quantities + expiry tracking
--   inventory_stock   – aggregate view (current_stock, available_stock)
-- ============================================================================

DO $$
DECLARE
  kinds TEXT[] := ARRAY['grocery', 'medical', 'food', 'stationery'];
  kind  TEXT;
  ns    TEXT;
  ms    TEXT;
BEGIN
  FOREACH kind IN ARRAY kinds LOOP
    ns := kind || '_local';
    ms := kind || '_master';

    -- -----------------------------------------------------------------
    -- inventory_items: per-store product inventory records
    -- -----------------------------------------------------------------
    EXECUTE format($sql$
      CREATE TABLE IF NOT EXISTS %I.inventory_items (
        id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        store_id          UUID NOT NULL REFERENCES public.stores(id),
        master_product_id UUID REFERENCES %I.products(id),
        sku               TEXT NOT NULL,
        barcode           TEXT,
        product_name      TEXT NOT NULL,
        brand             TEXT,
        category          TEXT,
        subcategory       TEXT,
        reserved_stock    NUMERIC(14,3) NOT NULL DEFAULT 0 CHECK (reserved_stock >= 0),
        reorder_level     NUMERIC(14,3) NOT NULL DEFAULT 0 CHECK (reorder_level >= 0),
        minimum_stock     NUMERIC(14,3) NOT NULL DEFAULT 0,
        maximum_stock     NUMERIC(14,3),
        cost_price        NUMERIC(12,2) NOT NULL DEFAULT 0,
        selling_price     NUMERIC(12,2) NOT NULL DEFAULT 0,
        mrp               NUMERIC(12,2),
        gst_percentage    NUMERIC(5,2) NOT NULL DEFAULT 0
                          CHECK (gst_percentage BETWEEN 0 AND 100),
        supplier_id       UUID REFERENCES %I.suppliers(id),
        storage_location  TEXT,
        stock_status      TEXT NOT NULL DEFAULT 'OUT_OF_STOCK'
                          CHECK (stock_status IN (
                            'IN_STOCK','LOW_STOCK','OUT_OF_STOCK',
                            'EXPIRED','DAMAGED','BLOCKED'
                          )),
        created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),

        -- Prevent duplicate products per store
        UNIQUE (store_id, sku),
        UNIQUE (store_id, master_product_id)
      )
    $sql$, ns, ms, ns);

    -- Indexes on inventory_items
    EXECUTE format(
      'CREATE INDEX IF NOT EXISTS %I ON %I.inventory_items(store_id, product_name)',
      'ix_' || ns || '_inv_name', ns
    );
    EXECUTE format(
      'CREATE INDEX IF NOT EXISTS %I ON %I.inventory_items(store_id, barcode) WHERE barcode IS NOT NULL',
      'ix_' || ns || '_inv_barcode', ns
    );
    EXECUTE format(
      'CREATE INDEX IF NOT EXISTS %I ON %I.inventory_items(store_id, category)',
      'ix_' || ns || '_inv_category', ns
    );
    EXECUTE format(
      'CREATE INDEX IF NOT EXISTS %I ON %I.inventory_items(master_product_id)',
      'ix_' || ns || '_inv_master', ns
    );
    EXECUTE format(
      'CREATE INDEX IF NOT EXISTS %I ON %I.inventory_items(supplier_id)',
      'ix_' || ns || '_inv_supplier', ns
    );
    EXECUTE format(
      'CREATE INDEX IF NOT EXISTS %I ON %I.inventory_items(stock_status)',
      'ix_' || ns || '_inv_status', ns
    );

    -- Full-text search on local inventory
    EXECUTE format($idx$
      CREATE INDEX IF NOT EXISTS %I ON %I.inventory_items
        USING gin(
          to_tsvector('simple',
            coalesce(product_name, '') || ' ' ||
            coalesce(brand, '')        || ' ' ||
            coalesce(category, '')     || ' ' ||
            sku
          )
        )
    $idx$, 'ix_' || ns || '_inv_search', ns);

    -- -----------------------------------------------------------------
    -- inventory_batches: batch-level stock with expiry tracking
    -- -----------------------------------------------------------------
    EXECUTE format($sql$
      CREATE TABLE IF NOT EXISTS %I.inventory_batches (
        id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        item_id            UUID NOT NULL REFERENCES %I.inventory_items(id) ON DELETE CASCADE,
        batch_number       TEXT NOT NULL DEFAULT '',
        manufacturing_date DATE,
        expiry_date        DATE,
        quantity           NUMERIC(14,3) NOT NULL DEFAULT 0 CHECK (quantity >= 0),
        created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),

        -- Same item + batch + expiry = one row
        UNIQUE (item_id, batch_number, expiry_date),
        -- Expiry must be after manufacturing
        CHECK (expiry_date IS NULL OR manufacturing_date IS NULL
               OR expiry_date >= manufacturing_date)
      )
    $sql$, ns, ns);

    -- Index for expiry queries
    EXECUTE format(
      'CREATE INDEX IF NOT EXISTS %I ON %I.inventory_batches(expiry_date) WHERE quantity > 0',
      'ix_' || ns || '_batch_expiry', ns
    );
    EXECUTE format(
      'CREATE INDEX IF NOT EXISTS %I ON %I.inventory_batches(item_id)',
      'ix_' || ns || '_batch_item', ns
    );

    -- -----------------------------------------------------------------
    -- inventory_stock: aggregate view
    -- -----------------------------------------------------------------
    EXECUTE format($sql$
      CREATE OR REPLACE VIEW %I.inventory_stock
      WITH (security_invoker = true) AS
      SELECT
        i.*,
        COALESCE(SUM(b.quantity), 0)                    AS current_stock,
        COALESCE(SUM(b.quantity), 0) - i.reserved_stock AS available_stock
      FROM %I.inventory_items i
      LEFT JOIN %I.inventory_batches b ON b.item_id = i.id
      GROUP BY i.id
    $sql$, ns, ns, ns);

    -- -----------------------------------------------------------------
    -- RLS on inventory_items
    -- -----------------------------------------------------------------
    EXECUTE format('ALTER TABLE %I.inventory_items ENABLE ROW LEVEL SECURITY', ns);
    EXECUTE format('DROP POLICY IF EXISTS tenant_inventory ON %I.inventory_items', ns);
    EXECUTE format($p$
      CREATE POLICY tenant_inventory ON %I.inventory_items
        USING (store_id IN (
          SELECT store_id FROM public.store_memberships WHERE user_id = auth.uid()
        ))
        WITH CHECK (store_id IN (
          SELECT store_id FROM public.store_memberships WHERE user_id = auth.uid()
        ))
    $p$, ns);

    -- RLS on inventory_batches
    EXECUTE format('ALTER TABLE %I.inventory_batches ENABLE ROW LEVEL SECURITY', ns);
    EXECUTE format('DROP POLICY IF EXISTS tenant_batches ON %I.inventory_batches', ns);
    EXECUTE format($p$
      CREATE POLICY tenant_batches ON %I.inventory_batches
        USING (
          EXISTS (
            SELECT 1 FROM %I.inventory_items i
            JOIN public.store_memberships m ON m.store_id = i.store_id
            WHERE i.id = item_id AND m.user_id = auth.uid()
          )
        )
    $p$, ns, ns);

    -- Grants
    EXECUTE format(
      'GRANT SELECT, INSERT, UPDATE, DELETE ON %I.inventory_items TO authenticated, service_role',
      ns
    );
    EXECUTE format(
      'GRANT SELECT ON %I.inventory_batches TO authenticated',
      ns
    );
    EXECUTE format(
      'GRANT ALL ON %I.inventory_batches TO service_role',
      ns
    );

  END LOOP;
END $$;

-- ---------------------------------------------------------------------------
-- Store-type-specific local extensions
-- ---------------------------------------------------------------------------

-- MEDICAL LOCAL: additional batch-level medical details
CREATE TABLE IF NOT EXISTS medical_local.medical_batch_details (
  batch_id              UUID PRIMARY KEY REFERENCES medical_local.inventory_batches(id) ON DELETE CASCADE,
  manufacturer          TEXT,
  storage_conditions    TEXT,
  prescription_required BOOLEAN,
  schedule              TEXT,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE medical_local.medical_batch_details ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_med_batch ON medical_local.medical_batch_details;
CREATE POLICY tenant_med_batch ON medical_local.medical_batch_details
  USING (
    EXISTS (
      SELECT 1 FROM medical_local.inventory_batches b
      JOIN medical_local.inventory_items i ON i.id = b.item_id
      JOIN public.store_memberships m ON m.store_id = i.store_id
      WHERE b.id = batch_id AND m.user_id = auth.uid()
    )
  );
GRANT SELECT ON medical_local.medical_batch_details TO authenticated;
GRANT ALL ON medical_local.medical_batch_details TO service_role;

-- FOOD LOCAL: additional batch-level food details
CREATE TABLE IF NOT EXISTS food_local.food_batch_details (
  batch_id      UUID PRIMARY KEY REFERENCES food_local.inventory_batches(id) ON DELETE CASCADE,
  best_before   DATE,
  storage_type  TEXT,                  -- Ambient, Chilled, Frozen
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE food_local.food_batch_details ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_food_batch ON food_local.food_batch_details;
CREATE POLICY tenant_food_batch ON food_local.food_batch_details
  USING (
    EXISTS (
      SELECT 1 FROM food_local.inventory_batches b
      JOIN food_local.inventory_items i ON i.id = b.item_id
      JOIN public.store_memberships m ON m.store_id = i.store_id
      WHERE b.id = batch_id AND m.user_id = auth.uid()
    )
  );
GRANT SELECT ON food_local.food_batch_details TO authenticated;
GRANT ALL ON food_local.food_batch_details TO service_role;
