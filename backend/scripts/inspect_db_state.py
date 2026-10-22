import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import engine
from sqlalchemy import text

with engine.connect() as conn:
    schemas = conn.execute(text("SELECT schema_name FROM information_schema.schemata;")).fetchall()
    print("Schemas:", [s[0] for s in schemas])
    tables = conn.execute(text("""
        SELECT table_schema, table_name 
        FROM information_schema.tables 
        WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
        ORDER BY table_schema, table_name;
    """)).fetchall()
    print("Tables:")
    for t in tables:
        print(f"  {t[0]}.{t[1]}")
