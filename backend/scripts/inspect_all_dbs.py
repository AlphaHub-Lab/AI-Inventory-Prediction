import os
import sys
from app.database_manager import get_engine_for_db
from sqlalchemy import text

for db_name in ['admin_db', 'master_medical', 'master_grocery', 'local_business_1', 'inventory_system']:
    try:
        engine = get_engine_for_db(db_name)
        with engine.connect() as conn:
            tables = conn.execute(text("SELECT table_schema, table_name FROM information_schema.tables WHERE table_schema NOT IN ('pg_catalog', 'information_schema')")).fetchall()
            print(f"{db_name}:", [(t[0], t[1]) for t in tables])
    except Exception as e:
        print(f"{db_name} error:", e)
