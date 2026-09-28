-- ============================================================================
-- MIGRATION 010: ENTERPRISE CORPORATE STANDARDS
-- ============================================================================
-- Elevates the 4-module Local + Master Multi-Schema architecture to corporate standards:
--   1. Automated updated_at triggers across all mutable tables
--   2. Sub-millisecond Trigram GIN indexes for fuzzy search over lakhs of records
--   3. High-throughput bulk master ingestion procedure (bulk_upsert_master_products)
--   4. Comprehensive enterprise data dictionary (comments on schemas, tables, views)
--   5. Full PostgREST API permissions and schema reload notification
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 1. Automated Timestamp Trigger Function & Triggers
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.updated_at = clock_timestamp();
  RETURN NEW;
END;
$$;

COMMENT ON FUNCTION public.set_updated_at() IS 
  'Enterprise trigger function guaranteeing updated_at accuracy on every row mutation.';

-- Apply triggers across all schemas and tables with updated_at
DO $$
DECLARE
  kinds TEXT[] := ARRAY['grocery', 'medical', 'food', 'stationery'];
  kind  TEXT;
  m_ns  TEXT;
  l_ns  TEXT;
BEGIN
  -- 1. Public schema
  DROP TRIGGER IF EXISTS trg_stores_updated_at ON public.stores;
  CREATE TRIGGER trg_stores_updated_at
    BEFORE UPDATE ON public.stores
    FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

  -- 2. Master and Local schemas
  FOREACH kind IN ARRAY kinds LOOP
    m_ns := kind || '_master';
    l_ns := kind || '_local';

    -- Master suppliers
    EXECUTE format('DROP TRIGGER IF EXISTS trg_%I_suppliers_updated ON %I.suppliers', m_ns, m_ns);
    EXECUTE format('CREATE TRIGGER trg_%I_suppliers_updated BEFORE UPDATE ON %I.suppliers FOR EACH ROW EXECUTE FUNCTION public.set_updated_at()', m_ns, m_ns);

    -- Master products
    EXECUTE format('DROP TRIGGER IF EXISTS trg_%I_products_updated ON %I.products', m_ns, m_ns);
    EXECUTE format('CREATE TRIGGER trg_%I_products_updated BEFORE UPDATE ON %I.products FOR EACH ROW EXECUTE FUNCTION public.set_updated_at()', m_ns, m_ns);

    -- Local suppliers
    EXECUTE format('DROP TRIGGER IF EXISTS trg_%I_suppliers_updated ON %I.suppliers', l_ns, l_ns);
    EXECUTE format('CREATE TRIGGER trg_%I_suppliers_updated BEFORE UPDATE ON %I.suppliers FOR EACH ROW EXECUTE FUNCTION public.set_updated_at()', l_ns, l_ns);

    -- Local inventory_items
    EXECUTE format('DROP TRIGGER IF EXISTS trg_%I_items_updated ON %I.inventory_items', l_ns, l_ns);
    EXECUTE format('CREATE TRIGGER trg_%I_items_updated BEFORE UPDATE ON %I.inventory_items FOR EACH ROW EXECUTE FUNCTION public.set_updated_at()', l_ns, l_ns);

    -- Local purchase_orders
    EXECUTE format('DROP TRIGGER IF EXISTS trg_%I_orders_updated ON %I.purchase_orders', l_ns, l_ns);
    EXECUTE format('CREATE TRIGGER trg_%I_orders_updated BEFORE UPDATE ON %I.purchase_orders FOR EACH ROW EXECUTE FUNCTION public.set_updated_at()', l_ns, l_ns);

  END LOOP;
END $$;


-- ---------------------------------------------------------------------------
-- 2. Enterprise Performance Indexing for High-Volume Catalog (Lakhs of rows)
-- ---------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS btree_gist;

DO $$
DECLARE
  kinds TEXT[] := ARRAY['grocery', 'medical', 'food', 'stationery'];
  kind  TEXT;
  m_ns  TEXT;
  l_ns  TEXT;
