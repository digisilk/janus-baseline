# FILE: generate_precomputed_data.py

import json
import os
import sqlite3
from pathlib import Path

PRECOMPUTED_DIR = 'precomputed_data'
DB_PATH = 'androzoo.db'
PACKAGE_JSON = 'filtered_package_ids_with_counts10_ver.json'

def get_packages_to_process():
    """Load packages from JSON"""
    with open(PACKAGE_JSON, 'r') as f:
        data = json.load(f)
        if isinstance(data, list) and data and isinstance(data[0], dict):
            return [pkg['name'] for pkg in data]
        elif isinstance(data, list):
            return data
        else:
            return list(data.keys())

def get_apk_info_from_db(package_name, limit=10):
    """Get APK info from database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    query = """
        SELECT sha256, pkg_name, vercode, vt_detection, vt_scan_date
        FROM apks
        WHERE pkg_name = ?
        ORDER BY vt_scan_date ASC
        LIMIT ?
    """
    
    cursor.execute(query, (package_name, limit))
    rows = cursor.fetchall()
    conn.close()
    
    return [{
        'sha256': row[0],
        'pkg_name': row[1],
        'vercode': row[2],
        'vt_detection': row[3],
        'vtscandate': row[4]
    } for row in rows]

def precompute_package(package_name):
    """Precompute data for a single package"""
    print(f"Processing {package_name}...")
    
    # Get APK info
    apks = get_apk_info_from_db(package_name)
    
    if not apks:
        print(f"  No APKs found for {package_name}")
        return None
    
    # Create output directory
    output_dir = Path(PRECOMPUTED_DIR) / 'packages' / package_name
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Create dummy data structure (you'll need to run actual analysis separately)
    processed_apks = []
    all_urls = set()
    all_domains = set()
    all_subdomains = set()
    
    for apk in apks:
        processed_apks.append({
            'sha256': apk['sha256'],
            'vercode': apk['vercode'],
            'vtscandate': apk['vtscandate'],
            'features': {
                'urls': [],
                'domains': [],
                'subdomains': []
            }
        })
    
    # Save results
    data = {
        'metadata': {
            'package_name': package_name,
            'processed_date': 'pending_analysis'
        },
        'apks': processed_apks,
        'features': {
            'urls': [],
            'domains': [],
            'subdomains': []
        }
    }
    
    output_file = output_dir / 'data.json'
    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"  Created structure at {output_file}")
    return data

def main():
    """Main function to precompute all packages"""
    # Get packages to process
    packages = get_packages_to_process()
    print(f"Found {len(packages)} packages")
    
    # Create base directory
    Path(PRECOMPUTED_DIR).mkdir(exist_ok=True)
    Path(PRECOMPUTED_DIR).joinpath('packages').mkdir(exist_ok=True)
    
    # Process each package
    processed_count = 0
    for i, package in enumerate(packages, 1):
        print(f"\n[{i}/{len(packages)}] {package}")
        result = precompute_package(package)
        if result:
            processed_count += 1
    
    # Save metadata
    metadata = {
        'total_packages': processed_count,
        'processed_packages': packages[:processed_count],
        'stats': {
            'total_packages': processed_count,
            'total_apks': processed_count * 10
        },
        'last_updated': 'pending_analysis'
    }
    
    metadata_file = Path(PRECOMPUTED_DIR) / 'metadata.json'
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"\n? Completed! Created structure for {processed_count}/{len(packages)} packages")
    print(f"?? Data saved to: {PRECOMPUTED_DIR}/")
    print("\n??  NOTE: This created empty structures. You need to run actual APK analysis to populate them.")

if __name__ == "__main__":
    main()