-- ============================================================================
-- MIGRATION 002: SUPPLIER TABLES (all 8 schemas)
-- ============================================================================
-- Each schema gets its own suppliers table. Master suppliers represent the
-- global wholesaler directory; local suppliers are store-scoped.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- Helper: create the supplier table in a given schema
-- ---------------------------------------------------------------------------
DO $$
DECLARE
  schemas TEXT[] := ARRAY[
    'grocery_master', 'grocery_local',
    'medical_master', 'medical_local',
    'food_master',    'food_local',
    'stationery_master', 'stationery_local'
  ];
  ns TEXT;
BEGIN
  FOREACH ns IN ARRAY schemas LOOP

    EXECUTE format($sql$
      CREATE TABLE IF NOT EXISTS %I.suppliers (
        id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        supplier_code   TEXT NOT NULL,
        supplier_name   TEXT NOT NULL,
        contact_person  TEXT,
        phone           TEXT,
        email           TEXT,
        address         TEXT,
        city            TEXT,
        state           TEXT,
        pincode         TEXT,
        gst_number      TEXT,
        payment_terms   TEXT,
        is_active       BOOLEAN NOT NULL DEFAULT TRUE,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE (supplier_code)
      )
    $sql$, ns);

    -- Index on supplier name for search
    EXECUTE format(
      'CREATE INDEX IF NOT EXISTS %I ON %I.suppliers(supplier_name)',
      'ix_' || ns || '_sup_name', ns
    );

    -- For local schemas, add store_id column for multi-store scoping
    IF ns LIKE '%_local' THEN
      BEGIN
        EXECUTE format(
          'ALTER TABLE %I.suppliers ADD COLUMN store_id UUID NOT NULL REFERENCES public.stores(id)',
          ns
        );
      EXCEPTION WHEN duplicate_column THEN NULL;
      END;

      -- Drop the plain unique on supplier_code, replace with per-store unique
      BEGIN
        EXECUTE format(
          'ALTER TABLE %I.suppliers DROP CONSTRAINT IF EXISTS suppliers_supplier_code_key', ns
        );
        EXECUTE format(
          'ALTER TABLE %I.suppliers ADD CONSTRAINT uq_%s_supplier_code UNIQUE (store_id, supplier_code)',
          ns, ns
        );
      EXCEPTION WHEN OTHERS THEN NULL;
      END;

      -- RLS on local suppliers
      EXECUTE format('ALTER TABLE %I.suppliers ENABLE ROW LEVEL SECURITY', ns);
      EXECUTE format(
        'DROP POLICY IF EXISTS tenant_suppliers ON %I.suppliers', ns
      );
      EXECUTE format($p$
        CREATE POLICY tenant_suppliers ON %I.suppliers
          USING (store_id IN (SELECT store_id FROM public.store_memberships WHERE user_id = auth.uid()))
          WITH CHECK (store_id IN (SELECT store_id FROM public.store_memberships WHERE user_id = auth.uid()))
      $p$, ns);

      -- Grants
      EXECUTE format(
        'GRANT SELECT, INSERT, UPDATE, DELETE ON %I.suppliers TO authenticated, service_role', ns
      );

    ELSE
      -- Master suppliers: read-only for authenticated, full for service_role
      EXECUTE format('ALTER TABLE %I.suppliers ENABLE ROW LEVEL SECURITY', ns);
      EXECUTE format(
        'DROP POLICY IF EXISTS catalog_suppliers_read ON %I.suppliers', ns
      );
      EXECUTE format($p$
        CREATE POLICY catalog_suppliers_read ON %I.suppliers
          FOR SELECT TO authenticated
          USING (is_active)
      $p$, ns);

      EXECUTE format('GRANT SELECT ON %I.suppliers TO authenticated', ns);
      EXECUTE format('GRANT ALL ON %I.suppliers TO service_role', ns);
    END IF;

  END LOOP;
END $$;
