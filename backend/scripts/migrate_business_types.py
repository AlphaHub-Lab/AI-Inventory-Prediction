import sys
from app.database_manager import get_admin_session, get_engine_for_db
from sqlalchemy import text

def migrate():
    s = get_admin_session()
    try:
        # Check current constraint
        print("Checking constraints on admin_db.businesses...")
        # Drop old constraint if exists and recreate with all 7 types
        try:
            s.execute(text("ALTER TABLE businesses DROP CONSTRAINT IF EXISTS ck_businesses_supported_type;"))
            s.execute(text("""
                ALTER TABLE businesses ADD CONSTRAINT ck_businesses_supported_type 
                CHECK (business_type IN ('medical', 'grocery', 'restaurant', 'food', 'stationery', 'dairy', 'clothing', 'others'));
            """))
            s.commit()
            print("Successfully updated ck_businesses_supported_type in admin_db!")
        except Exception as e:
            s.rollback()
            print(f"Error updating constraint: {e}")

        # Check existing businesses
        rows = s.execute(text("SELECT id, name, business_type, local_database_name FROM businesses")).fetchall()
        print("Current businesses in admin_db:")
        for r in rows:
            print(f"  ID {r[0]}: {r[1]} ({r[2]}) -> {r[3]}")
    finally:
        s.close()

if __name__ == "__main__":
    migrate()
