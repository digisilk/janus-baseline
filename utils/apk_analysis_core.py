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
import os
import re
import time
import json
import logging
import zipfile
import sqlite3
import requests
import tldextract
import multiprocessing as mp
from pathlib import Path
from tqdm import tqdm
from datetime import datetime
from androguard.core.bytecodes import dvm
from androguard.misc import AnalyzeAPK
from utils.dex_parser import DEXParser
from utils.ui_logger import UILogger, ui_logger, should_cancel as session_should_cancel

# Import config values with fallbacks
try:
    from config import MAX_DOWNLOAD_RETRIES, DOWNLOAD_RETRY_CYCLES
except ImportError:
    MAX_DOWNLOAD_RETRIES = 20
    DOWNLOAD_RETRY_CYCLES = 4

def sanitize_string(input_string):
    """Clean and sanitise extracted strings"""
    return input_string.replace('\x00', '')

def truncate_string(s, max_length=100):
    """Truncate string to max length"""
    if len(s) <= max_length:
        return s
    return s[:max_length-3] + "..."

def apply_config_overrides(api_key=None, parser_selection=None, desired_versions=None, num_cores=None):
    """Apply configuration overrides from config.py"""
    try:
        from config import get_effective_config
        config = get_effective_config()
    except ImportError:
        logging.warning("config.py not found, using defaults")
        return api_key, parser_selection, desired_versions, num_cores
    
    # Override API key if configured
    if config['override_api_key'] or not api_key:
        api_key = config['api_key']
    
    # Override parser if configured
    if config['force_parser']:
        parser_selection = config['force_parser']
        logging.info(f"Config override: Using {parser_selection} parser")
    
    # Override max versions if configured
    if config['max_versions'] and desired_versions:
        desired_versions = min(desired_versions, config['max_versions'])
        logging.info(f"Config override: Limited to {desired_versions} versions")
    elif config['max_versions']:
        desired_versions = config['max_versions']
        logging.info(f"Config override: Set to {desired_versions} versions")
    
    # Override cores if configured
    if config['force_single_core']:
        num_cores = 1
        logging.info("Config override: Using single core processing")
    
    return api_key, parser_selection, desired_versions, num_cores

def get_ui_config():
    """Get UI configuration for showing/hiding controls"""
    try:
        from config import get_effective_config
        config = get_effective_config()
        return {
            'show_versions_control': config['show_version_control'],
            'show_parser_control': config['show_parser_selection'],
            'show_cores_control': config['show_core_control'],
            'show_api_key_input': config['show_api_key_input']
        }
    except ImportError:
        logging.warning("config.py not found, showing all UI controls")
        return {
            'show_versions_control': True,
            'show_parser_control': True,
            'show_cores_control': True,
            'show_api_key_input': True
        } 

def extract_apk_dex_files(apk_path):
    """Extract DEX files from APK"""
    dex_files = []
    with zipfile.ZipFile(apk_path, 'r') as z:
        for filename in z.namelist():
            if filename.endswith('.dex'):
                dex_data = z.read(filename)
                dex_files.append(dex_data)
    return dex_files

# ============================================================================
# APK Feature Extraction Functions
# ============================================================================

