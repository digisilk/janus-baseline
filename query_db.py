#!/usr/bin/env python3
"""Quick database exploration tool"""
import sqlite3
import sys

def explore_db(db_name='androzoo.db'):
    if not os.path.exists(db_name):
        print(f"❌ Database {db_name} not found!")
        return
    
    conn = sqlite3.connect(db_name)
    cursor = conn.cursor()
    
    # List all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    
    print(f"\n📊 Tables in {db_name}:")
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
        count = cursor.fetchone()[0]
        print(f"  • {table[0]}: {count:,} rows")
        
        # Show sample data
        cursor.execute(f"SELECT * FROM {table[0]} LIMIT 3")
        rows = cursor.fetchall()
        if rows:
            print(f"    Sample: {rows[0][:3]}...")  # First 3 columns
    
    conn.close()

if __name__ == "__main__":
    import os
    explore_db()