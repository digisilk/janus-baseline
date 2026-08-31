import sqlite3
import pandas as pd
import os


def create_sqlite_db(csv_path, db_path):
    print(f"Creating SQLite database from {csv_path}...")

    # Check if database already
    if os.path.exists(db_path):
        print(f"Database {db_path} already exists. Skipping creation.")
        return

    # Create a connection to the db
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create the table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS apks (
        sha256 TEXT PRIMARY KEY,
        sha1 TEXT,
        md5 TEXT,
        dex_date TEXT,
        apk_size INTEGER,
        pkg_name TEXT,
        vercode TEXT,
        vt_detection INTEGER,
        vt_scan_date TEXT,
        dex_size INTEGER,
        added TEXT,
        markets TEXT
    )
    ''')

    # Read / insert CSV data in chunks
    chunksize = 100000
    for chunk in pd.read_csv(csv_path, chunksize=chunksize):
        chunk.to_sql('apks', conn, if_exists='append', index=False)
        conn.commit()
        print(f"Inserted {chunksize} rows...")

    # indexes for faster querying
    print("Creating indexes...")
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_pkg_name ON apks(pkg_name)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_vt_scan_date ON apks(vt_scan_date)')

    conn.commit()
    conn.close()
    print("Database creation completed.")
