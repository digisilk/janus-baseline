#!/usr/bin/env python3
"""
Bootstrap AndroZoo Database
Downloads the latest CSV and creates SQLite databases for Janus
"""

import os
import sys
import urllib.request
import gzip
import csv
import sqlite3
from pathlib import Path
from datetime import datetime

# Configuration
CSV_URL = "https://androzoo.uni.lu/static/lists/latest.csv.gz"
CSV_FILE = "latest.csv.gz"
CSV_EXTRACTED = "latest.csv"
ANDROZOO_DB = "androzoo.db"
PACKAGE_IDS_DB = "package_ids.db"

def download_csv():
    """Download the AndroZoo CSV file"""
    print(f"📥 Downloading AndroZoo CSV from: {CSV_URL}")
    print("⏳ This is ~2.7GB and may take 30-60 minutes...")
    
    if os.path.exists(CSV_FILE):
        print(f"⚠️  {CSV_FILE} already exists. Delete it to re-download.")
        choice = input("Use existing file? (y/n): ").lower()
        if choice != 'y':
            os.remove(CSV_FILE)
        else:
            return True
    
    try:
        def report_progress(block_num, block_size, total_size):
            downloaded = block_num * block_size
            percent = min(100, (downloaded / total_size) * 100)
            mb_downloaded = downloaded / (1024 * 1024)
            mb_total = total_size / (1024 * 1024)
            print(f"\r  Progress: {percent:.1f}% ({mb_downloaded:.1f} MB / {mb_total:.1f} MB)", end='')
        
        urllib.request.urlretrieve(CSV_URL, CSV_FILE, report_progress)
        print("\n✅ Download complete!")
        return True
    except Exception as e:
        print(f"\n❌ Error downloading: {e}")
        print("\n💡 Alternative: Manual download")
        print(f"   1. Visit: https://androzoo.uni.lu/lists")
        print(f"   2. Download 'latest.csv.gz'")
        print(f"   3. Place it in: {os.getcwd()}")
        return False

def extract_csv():
    """Extract the compressed CSV file"""
    if os.path.exists(CSV_EXTRACTED):
        print(f"⚠️  {CSV_EXTRACTED} already exists.")
        return True
    
    print(f"\n📦 Extracting {CSV_FILE}...")
    try:
        with gzip.open(CSV_FILE, 'rb') as f_in:
            with open(CSV_EXTRACTED, 'wb') as f_out:
                # Read in chunks to show progress
                chunk_size = 1024 * 1024  # 1MB chunks
                total_read = 0
                while True:
                    chunk = f_in.read(chunk_size)
                    if not chunk:
                        break
                    f_out.write(chunk)
                    total_read += len(chunk)
                    print(f"\r  Extracted: {total_read / (1024**3):.2f} GB", end='')
        
        print("\n✅ Extraction complete!")
        return True
    except Exception as e:
        print(f"\n❌ Error extracting: {e}")
        return False

