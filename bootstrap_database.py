#!/usr/bin/env python3
"""
Database Bootstrap Script

This script handles the complete database setup process:
1. Downloads the latest AndroZoo CSV data
2. Extracts and validates the data
3. Creates the SQLite database
4. Generates filtered package IDs for the UI

Run this script before starting the web app.
"""

import gzip
import json
import os
import sqlite3
import urllib.request
from pathlib import Path
from tqdm import tqdm

from create_sql_db import create_sqlite_db


class DatabaseBootstrap:
    def __init__(self):
        self.csv_filename = "latest_with-added-date.csv"
        self.db_filename = "androzoo.db"
        self.package_ids_filename = "filtered_package_ids_with_counts10_ver.json"
        self.androzoo_url = "https://androzoo.uni.lu/static/lists/latest_with-added-date.csv.gz"
    
    def download_file_with_progress(self, url, output_path):
        """Download a file with a progress bar"""
        class DownloadProgressBar(tqdm):
            def update_to(self, b=1, bsize=1, tsize=None):
                if tsize is not None:
                    self.total = tsize
                self.update(b * bsize - self.n)

        print(f"Downloading {url}...")
        with DownloadProgressBar(unit='B', unit_scale=True, miniters=1, desc=url.split('/')[-1]) as t:
            urllib.request.urlretrieve(url, filename=output_path, reporthook=t.update_to)
        print("Download completed.")
    
    def check_file_corruption(self, file_path):
        """Basic file corruption check"""
        try:
            with open(file_path, 'rb') as f:
                # Try to read a chunk of the file to check for corruption
                f.read(1024)
            return False
        except Exception:
            return True
    
    def extract_gzip_file(self, gz_path, output_path):
        """Extract a gzip file"""
        print("Extracting gzip file...")
        try:
            with gzip.open(gz_path, "rb") as f_in:
                with open(output_path, "wb") as f_out:
                    f_out.write(f_in.read())
            print("Extraction completed.")
            
            # Clean up the gzip file
            os.remove(gz_path)
            print("Cleaned up temporary gzip file.")
            
            return True
        except Exception as e:
            print(f"Error extracting file: {e}")
            return False
    
    def extract_package_ids_with_counts(self, conn, min_count=10):
        """Extract package IDs with their version counts from the database"""
        cursor = conn.cursor()
        cursor.execute("""
        SELECT pkg_name, COUNT(*) as count
        FROM apks
        GROUP BY pkg_name
        HAVING count > ?
        ORDER BY count DESC
        """, (min_count,))
        return [{"name": row[0], "count": row[1]} for row in cursor.fetchall()]
    
    def download_and_extract_csv(self):
        """Download and extract the CSV file if needed"""
        if os.path.isfile(self.csv_filename) and not self.check_file_corruption(self.csv_filename):
            print(f"CSV file {self.csv_filename} already exists and is valid.")
            return True
        
        print(f"CSV file missing or corrupted. Downloading from AndroZoo...")
        gz_filename = self.csv_filename + ".gz"
        
        try:
            self.download_file_with_progress(self.androzoo_url, gz_filename)
            
            if self.extract_gzip_file(gz_filename, self.csv_filename):
                if self.check_file_corruption(self.csv_filename):
                    print("ERROR: Downloaded file is corrupted. Please try again.")
                    return False
                else:
                    print("CSV file successfully downloaded and extracted.")
                    return True
            else:
                return False
                
        except Exception as e:
            print(f"Error downloading CSV file: {e}")
            return False
    
    def create_database(self):
        """Create the SQLite database from CSV data"""
        if os.path.exists(self.db_filename):
            print(f"Database {self.db_filename} already exists.")
            return True
        
        print("Creating SQLite database...")
        try:
            create_sqlite_db(self.csv_filename, self.db_filename)
            print("Database created successfully.")
            return True
        except Exception as e:
            print(f"Error creating database: {e}")
            return False
    
    def generate_package_ids_file(self):
        """Generate the filtered package IDs JSON file"""
        if os.path.isfile(self.package_ids_filename):
            print(f"Package IDs file {self.package_ids_filename} already exists.")
            return True
        
        print("Generating filtered package IDs file...")
        try:
            conn = sqlite3.connect(self.db_filename)
            
            print("Extracting and filtering package IDs...")
            filtered_data = self.extract_package_ids_with_counts(conn, min_count=10)
            print(f"Found {len(filtered_data)} packages with more than 10 versions")
            
            print(f"Saving to {self.package_ids_filename}...")
            with open(self.package_ids_filename, 'w') as f:
                json.dump(filtered_data, f, indent=2)
            
            conn.close()
            print("Package IDs file generated successfully.")
            return True
            
        except Exception as e:
            print(f"Error generating package IDs file: {e}")
            return False
    
    def bootstrap(self):
        """Run the complete database bootstrap process"""
        print("=" * 60)
        print("JANUS DATABASE BOOTSTRAP")
        print("=" * 60)
        
        # Step 1: Download and extract CSV
        if not self.download_and_extract_csv():
            print("❌ Failed to download/extract CSV file")
            return False
        
        # Step 2: Create SQLite database
        if not self.create_database():
            print("❌ Failed to create database")
            return False
        
        # Step 3: Generate package IDs file
        if not self.generate_package_ids_file():
            print("❌ Failed to generate package IDs file")
            return False
        
        print("=" * 60)
        print("✅ DATABASE BOOTSTRAP COMPLETED SUCCESSFULLY")
        print("=" * 60)
        print(f"📁 Database: {self.db_filename}")
        print(f"📁 Package IDs: {self.package_ids_filename}")
        print(f"📁 CSV Data: {self.csv_filename}")
        print("\nYou can now start the web application with: python index.py")
        return True


def main():
    """Main entry point"""
    bootstrap = DatabaseBootstrap()
    success = bootstrap.bootstrap()
    return 0 if success else 1


if __name__ == "__main__":
    exit(main()) 