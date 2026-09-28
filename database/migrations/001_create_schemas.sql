-- ============================================================================
-- MIGRATION 001: CREATE SCHEMAS & FOUNDATION TABLES
-- ============================================================================
-- Creates:
--   1. Eight logical schemas (4 store types × master/local)
--   2. public.stores            – registered businesses/shops
--   3. public.store_memberships – user↔store authorization boundary
--   4. public.audit_log         – system-wide audit trail
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 1. Create the eight logical schemas
-- ---------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS grocery_local;
CREATE SCHEMA IF NOT EXISTS grocery_master;

CREATE SCHEMA IF NOT EXISTS medical_local;
CREATE SCHEMA IF NOT EXISTS medical_master;

CREATE SCHEMA IF NOT EXISTS food_local;
CREATE SCHEMA IF NOT EXISTS food_master;

CREATE SCHEMA IF NOT EXISTS stationery_local;
CREATE SCHEMA IF NOT EXISTS stationery_master;

-- ---------------------------------------------------------------------------
-- 2. Business type ENUM
-- ---------------------------------------------------------------------------
DO $$ BEGIN
  CREATE TYPE public.business_type AS ENUM (
    'grocery', 'medical', 'food', 'stationery'
  );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ---------------------------------------------------------------------------
-- 3. public.stores – every registered shop
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.stores (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  store_name      TEXT NOT NULL,
  business_type   public.business_type NOT NULL,
  owner_id        UUID REFERENCES auth.users(id),
  address         TEXT,
  city            TEXT,
  state           TEXT,
  pincode         TEXT,
  phone           TEXT,
  email           TEXT,
  gst_number      TEXT,
  is_active       BOOLEAN NOT NULL DEFAULT TRUE,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.stores IS
  'Registered businesses. store_type maps to exactly one pair of schemas (e.g. grocery_master + grocery_local).';

-- ---------------------------------------------------------------------------
-- 4. public.store_memberships – user ↔ store authorisation
-- ---------------------------------------------------------------------------
DO $$ BEGIN
  CREATE TYPE public.store_role AS ENUM (
    'owner', 'manager', 'seller', 'viewer'
  );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS public.store_memberships (
  store_id  UUID NOT NULL REFERENCES public.stores(id) ON DELETE CASCADE,
  user_id   UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  role      public.store_role NOT NULL DEFAULT 'seller',
  PRIMARY KEY (store_id, user_id)
);

COMMENT ON TABLE public.store_memberships IS
  'Maps Supabase auth.users to stores. Provisioned by a trusted backend/service role.';

-- RLS on memberships: users see only their own rows
ALTER TABLE public.store_memberships ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS memberships_self_read ON public.store_memberships;
CREATE POLICY memberships_self_read
  ON public.store_memberships
  FOR SELECT TO authenticated
  USING (user_id = auth.uid());

-- RLS on stores: users see stores they belong to
ALTER TABLE public.stores ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS stores_member_read ON public.stores;
CREATE POLICY stores_member_read
  ON public.stores
  FOR SELECT TO authenticated
  USING (
    id IN (SELECT store_id FROM public.store_memberships WHERE user_id = auth.uid())
  );

-- ---------------------------------------------------------------------------
-- 5. public.audit_log – system-wide audit trail
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.audit_log (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  store_id    UUID REFERENCES public.stores(id),
  user_id     UUID REFERENCES auth.users(id),
  action      TEXT NOT NULL,
  entity      TEXT NOT NULL,
  entity_id   TEXT,
  old_value   JSONB,
  new_value   JSONB,
  ip_address  INET,
  note        TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_audit_log_store
  ON public.audit_log(store_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_audit_log_entity
  ON public.audit_log(entity, entity_id);
CREATE INDEX IF NOT EXISTS ix_audit_log_user
  ON public.audit_log(user_id, created_at DESC);

ALTER TABLE public.audit_log ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS audit_store_read ON public.audit_log;
CREATE POLICY audit_store_read
  ON public.audit_log
  FOR SELECT TO authenticated
  USING (
    store_id IN (SELECT store_id FROM public.store_memberships WHERE user_id = auth.uid())
  );

COMMENT ON TABLE public.audit_log IS
  'Immutable audit trail. All inventory mutations are recorded here.';

-- ---------------------------------------------------------------------------
-- 6. Grants
-- ---------------------------------------------------------------------------
GRANT USAGE ON SCHEMA
  grocery_master, grocery_local,
  medical_master, medical_local,
  food_master,    food_local,
  stationery_master, stationery_local
TO authenticated, service_role;

GRANT SELECT ON public.store_memberships TO authenticated;
GRANT SELECT ON public.stores TO authenticated;
GRANT SELECT ON public.audit_log TO authenticated;

GRANT ALL ON public.stores, public.store_memberships, public.audit_log TO service_role;
