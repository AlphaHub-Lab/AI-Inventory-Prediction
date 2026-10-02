from app.config import get_settings
import sqlalchemy as sa

engine = sa.create_engine(get_settings().database_url)
with engine.connect() as conn:
    print("Connected successfully!")
    dbs = conn.execute(sa.text("SELECT datname FROM pg_database WHERE datistemplate = false;")).fetchall()
    print("Databases:", [d[0] for d in dbs])
    tables = conn.execute(sa.text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")).fetchall()
    print("Tables in admin_db.public:", [t[0] for t in tables])
