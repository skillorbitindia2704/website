"""Migrate all data from SQLite to PostgreSQL with schema preservation, sequence sync, and validation."""

import argparse
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.schema import Table

# Add website root to path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
WEBSITE_DIR = os.path.dirname(CURRENT_DIR)
if WEBSITE_DIR not in sys.path:
    sys.path.insert(0, WEBSITE_DIR)

from app import create_app
from models import db


def normalize_pg_uri(uri: str) -> str:
    """Ensure PostgreSQL URI uses postgresql+psycopg driver if not specified."""
    uri = uri.strip()
    if uri.startswith("postgres://"):
        uri = "postgresql+psycopg://" + uri[len("postgres://") :]
    elif uri.startswith("postgresql://"):
        uri = "postgresql+psycopg://" + uri[len("postgresql://") :]
    return uri


def parse_datetime(val: Any) -> Any:
    """Convert SQLite string datetimes to Python datetime objects."""
    if isinstance(val, str) and val:
        try:
            return datetime.fromisoformat(val)
        except ValueError:
            for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                try:
                    return datetime.strptime(val, fmt)
                except ValueError:
                    continue
    return val


def migrate(
    pg_uri: str,
    sqlite_path: Optional[str] = None,
    clean_target: bool = False,
) -> Dict[str, Any]:
    """Execute complete migration from SQLite to PostgreSQL."""
    pg_uri = normalize_pg_uri(pg_uri)

    if not sqlite_path:
        sqlite_path = os.path.join(WEBSITE_DIR, "instance", "skill_orbit_india.db")

    if not os.path.exists(sqlite_path):
        raise FileNotFoundError(f"Source SQLite database not found at: {sqlite_path}")

    print("=" * 65)
    print("Skill Orbit India: SQLite -> PostgreSQL Safe Migration Engine")
    print("=" * 65)
    print(f"Source SQLite: {sqlite_path} ({os.path.getsize(sqlite_path)} bytes)")
    print(f"Target DB URI: {pg_uri.split('@')[-1] if '@' in pg_uri else pg_uri}")
    print("=" * 65)

    sqlite_engine = create_engine(f"sqlite:///{sqlite_path}")
    pg_engine = create_engine(pg_uri, pool_pre_ping=True)

    # 1. Test target connection
    print("\n[Step 1/6] Testing PostgreSQL connection...")
    with pg_engine.connect() as conn:
        version = conn.execute(text("SELECT version();")).scalar()
        encoding = conn.execute(text("SHOW server_encoding;")).scalar()
        print(f"Connected to PostgreSQL: {version}")
        print(f"Database Server Encoding: {encoding}")

    # 2. Build Schema via SQLAlchemy metadata
    print("\n[Step 2/6] Ensuring all 76 tables exist in PostgreSQL schema...")
    app = create_app()
    with app.app_context():
        metadata = db.metadata

        if clean_target:
            print("  Warning: clean_target=True requested. Dropping existing target tables...")
            metadata.drop_all(bind=pg_engine)

        metadata.create_all(bind=pg_engine)
        print(f"  Successfully ensured {len(metadata.tables)} tables in PostgreSQL.")

    # 3. Disable Foreign Keys temporarily during data insertion if permitted
    print("\n[Step 3/6] Migrating records table-by-table in dependency order...")
    # Sorted in dependency order (parents before children)
    sorted_tables: List[Table] = metadata.sorted_tables

    can_disable_triggers = False
    try:
        with pg_engine.begin() as conn:
            conn.execute(text("SET session_replication_role = 'replica';"))
            can_disable_triggers = True
            print("  Replication role set to 'replica' (FK triggers safely deferred).")
    except Exception:
        print("  Notice: Running without superuser replication role; using strict dependency ordering.")

    sqlite_counts: Dict[str, int] = {}
    pg_counts: Dict[str, int] = {}

    with sqlite_engine.connect() as sqlite_conn, pg_engine.begin() as pg_conn:
        if can_disable_triggers:
            pg_conn.execute(text("SET session_replication_role = 'replica';"))

        for table in sorted_tables:
            table_name = table.name
            quoted_name = f'"{table_name}"'

            # Get row count from SQLite
            s_count = sqlite_conn.execute(text(f"SELECT COUNT(*) FROM {quoted_name}")).scalar() or 0
            sqlite_counts[table_name] = s_count

            if s_count == 0:
                continue

            print(f"  -> Migrating {table_name}: {s_count} records...", end="", flush=True)

            # Check if target already has records
            p_count_before = pg_conn.execute(text(f"SELECT COUNT(*) FROM {quoted_name}")).scalar() or 0
            if p_count_before > 0:
                print(f" (target already has {p_count_before} rows, clearing for clean sync)...", end="", flush=True)
                pg_conn.execute(text(f"TRUNCATE TABLE {quoted_name} CASCADE;"))

            # Read from SQLite
            rows = sqlite_conn.execute(select(table)).mappings().all()

            # Sanitize types for PostgreSQL
            clean_rows = []
            for r in rows:
                row_dict = dict(r)
                for col in table.columns:
                    col_name = col.name
                    val = row_dict.get(col_name)

                    # Boolean conversion
                    if str(col.type).upper().startswith("BOOL") and val is not None:
                        row_dict[col_name] = bool(val)
                    # Datetime conversion
                    elif str(col.type).upper().startswith("DATETIME") and val is not None:
                        row_dict[col_name] = parse_datetime(val)
                    elif str(col.type).upper().startswith("DATE") and val is not None:
                        row_dict[col_name] = parse_datetime(val).date() if hasattr(parse_datetime(val), "date") else val

                clean_rows.append(row_dict)

            # Bulk insert into PostgreSQL
            if clean_rows:
                pg_conn.execute(table.insert(), clean_rows)

            print(" Done.")

        if can_disable_triggers:
            pg_conn.execute(text("SET session_replication_role = 'origin';"))

    # 4. Synchronize Auto-Increment Sequences
    print("\n[Step 4/6] Synchronizing PostgreSQL auto-increment sequences...")
    with pg_engine.begin() as pg_conn:
        synced_seqs = 0
        for table in sorted_tables:
            # Check for autoincrement primary key
            pk_cols = [col for col in table.columns if col.primary_key and str(col.type).upper().startswith("INT")]
            for pk in pk_cols:
                quoted_table = f'"{table.name}"'
                pk_name = pk.name
                seq_query = text(f"""
                    SELECT pg_get_serial_sequence('{table.name}', '{pk_name}');
                """)
                try:
                    seq_name = pg_conn.execute(seq_query).scalar()
                    if seq_name:
                        max_val_q = text(f'SELECT MAX("{pk_name}") FROM {quoted_table};')
                        max_id = pg_conn.execute(max_val_q).scalar()
                        if max_id is not None:
                            pg_conn.execute(text(f"SELECT setval('{seq_name}', {max_id}, true);"))
                        else:
                            pg_conn.execute(text(f"SELECT setval('{seq_name}', 1, false);"))
                        synced_seqs += 1
                except Exception as exc:
                    print(f"  Note on sequence sync for {table.name}.{pk_name}: {exc}")

        print(f"  Successfully synchronized {synced_seqs} sequences.")

    # 5. Validation Suite
    print("\n[Step 5/6] Validating SQLite vs PostgreSQL parity...")
    validation_failures = []
    with pg_engine.connect() as pg_conn:
        for table in sorted_tables:
            t_name = table.name
            quoted_name = f'"{t_name}"'
            p_count = pg_conn.execute(text(f"SELECT COUNT(*) FROM {quoted_name}")).scalar() or 0
            pg_counts[t_name] = p_count
            s_count = sqlite_counts.get(t_name, 0)

            if s_count != p_count:
                validation_failures.append(f"Table '{t_name}' count mismatch: SQLite={s_count}, PG={p_count}")

    if validation_failures:
        print("\nERROR: VALIDATION FAILED!")
        for fail in validation_failures:
            print(f"  - {fail}")
        raise ValueError(f"Migration validation failed with {len(validation_failures)} errors.")

    print(f"  VERIFICATION PASSED: All {len(sorted_tables)} tables match 100% in row counts!")

    # 6. Checksum / Data Sampling Check
    print("\n[Step 6/6] Verifying critical record values across engines...")
    with sqlite_engine.connect() as s_conn, pg_engine.connect() as p_conn:
        # Check users
        s_users = s_conn.execute(text("SELECT id, email, role FROM \"user\" ORDER BY id")).fetchall()
        p_users = p_conn.execute(text("SELECT id, email, role FROM \"user\" ORDER BY id")).fetchall()
        assert s_users == p_users, "User records do not match between SQLite and PostgreSQL!"
        print(f"  - User records match: {len(p_users)} verified.")

        # Check products
        s_prods = s_conn.execute(text("SELECT id, name, price_inr, stock FROM product ORDER BY id")).fetchall()
        p_prods = p_conn.execute(text("SELECT id, name, price_inr, stock FROM product ORDER BY id")).fetchall()
        assert s_prods == p_prods, "Product records do not match between SQLite and PostgreSQL!"
        print(f"  - Product records match: {len(p_prods)} verified.")

        # Check orders
        s_orders = s_conn.execute(text('SELECT id, user_id, total_inr, status FROM "order" ORDER BY id')).fetchall()
        p_orders = p_conn.execute(text('SELECT id, user_id, total_inr, status FROM "order" ORDER BY id')).fetchall()
        assert s_orders == p_orders, "Order records do not match between SQLite and PostgreSQL!"
        print(f"  - Order records match: {len(p_orders)} verified.")

    print("\n" + "=" * 65)
    print("SUCCESS: Database migrated, sequences aligned, and validated!")
    print("=" * 65)

    return {
        "tables_count": len(sorted_tables),
        "migrated_records": sum(sqlite_counts.values()),
        "sqlite_counts": sqlite_counts,
        "pg_counts": pg_counts,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate Skill Orbit India from SQLite to PostgreSQL")
    parser.add_argument(
        "--pg-uri",
        default=os.getenv("TARGET_DATABASE_URL") or os.getenv("DATABASE_URL"),
        help="PostgreSQL connection URI (e.g. postgresql://user:pass@localhost:5432/dbname)",
    )
    parser.add_argument(
        "--sqlite-path",
        default=None,
        help="Path to SQLite database (default: website/instance/skill_orbit_india.db)",
    )
    parser.add_argument(
        "--clean-target",
        action="store_true",
        help="Drop and recreate target tables before migration",
    )

    args = parser.parse_args()

    if not args.pg_uri or "sqlite" in args.pg_uri.lower():
        print("ERROR: A valid PostgreSQL connection URI must be provided.")
        print("Usage: python website/utils/migrate_sqlite_to_pg.py --pg-uri postgresql://user:pass@host:5432/dbname")
        sys.exit(1)

    try:
        migrate(args.pg_uri, args.sqlite_path, args.clean_target)
    except Exception as e:
        print(f"\nFATAL MIGRATION ERROR: {e}")
        sys.exit(1)
