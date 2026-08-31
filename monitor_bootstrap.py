#!/usr/bin/env python3
"""
Database Activity Monitor

Run this in a SEPARATE terminal while bootstrap is running
to see if the database is actually being processed.
"""

import sqlite3
import time
import sys
import os

def monitor_database():
    """Monitor database activity"""
    
    print("="*70)
    print("DATABASE ACTIVITY MONITOR")
    print("="*70)
    print("\nThis script monitors if bootstrap_androzoo.py is actually working.")
    print("Press Ctrl+C to stop monitoring.\n")
    
    db_file = "androzoo.db"
    pkg_db_file = "package_ids.db"
    
    if not os.path.exists(db_file):
        print(f"❌ {db_file} not found!")
        return
    
    print(f"Monitoring: {db_file}")
    print("="*70)
    
    last_size = 0
    check_count = 0
    
    while True:
        try:
            check_count += 1
            
            # Check main database
            db_size = os.path.getsize(db_file) / (1024**3)
            
            # Check if package_ids.db exists and is growing
            pkg_db_exists = os.path.exists(pkg_db_file)
            pkg_db_size = os.path.getsize(pkg_db_file) / 1024 if pkg_db_exists else 0
            
            # Try to connect and get record counts
            try:
                conn = sqlite3.connect(db_file, timeout=1)
                cursor = conn.cursor()
                
                # Quick count query
                cursor.execute("SELECT COUNT(*) FROM apks")
                apk_count = cursor.fetchone()[0]
                
                conn.close()
                
                # Check if package_ids.db has data
                pkg_count = 0
                if pkg_db_exists:
                    try:
                        pkg_conn = sqlite3.connect(pkg_db_file, timeout=1)
                        pkg_cursor = pkg_conn.cursor()
                        pkg_cursor.execute("SELECT COUNT(*) FROM package_ids")
                        pkg_count = pkg_cursor.fetchone()[0]
                        pkg_conn.close()
                    except:
                        pkg_count = 0
                
                # Display status
                print(f"\n[Check #{check_count}] {time.strftime('%H:%M:%S')}")
                print(f"  androzoo.db:")
                print(f"    Size: {db_size:.2f} GB")
                print(f"    APKs: {apk_count:,}")
                
                if pkg_db_exists:
                    print(f"  package_ids.db:")
                    print(f"    Size: {pkg_db_size:.1f} KB")
                    print(f"    Packages: {pkg_count:,}")
                    
                    if pkg_count > 0:
                        print(f"  ✅ package_ids.db is being populated!")
                    else:
                        print(f"  ⏳ package_ids.db exists but empty (query processing...)")
                else:
                    print(f"  ⏳ package_ids.db not created yet")
                
                # Check if database size changed
                if db_size != last_size:
                    print(f"  ✅ Database is ACTIVE (size changed)")
                    last_size = db_size
                else:
                    print(f"  📊 Database size stable (query may be processing)")
                
            except sqlite3.OperationalError as e:
                print(f"\n[Check #{check_count}] {time.strftime('%H:%M:%S')}")
                print(f"  ⚠️  Database is LOCKED (query is running)")
                print(f"  androzoo.db: {db_size:.2f} GB")
                print(f"  This means bootstrap is ACTIVELY querying")
                
            except Exception as e:
                print(f"\n❌ Error checking database: {e}")
            
            # Wait before next check
            print(f"\nNext check in 10 seconds...")
            time.sleep(10)
            
        except KeyboardInterrupt:
            print("\n\n👋 Monitoring stopped")
            break

def check_process_alive():
    """Check if bootstrap process is running"""
    print("\n" + "="*70)
    print("PROCESS CHECK")
    print("="*70)
    
    try:
        import subprocess
        
        # Check for python processes running bootstrap
        result = subprocess.run(
            ['ps', 'aux'], 
            capture_output=True, 
            text=True, 
            timeout=5
        )
        
        bootstrap_processes = [
            line for line in result.stdout.split('\n') 
            if 'bootstrap' in line.lower() and 'python' in line.lower()
        ]
        
        if bootstrap_processes:
            print("\n✅ Bootstrap process(es) found:")
            for proc in bootstrap_processes:
                print(f"  {proc}")
        else:
            print("\n⚠️  No bootstrap process found")
            print("   Either it finished or it's not running")
        
    except Exception as e:
        print(f"\n⚠️  Could not check processes: {e}")

if __name__ == "__main__":
    print("\n🔍 Checking if bootstrap is alive...\n")
    check_process_alive()
    
    print("\n" + "="*70)
    
    choice = input("\nStart monitoring database? (y/n): ").lower()
    if choice == 'y':
        monitor_database()
    else:
        print("\n💡 Tip: Run this script to monitor database activity")
        print("   python3 monitor_bootstrap.py")
