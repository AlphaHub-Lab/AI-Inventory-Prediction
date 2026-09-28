-- ============================================================================
-- MIGRATION 003: MASTER PRODUCT TABLES (all 4 master schemas)
-- ============================================================================
-- Common product structure + store-type-specific extension tables.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- Common products table in each master schema
-- ---------------------------------------------------------------------------
DO $$
DECLARE
  kinds TEXT[] := ARRAY['grocery', 'medical', 'food', 'stationery'];
  kind  TEXT;
  ns    TEXT;
BEGIN
  FOREACH kind IN ARRAY kinds LOOP
    ns := kind || '_master';

    -- Core products table
    EXECUTE format($sql$
      CREATE TABLE IF NOT EXISTS %I.products (
        id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        sku                   TEXT NOT NULL,
        barcode               TEXT,
        product_name          TEXT NOT NULL,
        brand                 TEXT,
        category              TEXT,
        subcategory           TEXT,
        description           TEXT,
        unit                  TEXT NOT NULL DEFAULT 'unit',
        pack_size             TEXT,
        mrp                   NUMERIC(12,2) CHECK (mrp >= 0),
        default_cost_price    NUMERIC(12,2) CHECK (default_cost_price >= 0),
        default_selling_price NUMERIC(12,2) CHECK (default_selling_price >= 0),
        gst_percentage        NUMERIC(5,2) NOT NULL DEFAULT 0
                              CHECK (gst_percentage BETWEEN 0 AND 100),
        supplier_id           UUID REFERENCES %I.suppliers(id),
        is_active             BOOLEAN NOT NULL DEFAULT TRUE,
        created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE (sku)
      )
    $sql$, ns, ns);

    -- Indexes on products
    EXECUTE format(
      'CREATE INDEX IF NOT EXISTS %I ON %I.products(product_name)',
      'ix_' || ns || '_prod_name', ns
    );
    EXECUTE format(
      'CREATE INDEX IF NOT EXISTS %I ON %I.products(barcode) WHERE barcode IS NOT NULL',
      'ix_' || ns || '_prod_barcode', ns
    );
    EXECUTE format(
      'CREATE INDEX IF NOT EXISTS %I ON %I.products(brand)',
      'ix_' || ns || '_prod_brand', ns
    );
    EXECUTE format(
      'CREATE INDEX IF NOT EXISTS %I ON %I.products(category)',
      'ix_' || ns || '_prod_category', ns
    );
    EXECUTE format(
      'CREATE INDEX IF NOT EXISTS %I ON %I.products(supplier_id)',
      'ix_' || ns || '_prod_supplier', ns
    );

    -- Full-text search index (product_name + brand + category + sku)
    EXECUTE format($idx$
      CREATE INDEX IF NOT EXISTS %I ON %I.products
        USING gin(
          to_tsvector('simple',
            coalesce(product_name, '') || ' ' ||
            coalesce(brand, '')        || ' ' ||
            coalesce(category, '')     || ' ' ||
            sku
          )
        )
    $idx$, 'ix_' || ns || '_prod_search', ns);

    -- Product-supplier many-to-many
    EXECUTE format($sql$
      CREATE TABLE IF NOT EXISTS %I.product_suppliers (
        product_id    UUID NOT NULL REFERENCES %I.products(id) ON DELETE CASCADE,
        supplier_id   UUID NOT NULL REFERENCES %I.suppliers(id),
        supplier_sku  TEXT,
        cost_price    NUMERIC(12,2) CHECK (cost_price >= 0),
        lead_time_days INTEGER CHECK (lead_time_days >= 0),
        is_preferred  BOOLEAN NOT NULL DEFAULT FALSE,
        created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (product_id, supplier_id)
      )
    $sql$, ns, ns, ns);

    -- RLS: master products are read-only for authenticated users
    EXECUTE format('ALTER TABLE %I.products ENABLE ROW LEVEL SECURITY', ns);
    EXECUTE format('DROP POLICY IF EXISTS catalog_read ON %I.products', ns);
    EXECUTE format($p$
      CREATE POLICY catalog_read ON %I.products
        FOR SELECT TO authenticated
        USING (is_active)
    $p$, ns);

    EXECUTE format('ALTER TABLE %I.product_suppliers ENABLE ROW LEVEL SECURITY', ns);
    EXECUTE format('DROP POLICY IF EXISTS catalog_ps_read ON %I.product_suppliers', ns);
    EXECUTE format($p$
      CREATE POLICY catalog_ps_read ON %I.product_suppliers
        FOR SELECT TO authenticated
        USING (TRUE)
    $p$, ns);

    -- Grants
    EXECUTE format('GRANT SELECT ON %I.products TO authenticated', ns);
    EXECUTE format('GRANT SELECT ON %I.product_suppliers TO authenticated', ns);
    EXECUTE format('GRANT ALL ON %I.products TO service_role', ns);
    EXECUTE format('GRANT ALL ON %I.product_suppliers TO service_role', ns);

  END LOOP;