def extract_apk_features(file_path, data_type='urls', use_cache_json=False, parser_selection='digisilk'):
    """
    Extract features from APK file
    
    Args:
        file_path: Path to APK file
        data_type: Type of data to extract ('urls', 'domains', 'subdomains', etc.)
        use_cache_json: Whether to use cached JSON results
        parser_selection: Parser to use ('digisilk' or 'androguard')
    
    Returns:
        List or dict with extracted features
    """
    json_file_path = f"{file_path}.{data_type}.json"
    
    # Check cache first
    if os.path.exists(json_file_path) and use_cache_json:
        logging.info(f"Using cached data for {file_path}")
        with open(json_file_path, 'r') as json_file:
            return json.load(json_file)
    
    # Initialise data structure
    data = []
    
    try:
        if parser_selection in ["digisilk", "custom_dex"]:  # Support both legacy and new naming
            logging.info(f"Using DigiSilk custom parser for {file_path}")
            dex_files = extract_apk_dex_files(file_path)
            for dex_data in dex_files:
                parser = DEXParser(dex_data)
                parser.parse()
                for string in parser.strings:
                    sanitised_string = sanitize_string(string)
                    urls = re.findall(r'https?://\S+', sanitised_string)
                    data.extend(urls)
        else:  # Androguard parser
            logging.info(f"Using Androguard parser for {file_path}")
            a, d, dx = AnalyzeAPK(file_path)
            logging.info(f"Androguard analysis complete for {file_path}")
            logging.info(f"APK Package name: {a.get_package()}")
            logging.info(f"APK Version name: {a.get_androidversion_name()}")
            logging.info(f"APK Version code: {a.get_androidversion_code()}")
            
            for dex in a.get_all_dex():
                dv = dvm.DalvikVMFormat(dex)
                for string in dv.get_strings():
                    sanitised_string = sanitize_string(string)
                    urls = re.findall(r'https?://\S+', sanitised_string)
                    data.extend(urls)
            
            # Extract additional features if requested (for plotting other features over time)
            if any(dt in data_type for dt in ['permissions', 'services', 'activities', 'providers', 'receivers', 'libraries', 'java_classes']):
                logging.info(f"Extracting additional APK features for {file_path}")
                
                if 'permissions' in data_type:
                    data.extend(a.get_permissions())
                if 'services' in data_type:
                    data.extend(a.get_services())
                if 'activities' in data_type:
                    data.extend(a.get_activities())
                if 'providers' in data_type:
                    data.extend(a.get_providers())
                if 'receivers' in data_type:
                    data.extend(a.get_receivers())
                if 'libraries' in data_type:
                    data.extend(a.get_libraries())
                if 'java_classes' in data_type:
                    for dex in a.get_all_dex():
                        dv = dvm.DalvikVMFormat(dex)
                        for clazz in dv.get_classes():
                            class_name = clazz.get_name()[1:-1].replace('/', '.')
                            data.append(class_name)

        logging.info(f"Extracted {len(data)} items of type {data_type} from {file_path}")

    except Exception as e:
        logging.error(f'Error whilst extracting {data_type} from {file_path}: {str(e)}')

    # Cache the results
    if use_cache_json:
        with open(json_file_path, 'w') as json_file:
            json.dump(data, json_file)
    
    return data

# ============================================================================
# Database and APK Management Functions
# ============================================================================

