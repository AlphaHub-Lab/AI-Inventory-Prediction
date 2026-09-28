-- Store membership is the authorization boundary used by all local-schema RLS policies.
CREATE TABLE IF NOT EXISTS public.inventory_stores (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), store_type text NOT NULL CHECK (store_type IN ('grocery','medical','food','stationery')),
  name text NOT NULL, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS public.inventory_store_memberships (
  store_id uuid NOT NULL REFERENCES public.inventory_stores(id) ON DELETE CASCADE,
  user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  role text NOT NULL DEFAULT 'seller' CHECK (role IN ('owner','manager','seller','viewer')),
  PRIMARY KEY (store_id,user_id)
);
ALTER TABLE public.inventory_store_memberships ENABLE ROW LEVEL SECURITY;
CREATE POLICY inventory_memberships_self_read ON public.inventory_store_memberships FOR SELECT TO authenticated USING (user_id = auth.uid());
COMMENT ON TABLE public.inventory_store_memberships IS 'Assign Supabase auth.users to stores; provisioning is performed by a trusted backend/service role.';

GRANT SELECT ON public.inventory_store_memberships TO authenticated;
GRANT ALL ON public.inventory_stores, public.inventory_store_memberships TO service_role;

