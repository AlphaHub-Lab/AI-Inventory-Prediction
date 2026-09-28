-- ============================================================================
-- MIGRATION 009: SEARCH & UTILITY FUNCTIONS
-- ============================================================================
-- Cross-schema search functions that implement the Local → Master fallback.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- search_local: search a store's local inventory
-- ---------------------------------------------------------------------------
DO $$
DECLARE
  kinds TEXT[] := ARRAY['grocery', 'medical', 'food', 'stationery'];
  kind TEXT; ns TEXT;
BEGIN
  FOREACH kind IN ARRAY kinds LOOP
    ns := kind || '_local';

    EXECUTE format($f$
      CREATE OR REPLACE FUNCTION %I.search_local(
        p_store_id  UUID,
        p_query     TEXT,
        p_limit     INTEGER DEFAULT 50
      ) RETURNS TABLE (
        id              UUID,
        sku             TEXT,
        barcode         TEXT,
        product_name    TEXT,
        brand           TEXT,
        category        TEXT,
        current_stock   NUMERIC,
        available_stock NUMERIC,
        selling_price   NUMERIC,
        mrp             NUMERIC,
        stock_status    TEXT,
        master_product_id UUID
      )
      LANGUAGE plpgsql
      STABLE
      SECURITY INVOKER
      AS $body$
      BEGIN
        RETURN QUERY
        SELECT
          s.id, s.sku, s.barcode, s.product_name, s.brand, s.category,
          s.current_stock, s.available_stock, s.selling_price, s.mrp,
          s.stock_status, s.master_product_id
        FROM %I.inventory_stock s
        WHERE s.store_id = p_store_id
          AND (
            s.sku ILIKE p_query || '%%'
            OR s.barcode = p_query
            OR s.product_name ILIKE '%%' || p_query || '%%'
            OR s.brand ILIKE '%%' || p_query || '%%'
            OR s.category ILIKE '%%' || p_query || '%%'
            OR to_tsvector('simple',
                 COALESCE(s.product_name,'') || ' ' ||
                 COALESCE(s.brand,'') || ' ' ||
                 COALESCE(s.category,'') || ' ' || s.sku
               ) @@ plainto_tsquery('simple', p_query)
          )
        ORDER BY s.product_name
        LIMIT p_limit;
      END $body$;
    $f$, ns, ns);

    EXECUTE format('GRANT EXECUTE ON FUNCTION %I.search_local(UUID,TEXT,INTEGER) TO authenticated, service_role', ns);

  END LOOP;
END $$;

-- ---------------------------------------------------------------------------
-- search_master: search the master catalog
-- ---------------------------------------------------------------------------
DO $$
DECLARE
  kinds TEXT[] := ARRAY['grocery', 'medical', 'food', 'stationery'];
  kind TEXT; ns TEXT;
BEGIN
  FOREACH kind IN ARRAY kinds LOOP
    ns := kind || '_master';

    EXECUTE format($f$
      CREATE OR REPLACE FUNCTION %I.search_catalog(
        p_query  TEXT,
        p_limit  INTEGER DEFAULT 50
      ) RETURNS TABLE (
        id                    UUID,
        sku                   TEXT,
        barcode               TEXT,
        product_name          TEXT,
        brand                 TEXT,
        category              TEXT,
        subcategory           TEXT,
        pack_size             TEXT,
        mrp                   NUMERIC,
        default_cost_price    NUMERIC,
        default_selling_price NUMERIC,
        supplier_id           UUID
      )
      LANGUAGE plpgsql
      STABLE
      SECURITY INVOKER
      AS $body$
      BEGIN
        RETURN QUERY
        SELECT
          p.id, p.sku, p.barcode, p.product_name, p.brand,
          p.category, p.subcategory, p.pack_size, p.mrp,
          p.default_cost_price, p.default_selling_price, p.supplier_id
        FROM %I.products p
        WHERE p.is_active
          AND (
            p.sku ILIKE p_query || '%%'
            OR p.barcode = p_query
            OR p.product_name ILIKE '%%' || p_query || '%%'
            OR p.brand ILIKE '%%' || p_query || '%%'
            OR p.category ILIKE '%%' || p_query || '%%'
            OR to_tsvector('simple',
                 COALESCE(p.product_name,'') || ' ' ||
                 COALESCE(p.brand,'') || ' ' ||
                 COALESCE(p.category,'') || ' ' || p.sku
               ) @@ plainto_tsquery('simple', p_query)
          )
        ORDER BY p.product_name
        LIMIT p_limit;
      END $body$;
    $f$, ns, ns);

    EXECUTE format('GRANT EXECUTE ON FUNCTION %I.search_catalog(TEXT,INTEGER) TO authenticated, service_role', ns);

  END LOOP;
END $$;

-- ---------------------------------------------------------------------------
-- Expiry report views
-- ---------------------------------------------------------------------------
DO $$
DECLARE
  kinds TEXT[] := ARRAY['grocery', 'medical', 'food', 'stationery'];
  kind TEXT; ns TEXT;
BEGIN
  FOREACH kind IN ARRAY kinds LOOP
    ns := kind || '_local';

    EXECUTE format($sql$
      CREATE OR REPLACE VIEW %I.expiring_batches
      WITH (security_invoker = true) AS
      SELECT
        i.store_id,
        i.id AS item_id,
        i.sku,
        i.product_name,
        i.brand,
        b.id AS batch_id,
        b.batch_number,
        b.quantity,
        b.expiry_date,
        CASE
          WHEN b.expiry_date < CURRENT_DATE        THEN 'EXPIRED'
          WHEN b.expiry_date = CURRENT_DATE         THEN 'EXPIRING_TODAY'
          WHEN b.expiry_date <= CURRENT_DATE + 7    THEN 'EXPIRING_7_DAYS'
          WHEN b.expiry_date <= CURRENT_DATE + 30   THEN 'EXPIRING_30_DAYS'
          WHEN b.expiry_date <= CURRENT_DATE + 60   THEN 'EXPIRING_60_DAYS'
          ELSE 'OK'
        END AS expiry_status,
        b.expiry_date - CURRENT_DATE AS days_until_expiry
      FROM %I.inventory_items i
      JOIN %I.inventory_batches b ON b.item_id = i.id
      WHERE b.quantity > 0
        AND b.expiry_date IS NOT NULL
      ORDER BY b.expiry_date ASC
    $sql$, ns, ns, ns);

  END LOOP;
END $$;

-- ---------------------------------------------------------------------------
-- Low stock view
-- ---------------------------------------------------------------------------
DO $$
DECLARE
  kinds TEXT[] := ARRAY['grocery', 'medical', 'food', 'stationery'];
  kind TEXT; ns TEXT;
BEGIN
  FOREACH kind IN ARRAY kinds LOOP
    ns := kind || '_local';

    EXECUTE format($sql$
      CREATE OR REPLACE VIEW %I.low_stock_items
      WITH (security_invoker = true) AS
      SELECT
        s.*,
        CASE
          WHEN s.current_stock = 0 THEN 'OUT_OF_STOCK'
          WHEN s.current_stock <= s.reorder_level THEN 'LOW_STOCK'
          WHEN s.current_stock <= s.minimum_stock THEN 'BELOW_MINIMUM'
          ELSE 'ADEQUATE'
        END AS stock_alert
      FROM %I.inventory_stock s
      WHERE s.current_stock <= s.reorder_level
      ORDER BY s.current_stock ASC
    $sql$, ns, ns);

  END LOOP;
END $$;