def initialize_database(db_path):
    """Initialize database - exact copy from original files"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS apks (
        sha256 TEXT PRIMARY KEY,
        pkg_name TEXT,
        vercode TEXT,
        vt_scan_date TEXT
    )
    ''')
    conn.commit()
    conn.close()

def find_sha256_vercode_vtscandate(package_name, db_path, start_date, end_date):
    """Find APK metadata from database"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    query = """
    SELECT sha256, vercode, vt_scan_date
    FROM apks
    WHERE pkg_name = ? AND vt_scan_date BETWEEN ? AND ?
    ORDER BY vt_scan_date
    """

    cursor.execute(query, (package_name, start_date, end_date))
    results = cursor.fetchall()
    conn.close()

    return [(sha256, vercode, vt_scan_date) for sha256, vercode, vt_scan_date in results]

def download_file_with_progress(url, filename):
    """Download file with progress bar"""
    response = requests.get(url, stream=True)
    total = int(response.headers.get('content-length', 0))
    with tqdm(total=total, unit='iB', unit_scale=True) as progress_bar:
        with open(filename, 'wb') as file:
            for data in response.iter_content(chunk_size=1024):
                progress_bar.update(len(data))
                file.write(data)

def download_apk(sha256, vercode, vtscandate, package_name, apikey, universal_cache_dir, max_retries=None, retry_cycles=None):
    """Download a single APK from AndroZoo"""
    # Use config values if not provided
    if max_retries is None:
        max_retries = MAX_DOWNLOAD_RETRIES
            
    if retry_cycles is None:
        retry_cycles = DOWNLOAD_RETRY_CYCLES
    
    apk_path = os.path.join(universal_cache_dir, f"{sha256}.apk")
    if check_apk_in_cache(sha256, universal_cache_dir):
        print(f"APK {sha256} found in cache.")
        return apk_path

    os.makedirs(universal_cache_dir, exist_ok=True)
    url = f"https://androzoo.uni.lu/api/download?apikey={apikey}&sha256={sha256}"
    
    for cycle in range(retry_cycles):
        attempts = 0
        while attempts < max_retries:
            response = requests.get(url, stream=True)
            if response.status_code == 200:
                with open(apk_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=1024):
                        if chunk:
                            f.write(chunk)
                if os.path.getsize(apk_path) > 1000:
                    return apk_path
                else:
                    attempts += 1
            else:
                attempts += 1
            if attempts >= max_retries:
                time.sleep(200)
    
    return None

def download_apk_worker(sha256, vercode, vtscandate, package_name, apikey, universal_cache_dir):
    """Worker function for downloading a single APK"""
    try:
        result = download_apk(sha256, vercode, vtscandate, package_name, apikey, universal_cache_dir)
        return result
    except Exception as e:
        logging.error(f"Error in download worker for {sha256}: {str(e)}")
        return None

# ============================================================================
# APK Processing Functions
# ============================================================================

def process_file(sha256, folder_path, vercode, vtscandate, parser_selection):
    """
    Process a single APK file and extract features
    
    Returns:
        List of dictionaries with extracted data
    """
    file_path = os.path.join(folder_path, f"{sha256}.apk")
    if not os.path.exists(file_path):
        logging.warning(f"Warning: APK file not found for SHA256 {sha256}")
        return None

    try:
        logging.info(f"Processing file {sha256}.apk with {parser_selection} parser")
        urls = extract_apk_features(file_path, 'urls', True, parser_selection)
        
        processed_data = []
        for url in urls:
            parsed_url = tldextract.extract(url)
            subdomain = '.'.join(filter(None, [parsed_url.subdomain, parsed_url.domain, parsed_url.suffix]))
            domain = '.'.join(filter(None, [parsed_url.domain, parsed_url.suffix]))
            processed_data.append({
                'version': vercode,
                'vtscandate': vtscandate,
                'urls': url,
                'subdomains': subdomain,
                'domains': domain
            })
        logging.info(f"Processed {len(processed_data)} items for {sha256}.apk")
        return processed_data
        
    except Exception as e:
        logging.error(f"Error processing file {sha256}.apk: {str(e)}")
        return None

def process_package_apks(universal_cache_dir, package_name, num_cores, parser_selection):
    """Process APKs for a package using multiprocessing"""
    with open(os.path.join(universal_cache_dir, 'apk_log.json'), 'r') as f:
        apk_log = json.load(f)

    relevant_apks = apk_log.get(package_name, [])

    if not relevant_apks:
        print(f"No relevant APKs found for {package_name}")
        return []

    pool = mp.Pool(num_cores, maxtasksperchild=4)
    results = pool.starmap(process_file, [
        (apk['sha256'], universal_cache_dir, apk['vercode'], apk['vtscandate'], parser_selection) 
        for apk in relevant_apks
    ])
    pool.close()
    pool.join()

    all_data = []
    for result in results:
        if result is not None:
            all_data.extend(result)

    if not all_data:
        print(f"No data extracted from APKs for {package_name}")

    del results
    import gc
    gc.collect()
    return all_data

# ============================================================================
# Validation and Cleanup Functions
# ============================================================================

def check_apk_in_cache(sha256, universal_cache_dir):
    """Check if APK exists in cache"""
    apk_path = os.path.join(universal_cache_dir, f"{sha256}.apk")
    return os.path.exists(apk_path)

def validate_and_clean_apks(universal_cache_dir, trash_dir):
    """Validate APK files and move corrupted ones to trash"""
    import shutil
    os.makedirs(trash_dir, exist_ok=True)
    for filename in os.listdir(universal_cache_dir):
        if filename.endswith('.apk'):
            apk_path = os.path.join(universal_cache_dir, filename)
            try:
                with zipfile.ZipFile(apk_path, 'r') as zip_ref:
                    zip_ref.testzip()
            except zipfile.BadZipFile:
                print(f"Corrupted APK detected: {apk_path}")
                trash_path = os.path.join(trash_dir, filename)
                shutil.move(apk_path, trash_path)
                print(f"Moved corrupted APK to trash: {trash_path}")

# ============================================================================
# Utility Functions
# ============================================================================

def calculate_sampling_frequency(total_versions, desired_versions):
    """Calculate sampling frequency for version selection"""
    return max(1, total_versions // desired_versions)

# ============================================================================
# Download Functions
# ============================================================================

def find_folders_for_package(base_directory, package_name_pattern):
    """Find folders matching package pattern"""
    matching_folders = []
    for folder_name in os.listdir(base_directory):
        if package_name_pattern in folder_name and os.path.isdir(os.path.join(base_directory, folder_name)):
            matching_folders.append(os.path.join(base_directory, folder_name))
    return matching_folders

def get_most_recent_folder(matching_folders):
    """Get most recent folder from list"""
    if not matching_folders:
        return None
    return max(matching_folders, key=os.path.getmtime)

# ============================================================================
# Configuration Management
# ============================================================================
