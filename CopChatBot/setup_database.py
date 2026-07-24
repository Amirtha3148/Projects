"""
setup_database.py
-----------------
Creates the 'copchatbot' database in PostgreSQL if it doesn't already exist.
Uses credentials from .env.

Usage:
    1. Update DB_PASSWORD in .env
    2. python setup_database.py
    3. python migrate_intents.py
"""

import os
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "copchatbot")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")


def main():
    # Connect to the default 'postgres' database to create our target DB
    print(f"[*] Connecting to PostgreSQL at {DB_HOST}:{DB_PORT} as '{DB_USER}'...")
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname="postgres",
        user=DB_USER,
        password=DB_PASSWORD,
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)

    with conn.cursor() as cur:
        # Check if the database already exists
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DB_NAME,))
        exists = cur.fetchone()

        if exists:
            print(f"[OK] Database '{DB_NAME}' already exists.")
        else:
            cur.execute(f'CREATE DATABASE "{DB_NAME}"')
            print(f"[OK] Database '{DB_NAME}' created successfully!")

    conn.close()
    print("Done. You can now run: python migrate_intents.py")


if __name__ == "__main__":
    main()
