import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.config import get_settings
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

def check_and_create_db():
    base_url = get_settings().database_url.replace("postgresql+psycopg://", "postgresql://")
    print(f"Connecting to base connection...")
    conn = psycopg2.connect(base_url)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    
    cur.execute("SELECT 1 FROM pg_database WHERE datname='inventory_system'")
    exists = cur.fetchone()
    print("Does database 'inventory_system' exist?", bool(exists))
    
    if not exists:
        print("Creating database 'inventory_system'...")
        try:
            cur.execute("CREATE DATABASE inventory_system")
            print("Successfully created database 'inventory_system'!")
        except Exception as e:
            print(f"Error creating database: {e}")
            cur.close()
            conn.close()
            return False
            
    cur.close()
    conn.close()
    return True

if __name__ == "__main__":
    check_and_create_db()
