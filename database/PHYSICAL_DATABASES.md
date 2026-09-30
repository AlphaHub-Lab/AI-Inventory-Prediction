# Supabase physical database layout

The live Supabase project now uses one PostgreSQL cluster with these databases:

| Database | Purpose | Current contents |
|---|---|---|
| `admin_db` | Application identities, businesses, roles, permissions, sessions, registry, audit and central app records | Alembic revision `0007_database_registry`; no businesses are registered yet |
| `master_medical` | Shared medical catalog | 86 products, 5 suppliers, 17 medical detail rows |
| `master_grocery` | Shared grocery catalog | 106 products, 5 suppliers |
| `master_restaurant` | Shared restaurant/food catalog | 110 products, 5 suppliers, restaurant ingredient/recipe/pricing tables |
| `master_stationery` | Shared stationery catalog | 105 products, 5 suppliers, 5 stationery detail rows |
| `master_dairy` | Shared dairy catalog | 11 dairy products, 5 suppliers, 11 expiry/storage detail rows |

Master catalog relations currently live under the `catalog` schema in their respective databases. Catalog rows were copied from the existing master schemas in the `postgres` database; the dairy catalog contains the dairy-related subset from the food catalog.

## Local databases

The design creates one `local_business_<business_id>` database per business. The live `admin_db.businesses` table is empty, so there were no local databases to create during setup. The registry is seeded with the admin and five master database entries; local entries are added when businesses are provisioned.

## Backend status and limitations

The backend `.env` points to `admin_db`, and Alembic migrations there are at `0007_database_registry`. Business, inventory, and transaction API data routing to `master_*` and `local_business_*` is not yet implemented; the existing API still uses the central application models. Do not treat the physical master/local databases as fully wired into application workflows until that routing and per-business database provisioning are implemented.

The older `database/migrations/*.sql` files bootstrap the former schema-per-type layout inside the single `postgres` database. They are not the provisioning mechanism for the physical database layout above. Those legacy schemas remain in `postgres` and were left intact to avoid deleting existing catalog or store data.

## Connection configuration

Keep the backend connection string in the ignored project `.env` file as `DATABASE_URL`, targeting `admin_db` through the Supabase session pooler. Use the separate target database name only for trusted backend connections. Never expose database credentials in frontend code, logs, or source control.
