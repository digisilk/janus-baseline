# Copyright 2025 Elisa
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#!/usr/bin/env python3
"""
Precompute Package Data Script

This script precomputes connectivity data for specified packages and saves them
in the format expected by the precomputed connectivity analysis page.

Usage:
    python precompute_packages.py
    
Edit the PACKAGES_TO_PROCESS list below to specify which packages to precompute.
"""

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from tqdm import tqdm
import logging

# Add the current directory to path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from logic.precomputed_connectivity_logic import (
    download_apks, 
    initialize_database
)
from utils.apk_analysis_core import (
    process_package_apks,
    find_sha256_vercode_vtscandate,
    calculate_sampling_frequency
)
from utils.ui_logger import ui_logger
import config

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
PRECOMPUTED_DATA_DIR = 'precomputed_data'
PACKAGES_DIR = os.path.join(PRECOMPUTED_DATA_DIR, 'packages')
CACHE_DIR = 'apk_cache'
DB_PATH = 'androzoo.db'

# ========================================
# CONFIGURATION - EDIT THIS SECTION TO CUSTOMIZE
# ========================================

# List of packages to precompute
PACKAGES_TO_PROCESS = ['com.unciv.app','com.duolingo','com.tencent.mtt','com.whatsapp','com.google.android.apps.photos','com.odskill.learning',
                       'com.offbitstudio.american.policedriving.offlinegame','com.odiousapps.justwalking','com.ogq.phonethemeshop',
                       'com.offworldsoftware.androidgamepadgames','com.oh.ohapp','com.ogi.heavy.cargo.truck.driver.simulator.offroad.game',
                       'com.offlinemusic'
    # Add more packages here in format: 'com.company.appname'
]

# Processing configuration
DEFAULT_VERSIONS = 10  # Number of versions to process per package
PARSER_SELECTION = 'digisilk'  # 'digisilk' (faster) or 'androguard' (more detailed)
NUM_CORES = 1  # Number of CPU cores to use (1 recommended for stability)

# Date range for APK selection
# Set both to None to use last 5 years automatically
# Or specify exact dates in format: 'YYYY-MM-DD 23:59:59.999999'
START_DATE = None  
END_DATE = None

# Example with specific dates:
# START_DATE = '2020-01-01 23:59:59.999999'
# END_DATE = '2024-12-31 23:59:59.999999'

