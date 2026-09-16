"""Quick interactive terminal viewer for PostgreSQL database tables."""

import argparse
import os
import sys
from dotenv import load_dotenv

# Load .env
website_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(website_dir, ".env"), override=True)

import psycopg

# Fix Windows console encoding
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

db_url = os.getenv("DATABASE_URL")
if not db_url:
    print("ERROR: DATABASE_URL not found in website/.env")
    sys.exit(1)

# Normalize for psycopg
if db_url.startswith("postgresql+psycopg://"):
    db_url = "postgresql://" + db_url[len("postgresql+psycopg://"):]
elif db_url.startswith("postgres://"):
    db_url = "postgresql://" + db_url[len("postgres://"):]


def format_cell(val):
    if val is None:
        return "NULL"
    s = str(val).replace("\n", " ")
    if len(s) > 40:
        return s[:37] + "..."
    return s


def view_data(table_name=None, limit=20):
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            if not table_name:
                cur.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    ORDER BY table_name;
                """)
                tables = [r[0] for r in cur.fetchall()]
                print("=" * 60)
                print("Skill Orbit India — PostgreSQL Database Tables")
                print("=" * 60)
                for idx, t in enumerate(tables, 1):
                    cur.execute(f'SELECT COUNT(*) FROM "{t}";')
                    cnt = cur.fetchone()[0]
                    star = " ★" if cnt > 0 else ""
                    print(f"[{idx:2}] {t:32} : {cnt:4} rows{star}")
                print("=" * 60)
                print("\nTip: To view rows in a table, run:")
                print("  python website/utils/view_db.py --table user")
                print("  python website/utils/view_db.py --table product")
                print("  python website/utils/view_db.py --table course")
                return

            quoted_name = f'"{table_name}"'
            cur.execute(f"SELECT * FROM {quoted_name} LIMIT {limit};")
            cols = [desc[0] for desc in cur.description]
            rows = cur.fetchall()

            cur.execute(f"SELECT COUNT(*) FROM {quoted_name};")
            total_count = cur.fetchone()[0]

            print("=" * 80)
            print(f"Table: {table_name} (Showing {len(rows)} of {total_count} total rows)")
            print("=" * 80)

            if not rows:
                print("  (Table is empty)")
                return

            # Print header
            formatted_cols = [c[:20] for c in cols]
            header = " | ".join(f"{c:20}" for c in formatted_cols)
            sep = "-+-".join("-" * 20 for _ in formatted_cols)
            print(header)
            print(sep)

            for r in rows:
                row_str = " | ".join(f"{format_cell(v):20}" for v in r)
                print(row_str)
            print("=" * 80)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="View PostgreSQL tables and rows")
    parser.add_argument("--table", "-t", default=None, help="Table name to inspect")
    parser.add_argument("--limit", "-l", type=int, default=15, help="Number of rows to show")
    args = parser.parse_args()

    try:
        view_data(args.table, args.limit)
    except Exception as e:
        print(f"Error: {e}")
