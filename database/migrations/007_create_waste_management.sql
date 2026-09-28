-- ============================================================================
-- MIGRATION 007: WASTE MANAGEMENT TABLES (all 4 local schemas)
-- ============================================================================
-- Tracks waste, spoilage, expiry and damage for analytics/AI forecasting.
-- Especially important for grocery, food and medical stores.
-- ============================================================================

DO $$
DECLARE
  kinds TEXT[] := ARRAY['grocery', 'medical', 'food', 'stationery'];
  kind  TEXT;
  ns    TEXT;
BEGIN
  FOREACH kind IN ARRAY kinds LOOP
    ns := kind || '_local';

    EXECUTE format($sql$
      CREATE TABLE IF NOT EXISTS %I.waste_records (
        id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        store_id            UUID NOT NULL REFERENCES public.stores(id),
        item_id             UUID NOT NULL REFERENCES %I.inventory_items(id),
        batch_id            UUID REFERENCES %I.inventory_batches(id),
        quantity            NUMERIC(14,3) NOT NULL CHECK (quantity > 0),
        reason              TEXT NOT NULL CHECK (reason IN (
          'EXPIRED', 'DAMAGED', 'SPOILED', 'RETURNED', 'OTHER'
        )),
        batch_number        TEXT,
        expiry_date         DATE,
        cost_loss           NUMERIC(14,2) NOT NULL DEFAULT 0,
        notes               TEXT,
        created_by          UUID REFERENCES auth.users(id),
        created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
      )
    $sql$, ns, ns, ns);

    -- Indexes
    EXECUTE format(
      'CREATE INDEX IF NOT EXISTS %I ON %I.waste_records(store_id, created_at DESC)',
      'ix_' || ns || '_waste_store', ns
    );
    EXECUTE format(
      'CREATE INDEX IF NOT EXISTS %I ON %I.waste_records(reason)',
      'ix_' || ns || '_waste_reason', ns
    );
    EXECUTE format(
      'CREATE INDEX IF NOT EXISTS %I ON %I.waste_records(item_id)',
      'ix_' || ns || '_waste_item', ns
    );

    -- RLS
    EXECUTE format('ALTER TABLE %I.waste_records ENABLE ROW LEVEL SECURITY', ns);
    EXECUTE format('DROP POLICY IF EXISTS tenant_waste ON %I.waste_records', ns);
    EXECUTE format($p$
      CREATE POLICY tenant_waste ON %I.waste_records
        USING (store_id IN (
          SELECT store_id FROM public.store_memberships WHERE user_id = auth.uid()
        ))
        WITH CHECK (store_id IN (
          SELECT store_id FROM public.store_memberships WHERE user_id = auth.uid()
        ))
    $p$, ns);

    EXECUTE format(
      'GRANT SELECT, INSERT ON %I.waste_records TO authenticated, service_role', ns
    );

  END LOOP;
END $$;