BEGIN
  FOREACH kind IN ARRAY kinds LOOP
    m_ns := kind || '_master';
    l_ns := kind || '_local';

    -- Trigram index on product name for lightning-fast autocomplete / fuzzy matching
    EXECUTE format('CREATE INDEX IF NOT EXISTS ix_%I_name_trgm ON %I.products USING gin(product_name gin_trgm_ops)', m_ns, m_ns);

    -- Trigram index on brand
    EXECUTE format('CREATE INDEX IF NOT EXISTS ix_%I_brand_trgm ON %I.products USING gin(brand gin_trgm_ops) WHERE brand IS NOT NULL', m_ns, m_ns);

    -- Btree index on barcode for barcode scanning lookups (instant sub-millisecond point lookups)
    EXECUTE format('CREATE INDEX IF NOT EXISTS ix_%I_barcode_btree ON %I.products(barcode) WHERE barcode IS NOT NULL', m_ns, m_ns);

    -- Local inventory barcode & sku lookups
    EXECUTE format('CREATE INDEX IF NOT EXISTS ix_%I_inv_barcode ON %I.inventory_items(store_id, barcode) WHERE barcode IS NOT NULL', l_ns, l_ns);
    EXECUTE format('CREATE INDEX IF NOT EXISTS ix_%I_inv_sku ON %I.inventory_items(store_id, sku)', l_ns, l_ns);

    -- FEFO Optimization: Composite index on item_id, expiry_date, quantity
    EXECUTE format('CREATE INDEX IF NOT EXISTS ix_%I_batches_fefo ON %I.inventory_batches(item_id, expiry_date ASC, quantity) WHERE quantity > 0', l_ns, l_ns);

  END LOOP;

  -- Specialized medicine composition search (e.g. Paracetamol + Caffeine combinations)
  CREATE INDEX IF NOT EXISTS ix_medical_composition_trgm 
    ON medical_master.medical_product_details USING gin(composition gin_trgm_ops);

END $$;