class PrecomputeProcessor:
    def __init__(self):
        self.api_key = self._get_api_key()
        self.processed_packages = []
        self.failed_packages = []
        
        # Create directories
        os.makedirs(PRECOMPUTED_DATA_DIR, exist_ok=True)
        os.makedirs(PACKAGES_DIR, exist_ok=True)
        os.makedirs(CACHE_DIR, exist_ok=True)
        
        # Initialize database
        initialize_database(DB_PATH)
        
    def _get_api_key(self):
        """Get AndroZoo API key from config or environment"""
        api_key = config.ANDROZOO_API_KEY
        if not api_key:
            api_key = os.environ.get('ANDROZOO_API_KEY')
            api_key = 'YOUR API KEY HERE'
        if not api_key:
            raise ValueError("AndroZoo API key not found. Set it in config.py or as environment variable ANDROZOO_API_KEY")
        return api_key
    
    def _get_date_range(self):
        """Get date range for APK selection"""
        if START_DATE and END_DATE:
            return START_DATE, END_DATE
        elif not START_DATE and not END_DATE:
            # Default: last 5 years
            from datetime import datetime, timedelta
            end_date = datetime.now()
            start_date = end_date - timedelta(days=5*365)
            return (
                start_date.strftime('%Y-%m-%d 23:59:59.999999'),
                end_date.strftime('%Y-%m-%d 23:59:59.999999')
            )
        else:
            raise ValueError("Both START_DATE and END_DATE must be specified or both None")
    
    def process_package(self, package_name):
        """Process a single package and save precomputed data"""
        logger.info(f"Processing package: {package_name}")
        
        try:
            # Get date range
            start_date, end_date = self._get_date_range()
            
            # Download APKs
            logger.info(f"Downloading APKs for {package_name}")
            downloaded_apks = download_apks(
                [package_name], 
                self.api_key, 
                CACHE_DIR, 
                DB_PATH, 
                start_date, 
                end_date, 
                DEFAULT_VERSIONS,
                session_id=None
            )
            
            if not downloaded_apks:
                logger.warning(f"No APKs downloaded for {package_name}")
                return False
            
            # Process APKs to extract features
            logger.info(f"Processing APKs for {package_name}")
            all_data = process_package_apks(CACHE_DIR, package_name, NUM_CORES, PARSER_SELECTION)
            
            if not all_data:
                logger.warning(f"No data extracted from APKs for {package_name}")
                return False
            
            # Convert the all_data to precomputed format
            precomputed_data = self._convert_to_precomputed_format(package_name, all_data)
            
            # Save the data
            package_dir = os.path.join(PACKAGES_DIR, package_name)
            os.makedirs(package_dir, exist_ok=True)
            
            data_file = os.path.join(package_dir, 'data.json')
            with open(data_file, 'w') as f:
                json.dump(precomputed_data, f, indent=2)
            
            logger.info(f"Saved precomputed data for {package_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error processing {package_name}: {str(e)}")
            return False
    
    def _convert_to_precomputed_format(self, package_name, all_data):
        """Convert processed APK data to precomputed format"""
        # Group data by version
        version_data = {}
        for item in all_data:
            version = item['version']
            if version not in version_data:
                version_data[version] = {
                    'version': version,
                    'vtscandate': item['vtscandate'],
                    'features': {
                        'urls': [],
                        'domains': [],
                        'subdomains': []
                    }
                }
            
            # Add features to respective lists
            if 'urls' in item and item['urls']:
                version_data[version]['features']['urls'].append(item['urls'])
            if 'domains' in item and item['domains']:
                version_data[version]['features']['domains'].append(item['domains'])
            if 'subdomains' in item and item['subdomains']:
                version_data[version]['features']['subdomains'].append(item['subdomains'])
        
        # Convert to APK list format
        apks = []
        all_features = {'urls': set(), 'domains': set(), 'subdomains': set()}
        
        for version, data in version_data.items():
            apk_data = {
                'vercode': version,
                'vtscandate': data['vtscandate'],
                'features': {
                    'urls': data['features']['urls'],
                    'domains': data['features']['domains'], 
                    'subdomains': data['features']['subdomains']
                }
            }
            apks.append(apk_data)
            
            # Collect all unique features
            for data_type in ['urls', 'domains', 'subdomains']:
                all_features[data_type].update(data['features'][data_type])
        
        # Convert sets to sorted lists
        for data_type in all_features:
            all_features[data_type] = sorted(list(all_features[data_type]))
        
        # Sort APKs by scan date
        apks.sort(key=lambda x: x['vtscandate'])
        
        return {
            'metadata': {
                'package_name': package_name,
                'processed_date': datetime.now().isoformat(),
                'total_apks': len(apks),
                'date_range': {
                    'start': min(apk['vtscandate'] for apk in apks),
                    'end': max(apk['vtscandate'] for apk in apks)
                }
            },
            'apks': apks,
            'features': all_features
        }
    
    def update_metadata(self):
        """Update the main metadata.json file"""
        metadata = {
            'processed_packages': self.processed_packages,
            'last_updated': datetime.now().isoformat(),
            'stats': {
                'total_packages': len(self.processed_packages),
                'total_features': 0,  # Could calculate this if needed
                'failed_packages': self.failed_packages
            }
        }
        
        metadata_file = os.path.join(PRECOMPUTED_DATA_DIR, 'metadata.json')
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        logger.info(f"Updated metadata with {len(self.processed_packages)} packages")
    
    def process_all_packages(self):
        """Process all packages in the list"""
        logger.info(f"Starting precomputation for {len(PACKAGES_TO_PROCESS)} packages")
        
        for i, package_name in enumerate(PACKAGES_TO_PROCESS, 1):
            logger.info(f"Processing package {i}/{len(PACKAGES_TO_PROCESS)}: {package_name}")
            
            try:
                success = self.process_package(package_name)
                if success:
                    self.processed_packages.append(package_name)
                    logger.info(f"✓ Successfully processed {package_name}")
                else:
                    self.failed_packages.append(package_name)
                    logger.warning(f"✗ Failed to process {package_name}")
                    
            except KeyboardInterrupt:
                logger.info("Process interrupted by user")
                break
            except Exception as e:
                logger.error(f"Unexpected error processing {package_name}: {str(e)}")
                self.failed_packages.append(package_name)
            
            # Small delay between packages
            time.sleep(1)
        
        # Update metadata
        self.update_metadata()
        
        # Summary
        logger.info("=" * 50)
        logger.info("PRECOMPUTATION SUMMARY")
        logger.info("=" * 50)
        logger.info(f"Successfully processed: {len(self.processed_packages)} packages")
        logger.info(f"Failed packages: {len(self.failed_packages)}")
        
        if self.processed_packages:
            logger.info("Successfully processed packages:")
            for pkg in self.processed_packages:
                logger.info(f"  ✓ {pkg}")
        
        if self.failed_packages:
            logger.info("Failed packages:")
            for pkg in self.failed_packages:
                logger.info(f"  ✗ {pkg}")
        
        logger.info(f"Precomputed data saved in: {PRECOMPUTED_DATA_DIR}")

def main():
    """Main entry point"""
    print("🔄 JANUS Precompute Packages Script")
    print("=" * 50)
    print(f"Packages to process: {len(PACKAGES_TO_PROCESS)}")
    print(f"Versions per package: {DEFAULT_VERSIONS}")
    print(f"Parser: {PARSER_SELECTION}")
    print(f"Output directory: {PRECOMPUTED_DATA_DIR}")
    print("=" * 50)
    
    # Check if database exists
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found: {DB_PATH}")
        print("Please run bootstrap_database.py first")
        return 1
    
    # Check API key
    try:
        processor = PrecomputeProcessor()
        print(f"✓ AndroZoo API key configured")
    except ValueError as e:
        print(f"❌ {str(e)}")
        return 1
    
    # Confirm before starting
    response = input("\nProceed with precomputation? (y/N): ")
    if response.lower() != 'y':
        print("Cancelled")
        return 0
    
    # Start processing
    start_time = time.time()
    processor.process_all_packages()
    end_time = time.time()
    
    print(f"\n🎉 Precomputation completed in {end_time - start_time:.2f} seconds")
    return 0

if __name__ == "__main__":
    exit(main()) 