END $$;

-- ---------------------------------------------------------------------------
-- Store-type-specific extension tables
-- ---------------------------------------------------------------------------

-- MEDICAL: additional medicine details
CREATE TABLE IF NOT EXISTS medical_master.medical_product_details (
  product_id           UUID PRIMARY KEY REFERENCES medical_master.products(id) ON DELETE CASCADE,
  generic_name         TEXT,
  drug_type            TEXT,
  dosage_form          TEXT,               -- Tablet, Capsule, Syrup, etc.
  strength             TEXT,               -- 500mg, 10ml, etc.
  manufacturer         TEXT,
  prescription_required BOOLEAN DEFAULT FALSE,
  schedule             TEXT,               -- H, H1, X, etc.
  storage_conditions   TEXT,               -- Room temp, Refrigerated, etc.
  composition          TEXT,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE medical_master.medical_product_details ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS catalog_med_read ON medical_master.medical_product_details;
CREATE POLICY catalog_med_read ON medical_master.medical_product_details
  FOR SELECT TO authenticated USING (TRUE);
GRANT SELECT ON medical_master.medical_product_details TO authenticated;
GRANT ALL ON medical_master.medical_product_details TO service_role;

-- FOOD: additional food details
CREATE TABLE IF NOT EXISTS food_master.food_product_details (
  product_id        UUID PRIMARY KEY REFERENCES food_master.products(id) ON DELETE CASCADE,
  food_type         TEXT,               -- Raw, Packaged, Ready-to-eat, Frozen, etc.
  storage_type      TEXT,               -- Ambient, Chilled, Frozen
  best_before_days  INTEGER CHECK (best_before_days IS NULL OR best_before_days >= 0),
  allergens         TEXT,
  is_vegetarian     BOOLEAN,
  fssai_license     TEXT,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE food_master.food_product_details ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS catalog_food_read ON food_master.food_product_details;
CREATE POLICY catalog_food_read ON food_master.food_product_details
  FOR SELECT TO authenticated USING (TRUE);
GRANT SELECT ON food_master.food_product_details TO authenticated;
GRANT ALL ON food_master.food_product_details TO service_role;

-- STATIONERY: additional stationery details
CREATE TABLE IF NOT EXISTS stationery_master.stationery_product_details (
  product_id  UUID PRIMARY KEY REFERENCES stationery_master.products(id) ON DELETE CASCADE,
  color       TEXT,
  size        TEXT,
  material    TEXT,
  grade       TEXT,               -- For pencils (HB, 2B, etc.)
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE stationery_master.stationery_product_details ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS catalog_stat_read ON stationery_master.stationery_product_details;
CREATE POLICY catalog_stat_read ON stationery_master.stationery_product_details
  FOR SELECT TO authenticated USING (TRUE);
GRANT SELECT ON stationery_master.stationery_product_details TO authenticated;
GRANT ALL ON stationery_master.stationery_product_details TO service_role;
