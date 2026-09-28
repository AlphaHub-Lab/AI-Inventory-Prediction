-- ============================================================================
-- MIGRATION 005: INVENTORY TRANSACTIONS (all 4 local schemas)
-- ============================================================================
-- Immutable record of every stock change. No stock mutation should ever
-- happen without a corresponding transaction row.
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
      CREATE TABLE IF NOT EXISTS %I.inventory_transactions (
        id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        store_id         UUID NOT NULL REFERENCES public.stores(id),
        item_id          UUID NOT NULL REFERENCES %I.inventory_items(id),
        batch_id         UUID REFERENCES %I.inventory_batches(id),
        transaction_type TEXT NOT NULL CHECK (transaction_type IN (
          'PURCHASE', 'SALE', 'RETURN', 'DAMAGE',
          'EXPIRED', 'ADJUSTMENT', 'TRANSFER_IN', 'TRANSFER_OUT'
        )),
        quantity_delta   NUMERIC(14,3) NOT NULL CHECK (quantity_delta <> 0),
        previous_stock   NUMERIC(14,3) NOT NULL,
        new_stock        NUMERIC(14,3) NOT NULL,
        reference_id     UUID,          -- FK to purchase_order, sale, etc.
        reference_type   TEXT,          -- 'purchase_order', 'sale', 'manual', etc.
        note             TEXT,
        created_by       UUID REFERENCES auth.users(id),
        created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
      )
    $sql$, ns, ns, ns);

    -- Indexes
    EXECUTE format(
      'CREATE INDEX IF NOT EXISTS %I ON %I.inventory_transactions(item_id, created_at DESC)',
      'ix_' || ns || '_txn_item', ns
    );
    EXECUTE format(
      'CREATE INDEX IF NOT EXISTS %I ON %I.inventory_transactions(store_id, created_at DESC)',
      'ix_' || ns || '_txn_store', ns
    );
    EXECUTE format(
      'CREATE INDEX IF NOT EXISTS %I ON %I.inventory_transactions(transaction_type)',
      'ix_' || ns || '_txn_type', ns
    );
    EXECUTE format(
      'CREATE INDEX IF NOT EXISTS %I ON %I.inventory_transactions(reference_id) WHERE reference_id IS NOT NULL',
      'ix_' || ns || '_txn_ref', ns
    );
    EXECUTE format(
      'CREATE INDEX IF NOT EXISTS %I ON %I.inventory_transactions(created_by)',
      'ix_' || ns || '_txn_user', ns
    );

    -- RLS
    EXECUTE format('ALTER TABLE %I.inventory_transactions ENABLE ROW LEVEL SECURITY', ns);
    EXECUTE format('DROP POLICY IF EXISTS tenant_txn ON %I.inventory_transactions', ns);
    EXECUTE format($p$
      CREATE POLICY tenant_txn ON %I.inventory_transactions
        USING (store_id IN (
          SELECT store_id FROM public.store_memberships WHERE user_id = auth.uid()
        ))
    $p$, ns);

    -- Authenticated can only read (transactions are created by server functions)
    EXECUTE format(
      'GRANT SELECT ON %I.inventory_transactions TO authenticated', ns
    );
    EXECUTE format(
      'GRANT ALL ON %I.inventory_transactions TO service_role', ns
    );

  END LOOP;
END $$;