-- ---------------------------------------------------------------------------
-- 3. High-Throughput Bulk Master Ingestion Procedure (API / File Feeds)
-- ---------------------------------------------------------------------------
-- Handles bulk JSON arrays containing hundreds or thousands of products per call,
-- performing high-speed idempotent upserting.
CREATE OR REPLACE FUNCTION public.bulk_upsert_master_products(
  p_store_type TEXT,
  p_products   JSONB
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
DECLARE
  v_master_schema TEXT;
  v_item          JSONB;
  v_inserted      INT := 0;
  v_updated       INT := 0;
  v_errors        INT := 0;
  v_prod_id       UUID;
  v_sku           TEXT;
  v_barcode       TEXT;
  v_name          TEXT;
  v_brand         TEXT;
  v_category      TEXT;
  v_subcategory   TEXT;
  v_desc          TEXT;
  v_unit          TEXT;
  v_pack_size     TEXT;
  v_mrp           NUMERIC;
  v_cost          NUMERIC;
  v_selling       NUMERIC;
  v_gst           NUMERIC;
BEGIN
  -- Validate store type
  IF p_store_type NOT IN ('grocery', 'medical', 'food', 'stationery') THEN
    RAISE EXCEPTION 'Invalid store type: %. Must be grocery, medical, food, or stationery.', p_store_type;
  END IF;

  v_master_schema := p_store_type || '_master';

  FOR v_item IN SELECT * FROM jsonb_array_elements(p_products) LOOP
    BEGIN
      v_sku         := v_item->>'sku';
      v_barcode     := NULLIF(TRIM(v_item->>'barcode'), '');
      v_name        := v_item->>'product_name';
      v_brand       := v_item->>'brand';
      v_category    := v_item->>'category';
      v_subcategory := v_item->>'subcategory';
      v_desc        := v_item->>'description';
      v_unit        := COALESCE(v_item->>'unit', 'unit');
      v_pack_size   := v_item->>'pack_size';
      v_mrp         := (v_item->>'mrp')::NUMERIC;
      v_cost        := (v_item->>'default_cost_price')::NUMERIC;
      v_selling     := (v_item->>'default_selling_price')::NUMERIC;
      v_gst         := COALESCE((v_item->>'gst_percentage')::NUMERIC, 0);

      IF v_sku IS NULL OR v_name IS NULL THEN
        v_errors := v_errors + 1;
        CONTINUE;
      END IF;

      -- Dynamic UPSERT into master products table
      EXECUTE format($upsert$
        INSERT INTO %I.products (
          sku, barcode, product_name, brand, category, subcategory,
          description, unit, pack_size, mrp, default_cost_price,
          default_selling_price, gst_percentage, is_active, updated_at
        ) VALUES (
          $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, TRUE, clock_timestamp()
        )
        ON CONFLICT (sku) DO UPDATE SET
          barcode               = EXCLUDED.barcode,
          product_name          = EXCLUDED.product_name,
          brand                 = EXCLUDED.brand,
          category              = EXCLUDED.category,
          subcategory           = EXCLUDED.subcategory,
          description           = EXCLUDED.description,
          unit                  = EXCLUDED.unit,
          pack_size             = EXCLUDED.pack_size,
          mrp                   = EXCLUDED.mrp,
          default_cost_price    = EXCLUDED.default_cost_price,
          default_selling_price = EXCLUDED.default_selling_price,
          gst_percentage        = EXCLUDED.gst_percentage,
          is_active             = TRUE,
          updated_at            = clock_timestamp()
        RETURNING id, (xmax = 0) AS was_inserted;
      $upsert$, v_master_schema)
      USING v_sku, v_barcode, v_name, v_brand, v_category, v_subcategory,
            v_desc, v_unit, v_pack_size, v_mrp, v_cost, v_selling, v_gst
      INTO v_prod_id;

      -- Upsert type-specific details if provided
      IF p_store_type = 'medical' AND (v_item ? 'details' OR v_item ? 'composition') THEN
        INSERT INTO medical_master.medical_product_details (
          product_id, generic_name, drug_type, dosage_form, strength,
          manufacturer, prescription_required, schedule, storage_conditions, composition
        ) VALUES (
          v_prod_id,
          COALESCE(v_item->'details'->>'generic_name', v_item->>'generic_name'),
          COALESCE(v_item->'details'->>'drug_type', v_item->>'drug_type'),
          COALESCE(v_item->'details'->>'dosage_form', v_item->>'dosage_form'),
          COALESCE(v_item->'details'->>'strength', v_item->>'strength'),
          COALESCE(v_item->'details'->>'manufacturer', v_item->>'manufacturer'),
          COALESCE((v_item->'details'->>'prescription_required')::BOOLEAN, (v_item->>'prescription_required')::BOOLEAN, FALSE),
          COALESCE(v_item->'details'->>'schedule', v_item->>'schedule'),
          COALESCE(v_item->'details'->>'storage_conditions', v_item->>'storage_conditions'),
          COALESCE(v_item->'details'->>'composition', v_item->>'composition')
        )
        ON CONFLICT (product_id) DO UPDATE SET
          generic_name          = EXCLUDED.generic_name,
          drug_type             = EXCLUDED.drug_type,
          dosage_form           = EXCLUDED.dosage_form,
          strength              = EXCLUDED.strength,
          manufacturer          = EXCLUDED.manufacturer,
          prescription_required = EXCLUDED.prescription_required,
          schedule              = EXCLUDED.schedule,
          storage_conditions    = EXCLUDED.storage_conditions,
          composition           = EXCLUDED.composition;

      ELSIF p_store_type = 'food' AND (v_item ? 'details' OR v_item ? 'fssai_license') THEN
        INSERT INTO food_master.food_product_details (
          product_id, food_type, storage_type, best_before_days, allergens, is_vegetarian, fssai_license
        ) VALUES (
          v_prod_id,
          COALESCE(v_item->'details'->>'food_type', v_item->>'food_type'),
          COALESCE(v_item->'details'->>'storage_type', v_item->>'storage_type'),
          COALESCE((v_item->'details'->>'best_before_days')::INT, (v_item->>'best_before_days')::INT),
          COALESCE(v_item->'details'->>'allergens', v_item->>'allergens'),
          COALESCE((v_item->'details'->>'is_vegetarian')::BOOLEAN, (v_item->>'is_vegetarian')::BOOLEAN),
          COALESCE(v_item->'details'->>'fssai_license', v_item->>'fssai_license')
        )
        ON CONFLICT (product_id) DO UPDATE SET
          food_type        = EXCLUDED.food_type,
          storage_type     = EXCLUDED.storage_type,
          best_before_days = EXCLUDED.best_before_days,
          allergens        = EXCLUDED.allergens,
          is_vegetarian    = EXCLUDED.is_vegetarian,
          fssai_license    = EXCLUDED.fssai_license;

      ELSIF p_store_type = 'stationery' AND (v_item ? 'details' OR v_item ? 'material') THEN
        INSERT INTO stationery_master.stationery_product_details (
          product_id, color, size, material, grade
        ) VALUES (
          v_prod_id,
          COALESCE(v_item->'details'->>'color', v_item->>'color'),
          COALESCE(v_item->'details'->>'size', v_item->>'size'),
          COALESCE(v_item->'details'->>'material', v_item->>'material'),
          COALESCE(v_item->'details'->>'grade', v_item->>'grade')
        )
        ON CONFLICT (product_id) DO UPDATE SET
          color    = EXCLUDED.color,
          size     = EXCLUDED.size,
          material = EXCLUDED.material,
          grade    = EXCLUDED.grade;
      END IF;

      v_inserted := v_inserted + 1;
    EXCEPTION WHEN OTHERS THEN
      v_errors := v_errors + 1;
    END;
  END LOOP;

  RETURN jsonb_build_object(
    'status', 'success',
    'store_type', p_store_type,
    'processed', v_inserted + v_errors,
    'upserted', v_inserted,
    'errors', v_errors
  );
END;
$$;

COMMENT ON FUNCTION public.bulk_upsert_master_products(TEXT, JSONB) IS
  'High-throughput idempotent upsert procedure for seeding master catalog products from API feeds or file batches.';


-- ---------------------------------------------------------------------------
-- 4. Enterprise Data Dictionary (Comments for Schemas, Tables, and Views)
-- ---------------------------------------------------------------------------
-- Schemas
COMMENT ON SCHEMA public            IS 'Core platform tenant directory, user-to-store authorizations, and global audit logging.';
COMMENT ON SCHEMA grocery_master    IS 'Module 1 (Grocery): Worldwide product master catalog, standard barcodes, categories, and supplier networks.';
COMMENT ON SCHEMA grocery_local     IS 'Module 1 (Grocery): Real-time store-level inventory, batches, POS transactions, orders, and wastage.';
COMMENT ON SCHEMA medical_master    IS 'Module 2 (Medical): Worldwide pharmaceutical drug catalog, Schedule H/H1/X compliance, CDSCO licensing, and salt compositions.';
COMMENT ON SCHEMA medical_local     IS 'Module 2 (Medical): Real-time pharmacy dispensary stock, batch-level temperature tracking, and expiry governance.';
COMMENT ON SCHEMA food_master       IS 'Module 3 (Food & FMCG): Worldwide food catalog, FSSAI regulatory compliance, allergens, and shelf-life metadata.';
COMMENT ON SCHEMA food_local        IS 'Module 3 (Food & FMCG): Real-time restaurant/supermarket perishable stock with strict FEFO inventory management.';
COMMENT ON SCHEMA stationery_master IS 'Module 4 (Stationery): Worldwide office/school stationery catalog, paper GSM, ruling specs, and brand taxonomies.';
COMMENT ON SCHEMA stationery_local  IS 'Module 4 (Stationery): Real-time store inventory, seasonal academic stock replenishments, and transaction auditing.';

-- Tables
COMMENT ON TABLE grocery_master.products IS 'Worldwide grocery master product index. Seeded from centralized API and bulk catalog datasets.';
COMMENT ON TABLE medical_master.products IS 'Worldwide pharmaceutical master medicine catalog with regulatory classifications.';
COMMENT ON TABLE food_master.products IS 'Worldwide packaged and fresh food catalog with dietary and preservation parameters.';
COMMENT ON TABLE stationery_master.products IS 'Worldwide stationery and office supplies master catalog with dimensional and material specs.';

-- ---------------------------------------------------------------------------
-- 5. Role Permissions & PostgREST Exposure
-- ---------------------------------------------------------------------------
-- Grant USAGE to anon, authenticated, and service_role on all custom schemas
GRANT USAGE ON SCHEMA 
  grocery_master, grocery_local, 
  medical_master, medical_local, 
  food_master, food_local, 
  stationery_master, stationery_local 
TO anon, authenticated, service_role;

-- Master catalogs: Read-only access for anon & authenticated, full access for service_role
GRANT SELECT ON ALL TABLES IN SCHEMA grocery_master, medical_master, food_master, stationery_master TO anon, authenticated;
GRANT ALL ON ALL TABLES IN SCHEMA grocery_master, medical_master, food_master, stationery_master TO service_role;

-- Local stores: Authenticated and service_role access (governed by RLS)
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA grocery_local, medical_local, food_local, stationery_local TO authenticated;
GRANT ALL ON ALL TABLES IN SCHEMA grocery_local, medical_local, food_local, stationery_local TO service_role;

-- Execute grants on functions
GRANT EXECUTE ON FUNCTION public.set_updated_at() TO authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.bulk_upsert_master_products(TEXT, JSONB) TO service_role;

-- Default privileges for future tables created in these schemas
DO $$
DECLARE
  kinds TEXT[] := ARRAY['grocery', 'medical', 'food', 'stationery'];
  kind  TEXT;
  m_ns  TEXT;
  l_ns  TEXT;
BEGIN
  FOREACH kind IN ARRAY kinds LOOP
    m_ns := kind || '_master';
    l_ns := kind || '_local';

    EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA %I GRANT SELECT ON TABLES TO anon, authenticated', m_ns);
    EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA %I GRANT ALL ON TABLES TO service_role', m_ns);

    EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA %I GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO authenticated', l_ns);
    EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA %I GRANT ALL ON TABLES TO service_role', l_ns);
  END LOOP;
END $$;

-- Notify PostgREST to reload schema cache
NOTIFY pgrst, 'reload schema';