def create_androzoo_database():
    """Create the main AndroZoo database from CSV"""
    print(f"\n📊 Creating {ANDROZOO_DB}...")
    
    if os.path.exists(ANDROZOO_DB):
        print(f"⚠️  {ANDROZOO_DB} already exists.")
        choice = input("Recreate database? (y/n): ").lower()
        if choice == 'y':
            os.remove(ANDROZOO_DB)
        else:
            return True
    
    try:
        conn = sqlite3.connect(ANDROZOO_DB)
        cursor = conn.cursor()
        
        # Create table based on AndroZoo CSV structure
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS apks (
                sha256 TEXT PRIMARY KEY,
                sha1 TEXT,
                md5 TEXT,
                dex_size INTEGER,
                apk_size INTEGER,
                dex_date TEXT,
                pkg_name TEXT,
                vercode INTEGER,
                vt_detection INTEGER,
                vt_scan_date TEXT,
                markets TEXT
            )
        ''')
        
        # Create indexes for common queries
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_pkg_name ON apks(pkg_name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_dex_date ON apks(dex_date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_markets ON apks(markets)')
        
        print("⏳ Reading CSV and inserting data (this takes a while)...")
        
        with open(CSV_EXTRACTED, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader)  # Skip header
            
            batch = []
            count = 0
            batch_size = 10000
            
            for row in reader:
                # Skip the problematic snaggamea APK
                if len(row) > 6 and 'snaggamea' in row[6]:
                    continue
                
                # Ensure we have enough columns
                if len(row) < 11:
                    continue
                
                try:
                    batch.append((
                        row[0],  # sha256
                        row[1],  # sha1
                        row[2],  # md5
                        int(row[3]) if row[3] else None,  # dex_size
                        int(row[4]) if row[4] else None,  # apk_size
                        row[5],  # dex_date
                        row[6],  # pkg_name
                        int(row[7]) if row[7] else None,  # vercode
                        int(row[8]) if row[8] else None,  # vt_detection
                        row[9],  # vt_scan_date
                        row[10]  # markets
                    ))
                    
                    count += 1
                    
                    if len(batch) >= batch_size:
                        cursor.executemany(
                            'INSERT OR IGNORE INTO apks VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                            batch
                        )
                        batch = []
                        print(f"\r  Inserted: {count:,} APKs", end='')
                
                except (ValueError, IndexError) as e:
                    # Skip malformed rows
                    continue
            
            # Insert remaining batch
            if batch:
                cursor.executemany(
                    'INSERT OR IGNORE INTO apks VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                    batch
                )
            
            print(f"\n✅ Inserted {count:,} APKs into database")
        
        conn.commit()
        conn.close()
        
        # Show database size
        db_size = os.path.getsize(ANDROZOO_DB) / (1024**3)
        print(f"📦 Database size: {db_size:.2f} GB")
        
        return True
    
    except Exception as e:
        print(f"❌ Error creating database: {e}")
        import traceback
        traceback.print_exc()
        return False

def create_package_ids_database():
    """Create a filtered database of popular package IDs for UI dropdown"""
    print(f"\n📋 Creating {PACKAGE_IDS_DB} for UI...")
    
    try:
        # Connect to main database
        main_conn = sqlite3.connect(ANDROZOO_DB)
        main_cursor = main_conn.cursor()
        
        # Get packages from Google Play with multiple versions
        print("⏳ Filtering popular packages from Google Play...")
        main_cursor.execute('''
            SELECT pkg_name, COUNT(*) as version_count
            FROM apks
            WHERE markets LIKE '%play.google.com%'
            AND pkg_name IS NOT NULL
            AND pkg_name != ''
            GROUP BY pkg_name
            HAVING version_count >= 3
            ORDER BY version_count DESC
            LIMIT 10000
        ''')
        
        packages = main_cursor.fetchall()
        main_conn.close()
        
        print(f"✅ Found {len(packages)} packages for UI")
        
        # Create package_ids database
        pkg_conn = sqlite3.connect(PACKAGE_IDS_DB)
        pkg_cursor = pkg_conn.cursor()
        
        pkg_cursor.execute('''
            CREATE TABLE IF NOT EXISTS package_ids (
                pkg_name TEXT PRIMARY KEY,
                version_count INTEGER
            )
        ''')
        
        pkg_cursor.executemany(
            'INSERT OR REPLACE INTO package_ids VALUES (?, ?)',
            packages
        )
        
        pkg_conn.commit()
        pkg_conn.close()
        
        print(f"✅ {PACKAGE_IDS_DB} created with {len(packages)} packages")
        return True
    
    except Exception as e:
        print(f"❌ Error creating package_ids database: {e}")
        import traceback
        traceback.print_exc()
        return False

def create_precomputed_directory():
    """Create directory for precomputed data"""
    precomp_dir = Path("precomputed_data")
    if not precomp_dir.exists():
        print(f"\n📁 Creating {precomp_dir}/ directory...")
        precomp_dir.mkdir()
        print("✅ Directory created")
    else:
        print(f"✅ {precomp_dir}/ already exists")

def verify_setup():
    """Verify the setup is complete"""
    print("\n" + "="*60)
    print("🔍 Verification")
    print("="*60)
    
    checks = []
    
    # Check databases
    if os.path.exists(ANDROZOO_DB):
        size = os.path.getsize(ANDROZOO_DB) / (1024**3)
        conn = sqlite3.connect(ANDROZOO_DB)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM apks')
        count = cursor.fetchone()[0]
        conn.close()
        print(f"✅ {ANDROZOO_DB}: {size:.2f} GB, {count:,} APKs")
        checks.append(True)
    else:
        print(f"❌ {ANDROZOO_DB}: NOT FOUND")
        checks.append(False)
    
    if os.path.exists(PACKAGE_IDS_DB):
        conn = sqlite3.connect(PACKAGE_IDS_DB)
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM package_ids')
        count = cursor.fetchone()[0]
        conn.close()
        print(f"✅ {PACKAGE_IDS_DB}: {count:,} packages")
        checks.append(True)
    else:
        print(f"❌ {PACKAGE_IDS_DB}: NOT FOUND")
        checks.append(False)
    
    if Path("precomputed_data").exists():
        print(f"✅ precomputed_data/ directory exists")
        checks.append(True)
    else:
        print(f"⚠️  precomputed_data/ directory missing")
        checks.append(False)
    
    return all(checks)

def main():
    print("="*60)
    print("🚀 Janus - AndroZoo Database Bootstrap")
    print("="*60)
    print(f"Working directory: {os.getcwd()}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    # Step 1: Download CSV
    if not download_csv():
        print("\n❌ Failed to download CSV. Exiting.")
        sys.exit(1)
    
    # Step 2: Extract CSV
    if not extract_csv():
        print("\n❌ Failed to extract CSV. Exiting.")
        sys.exit(1)
    
    # Step 3: Create main database
    if not create_androzoo_database():
        print("\n❌ Failed to create AndroZoo database. Exiting.")
        sys.exit(1)
    
    # Step 4: Create package IDs database
    if not create_package_ids_database():
        print("\n❌ Failed to create package_ids database. Exiting.")
        sys.exit(1)
    
    # Step 5: Create precomputed directory
    create_precomputed_directory()
    
    # Step 6: Verify everything
    if verify_setup():
        print("\n" + "="*60)
        print("🎉 SUCCESS! Janus is ready to use!")
        print("="*60)
        print("\nNext steps:")
        print("  1. (Optional) Precompute some popular packages:")
        print("     python precompute_packages.py")
        print("  2. Start Janus:")
        print("     python index.py")
        print("  3. Access at: http://127.0.0.1:8050")
        print("="*60)
    else:
        print("\n⚠️  Setup incomplete. Please check errors above.")
        sys.exit(1)

if __name__ == "__main__":
    main()
