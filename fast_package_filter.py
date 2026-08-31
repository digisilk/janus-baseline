#!/usr/bin/env python3
"""
Fast Package ID Generator with Progress Tracking

This script replaces the slow filtering step in bootstrap_androzoo.py
It shows progress and saves results incrementally.
"""

import sqlite3
import time
import sys

def create_package_ids_with_progress():
    """Create package_ids.db with progress tracking"""
    
    print("="*70)
    print("FAST PACKAGE ID GENERATOR")
    print("="*70)
    
    ANDROZOO_DB = "androzoo.db"
    PACKAGE_IDS_DB = "package_ids.db"
    MIN_VERSIONS = 3
    
    print(f"\nConnecting to {ANDROZOO_DB}...")
    conn = sqlite3.connect(ANDROZOO_DB)
    cursor = conn.cursor()
    
    # Get total count of unique packages
    print("\n📊 Counting unique packages...")
    cursor.execute("SELECT COUNT(DISTINCT pkg_name) FROM apks WHERE pkg_name IS NOT NULL")
    total_packages = cursor.fetchone()[0]
    print(f"   Total unique packages: {total_packages:,}")
    
    # Create output database
    print(f"\n📝 Creating {PACKAGE_IDS_DB}...")
    out_conn = sqlite3.connect(PACKAGE_IDS_DB)
    out_cursor = out_conn.cursor()
    
    out_cursor.execute('''
        CREATE TABLE IF NOT EXISTS package_ids (
            pkg_name TEXT PRIMARY KEY,
            version_count INTEGER
        )
    ''')
    out_conn.commit()
    
    # Method 1: Fast approach - get all package names first, then count
    print("\n⚡ Fast Method: Processing in batches...")
    print("   Step 1: Getting all package names...")
    
    cursor.execute("""
        SELECT DISTINCT pkg_name 
        FROM apks 
        WHERE pkg_name IS NOT NULL 
        AND pkg_name != ''
        AND markets LIKE '%play.google.com%'
    """)
    
    package_names = [row[0] for row in cursor.fetchall()]
    total_to_process = len(package_names)
    print(f"   Found {total_to_process:,} Google Play packages to process")
    
    print("\n   Step 2: Counting versions for each package...")
    
    batch_size = 100
    processed = 0
    qualified_packages = 0
    batch_data = []
    
    start_time = time.time()
    
    for i, pkg_name in enumerate(package_names):
        # Count versions for this package
        cursor.execute("""
            SELECT COUNT(*) FROM apks 
            WHERE pkg_name = ? 
            AND markets LIKE '%play.google.com%'
        """, (pkg_name,))
        
        count = cursor.fetchone()[0]
        
        if count >= MIN_VERSIONS:
            batch_data.append((pkg_name, count))
            qualified_packages += 1
        
        processed += 1
        
        # Save batch
        if len(batch_data) >= batch_size:
            out_cursor.executemany(
                'INSERT OR REPLACE INTO package_ids VALUES (?, ?)',
                batch_data
            )
            out_conn.commit()
            batch_data = []
        
        # Progress update
        if processed % 100 == 0 or processed == total_to_process:
            elapsed = time.time() - start_time
            rate = processed / elapsed if elapsed > 0 else 0
            remaining = (total_to_process - processed) / rate if rate > 0 else 0
            
            percent = (processed / total_to_process) * 100
            
            # Progress bar
            bar_width = 40
            filled = int(bar_width * processed / total_to_process)
            bar = '█' * filled + '░' * (bar_width - filled)
            
            print(f"\r   [{bar}] {percent:.1f}% | "
                  f"{processed:,}/{total_to_process:,} packages | "
                  f"{qualified_packages:,} with {MIN_VERSIONS}+ versions | "
                  f"ETA: {remaining/60:.1f} min", 
                  end='', flush=True)
    
    # Save remaining
    if batch_data:
        out_cursor.executemany(
            'INSERT OR REPLACE INTO package_ids VALUES (?, ?)',
            batch_data
        )
        out_conn.commit()
    
    print()  # New line after progress bar
    
    total_time = time.time() - start_time
    print(f"\n✅ Completed in {total_time/60:.1f} minutes")
    print(f"   Processed: {processed:,} packages")
    print(f"   Qualified: {qualified_packages:,} packages (with {MIN_VERSIONS}+ versions)")
    
    conn.close()
    out_conn.close()
    
    print("\n" + "="*70)
    print("✅ PACKAGE IDs GENERATED SUCCESSFULLY")
    print("="*70)
    print(f"📁 Output: {PACKAGE_IDS_DB}")
    print(f"📊 Total packages: {qualified_packages:,}")
    print("\nYou can now start Janus: python index.py")

if __name__ == "__main__":
    try:
        create_package_ids_with_progress()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        print("   Partial results may be saved")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
