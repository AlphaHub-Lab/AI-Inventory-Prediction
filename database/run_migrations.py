#!/usr/bin/env python3
"""
Run all SQL migration files against Supabase PostgreSQL in order.

Usage:
    python run_migrations.py                # Run all migrations
    python run_migrations.py --seed         # Run migrations + seed data
    python run_migrations.py --seed-only    # Run only seed data
    python run_migrations.py --dry-run      # Show files that would be executed

Requires: psycopg2-binary (pip install psycopg2-binary)
Reads DATABASE_URL from .env file in the project root.
"""

import os
import sys
import glob
import argparse
from pathlib import Path

def load_env():
    """Load .env file from project root."""
    env_path = Path(__file__).parent.parent / '.env'
    if not env_path.exists():
        print("ERROR: .env file not found at", env_path)
        print("Copy .env.example to .env and set DATABASE_URL")
        sys.exit(1)

    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, _, value = line.partition('=')
                os.environ.setdefault(key.strip(), value.strip())

def get_sql_files(directory, pattern='*.sql'):
    """Get sorted list of SQL files from a directory."""
    files = sorted(glob.glob(os.path.join(directory, pattern)))
    return files

def execute_sql_file(cursor, filepath):
    """Execute a single SQL file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        sql = f.read()

    filename = os.path.basename(filepath)
    print(f"  Executing: {filename} ... ", end='', flush=True)

    try:
        cursor.execute(sql)
        print("OK")
        return True
    except Exception as e:
        print(f"FAILED\n    Error: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Run database migrations')
    parser.add_argument('--seed', action='store_true',
                        help='Also run seed data after migrations')
    parser.add_argument('--seed-only', action='store_true',
                        help='Run only seed data (skip migrations)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show files that would be executed')
    args = parser.parse_args()

    load_env()

    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("ERROR: DATABASE_URL not set in .env")
        sys.exit(1)

    # Resolve paths
    db_dir = Path(__file__).parent
    migrations_dir = db_dir / 'migrations'
    seeds_dir = db_dir / 'seeds'

    migration_files = get_sql_files(migrations_dir)
    seed_files = get_sql_files(seeds_dir)

    if args.dry_run:
        if not args.seed_only:
            print("\nMigration files:")
            for f in migration_files:
                print(f"  {os.path.basename(f)}")
        if args.seed or args.seed_only:
            print("\nSeed files:")
            for f in seed_files:
                print(f"  {os.path.basename(f)}")
        return

    try:
        import psycopg2
    except ImportError:
        print("ERROR: psycopg2-binary is required.")
        print("Install it with: pip install psycopg2-binary")
        sys.exit(1)

    # Connect
    print(f"\nConnecting to database...")
    try:
        conn = psycopg2.connect(database_url)
        conn.autocommit = False
        cursor = conn.cursor()
        print("Connected successfully.\n")
    except Exception as e:
        print(f"ERROR: Could not connect: {e}")
        sys.exit(1)

    success = True

    # Run migrations
    if not args.seed_only:
        print("=" * 60)
        print("RUNNING MIGRATIONS")
        print("=" * 60)
        for filepath in migration_files:
            if not execute_sql_file(cursor, filepath):
                success = False
                print("\nMigration failed. Rolling back...")
                conn.rollback()
                conn.close()
                sys.exit(1)

        conn.commit()
        print(f"\n  All {len(migration_files)} migrations completed successfully.\n")

    # Run seeds
    if args.seed or args.seed_only:
        print("=" * 60)
        print("RUNNING SEED DATA")
        print("=" * 60)
        for filepath in seed_files:
            if not execute_sql_file(cursor, filepath):
                success = False
                print("\nSeed failed. Rolling back...")
                conn.rollback()
                conn.close()
                sys.exit(1)

        conn.commit()
        print(f"\n  All {len(seed_files)} seed files completed successfully.\n")

    conn.close()

    if success:
        print("=" * 60)
        print("DATABASE SETUP COMPLETE")
        print("=" * 60)
    else:
        sys.exit(1)

if __name__ == '__main__':
    main()
