#!/usr/bin/env python3
"""Quick health check for Janus installation"""
import os
import sqlite3
from pathlib import Path

def check_health():
    print("🔍 Janus Health Check\n" + "="*50)
    
    # Check database files
    db_files = ['androzoo.db', 'package_ids.db']
    for db in db_files:
        if os.path.exists(db):
            size = os.path.getsize(db) / (1024**3)  # GB
            print(f"✅ {db}: {size:.2f} GB")
            
            # Check row counts
            try:
                conn = sqlite3.connect(db)
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = cursor.fetchall()
                for table in tables:
                    cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
                    count = cursor.fetchone()[0]
                    print(f"   └─ {table[0]}: {count:,} rows")
                conn.close()
            except Exception as e:
                print(f"   └─ Error reading: {e}")
        else:
            print(f"❌ {db}: NOT FOUND")
    
    # Check precomputed data
    precomp_dir = Path("precomputed_data")
    if precomp_dir.exists():
        files = list(precomp_dir.glob("*.json"))
        print(f"\n✅ Precomputed data: {len(files)} files")
    else:
        print(f"\n⚠️  Precomputed data directory not found")
    
    # Check config
    try:
        import config
        print(f"\n✅ Config loaded")
        print(f"   └─ Debug mode: {getattr(config, 'DEBUG', 'Not set')}")
        print(f"   └─ Host: {getattr(config, 'HOST', 'Not set')}")
        print(f"   └─ Port: {getattr(config, 'PORT', 'Not set')}")
    except Exception as e:
        print(f"\n❌ Config error: {e}")

if __name__ == "__main__":
    check_health()