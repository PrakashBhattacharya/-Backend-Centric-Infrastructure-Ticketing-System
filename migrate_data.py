import sqlite3
import psycopg2
import psycopg2.extras
import os
from dotenv import load_dotenv

# Load Postgres connection string from local .env
load_dotenv('.env')
postgres_url = os.environ.get('POSTGRES_URL')

if not postgres_url:
    print("ERROR: POSTGRES_URL not found in .env file.")
    exit(1)

# Connect to SQLite
sqlite_db_path = os.path.join('backend', 'instance', 'infratick.db')
if not os.path.exists(sqlite_db_path):
    print(f"ERROR: SQLite database not found at {sqlite_db_path}")
    exit(1)

sqlite_conn = sqlite3.connect(sqlite_db_path)
sqlite_conn.row_factory = sqlite3.Row
sqlite_cur = sqlite_conn.cursor()

# Connect to PostgreSQL
pg_conn = psycopg2.connect(postgres_url)
pg_cur = pg_conn.cursor()

try:
    print("Connected to both databases. Starting migration...")

    # Define tables to migrate in order of dependencies (parent tables first)
    tables = [
        ('users', ['id', 'full_name', 'email', 'password_hash', 'role', 'created_at']),
        ('tickets', ['id', 'subject', 'description', 'service_area', 'environment', 'priority', 'status', 'sla_deadline', 'created_at', 'updated_at', 'created_by', 'assigned_to']),
        ('comments', ['id', 'ticket_id', 'user_id', 'text', 'created_at']),
        ('audit_logs', ['id', 'action', 'details', 'icon', 'color', 'danger', 'user_id', 'ticket_id', 'created_at'])
    ]

    # Clear existing data in Postgres to perform a clean transfer
    print("Clearing production tables to prepare for import...")
    for table_name, _ in reversed(tables):
        pg_cur.execute(f"TRUNCATE TABLE {table_name} CASCADE;")

    # Migrate data
    for table_name, columns in tables:
        print(f"Migrating table: {table_name}...")

        sqlite_cur.execute(f"SELECT * FROM {table_name}")
        rows = sqlite_cur.fetchall()

        if not rows:
            print(f"  No data to migrate for {table_name}.")
            continue

        print(f"  Found {len(rows)} rows. Inserting into Postgres...")

        cols_str = ', '.join(columns)
        placeholders = ', '.join(['%s'] * len(columns))
        insert_query = f"INSERT INTO {table_name} ({cols_str}) VALUES ({placeholders})"

        for row in rows:
            values = tuple(row[col] for col in columns)
            pg_cur.execute(insert_query, values)

        # Update PostgreSQL sequence so future inserts don't collide with migrated IDs
        pg_cur.execute(f"SELECT setval('{table_name}_id_seq', COALESCE((SELECT MAX(id)+1 FROM {table_name}), 1), false);")

        print(f"  Table {table_name} migration complete.")

    pg_conn.commit()
    print("Migration successful! All local data is now live on Vercel Postgres.")

except Exception as e:
    pg_conn.rollback()
    print("ERROR DURING MIGRATION:")
    print(e)
finally:
    sqlite_conn.close()
    pg_cur.close()
    pg_conn.close()
