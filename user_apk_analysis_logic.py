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
import base64
import logging
import re
import time
import zipfile
from datetime import datetime
from pathlib import Path
import uuid
import pandas as pd
import requests
import tldextract
from androguard.core.bytecodes import dvm
from androguard.misc import AnalyzeAPK
from dash import html
from tqdm import tqdm
import threading
import logging
from io import StringIO
import os
import tempfile
from utils.dex_parser import DEXParser, extract_apk_dex_files
from utils.ui_logger import UILogger, register_process, should_cancel
import sqlite3
import plotly.io as pio
from dash.exceptions import PreventUpdate
import utils.apk_analysis_core
from utils.apk_analysis_core import (
    calculate_sampling_frequency,
    check_apk_in_cache,
    download_apk,
    download_apk_worker,
    download_file_with_progress,
    extract_apk_dex_files,
    extract_apk_features,
    find_folders_for_package,
    find_sha256_vercode_vtscandate,
    get_most_recent_folder,
    process_file,
    process_package_apks,
    sanitize_string,
    truncate_string,
    validate_and_clean_apks,
)
import plotly.graph_objects as go
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
current_process = None
logger = logging.getLogger(__name__)
ui_logger = UILogger()

def initialize_database(db_path):
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

def check_and_print_csv(filename):
    try:
        data = pd.read_csv(filename, nrows=5)
        if data.empty:
            print("CSV file is empty.")
        else:
            print("First few rows of the CSV file:")
            print(data)
    except pd.errors.EmptyDataError:
        print("CSV file is empty.")
    except Exception as e:
        print(f"Error reading CSV file: {e}")

def process_apks(n_clicks, api_key, start_date, end_date, package_list_input, desired_versions, highlight_config, num_cores, parser_selection):
    if n_clicks is None:
        raise PreventUpdate

    # Generate session ID for this process
    session_id = str(uuid.uuid4())
    
    # Register current thread with session
    register_process(session_id, threading.current_thread())
    
    # Get session logger
    logger_data = UILogger.get_logger(session_id)
    logger = logger_data['logger']
    logger.info("Starting new APK processing")
    
    package_list = [package_list_input.strip()]  # Only accept one package
    
    logger.info("Starting APK processing")

    start_date_str = datetime.strptime(start_date, '%Y-%m-%d').strftime('%Y-%m-%d ') + "23:59:59.999999"
    end_date_str = datetime.strptime(end_date, '%Y-%m-%d').strftime('%Y-%m-%d ') + "23:59:59.999999"

    # Validate and clean APKs
    base_dir = Path(__file__).parent.parent.absolute()
    universal_cache_dir = os.path.join(base_dir, "apk_cache")
    trash_dir = os.path.join(base_dir, "trash")
    validate_and_clean_apks(universal_cache_dir, trash_dir)
    logger.info("APK cache validated and cleaned")

    results = {}

    for package_name in package_list:
        logger.info(f"Processing package: {package_name}")

        if package_name:
            try:
                logger.info(f"Downloading APKs for {package_name}")
                figs = process_package(
                    package_name.strip(),
                    os.getcwd(),
                    api_key,
                    'androzoo.db',
                    start_date_str,
                    end_date_str,
                    int(desired_versions),
                    highlight_config,
                    num_cores,
                    parser_selection
                )

                # Check for cancellation after each major step
                if should_cancel(session_id):
                    logger.info("Process cancelled")
                    return None

                if figs:
                    results.update(figs)
                    logger.info(f"Figures generated for {package_name}")
                else:
                    logger.warning(f"No figures generated for package {package_name}")
            except Exception as e:
                logger.error(f"Error processing package {package_name}: {str(e)}")

    logger.info("APK processing complete")
    return results

def process_uploaded_apks(stored_data, highlight_config, num_cores, parser_selection, sort_order, session_id=None):
    """
    Process uploaded APKs for analysis with session tracking
    
    Args:
        stored_data: Data from uploaded APKs (with server_path already stored)
        highlight_config: Configuration for highlighting
        num_cores: Number of CPU cores to use
        parser_selection: Parser to use (digisilk or androguard)
        sort_order: Order to sort the results
        session_id: Unique session identifier
    """
    # Ensure we have a session ID
    if session_id is None:
        session_id = str(uuid.uuid4())
    
    # Register this process with the session
    register_process(session_id, threading.current_thread())
    
    # Get session logger
    logger_data = UILogger.get_logger(session_id)
    logger = logger_data['logger']
    
    try:
        logger.info(f"Processing {len(stored_data)} uploaded APK files")
        
        # Create empty results
        results = {
            'urls': None,
            'domains': None,
            'subdomains': None
        }
        
        # Process each data type
        for data_type in ['urls', 'domains', 'subdomains']:
            logger.info(f"Processing {data_type} from uploaded APKs")
            
            # Extract features from APKs
            all_data = []
            for i, item in enumerate(stored_data):
                # Check for cancellation
                if should_cancel(session_id):
                    logger.info("Process cancelled")
                    return None
                
                filename = item['filename']
                apk_path = item['server_path']
                
                logger.info(f"Extracting features from {filename} ({i+1}/{len(stored_data)})")
                # Extract features 
                features = extract_apk_features(apk_path, 'urls', False, parser_selection)
                
                if features:
                    # Create data entries for plotting
                    for feature in features:
                        parsed_url = tldextract.extract(feature)
                        subdomain = '.'.join(filter(None, [parsed_url.subdomain, parsed_url.domain, parsed_url.suffix]))
                        domain = '.'.join(filter(None, [parsed_url.domain, parsed_url.suffix]))
                        
                        # Use the filename (without extension) as version identifier
                        version_name = os.path.splitext(filename)[0]
                        
                        # Create the data entry based on the data type we're currently processing
                        if data_type == 'urls':
                            data_value = feature
                        elif data_type == 'domains':
                            data_value = domain
                        elif data_type == 'subdomains':
                            data_value = subdomain
                        else:
                            continue
                        
                        # Only add non-empty data
                        if data_value:
                            all_data.append({
                                'Data': data_value,
                                'version': version_name,
                                'ui_order': i,
                                'vtscandate': datetime.now().strftime('%Y-%m-%d')
                            })
            
            # Check for cancellation before plotting
            if should_cancel(session_id):
                logger.info("Process cancelled")
                return None
            
            # Plot the data
            if all_data:
                logger.info(f"Plotting {data_type} data ({len(all_data)} items)")
                # Pass highlight_config as-is (it's already in list format with 'regex' and 'color' keys)
                result = plot_data(all_data, "user_uploaded_apks", highlight_config, data_type, sort_order)
                results[data_type] = result
            else:
                logger.warning(f"No {data_type} data found in the uploaded APKs")
        
        logger.info("APK processing complete")
        return results
        
    except Exception as e:
        logger.error(f"Error processing uploaded APKs: {str(e)}")
        return None

def process_package(package_name, base_directory, apikey, db_path, start_date, end_date, desired_versions, highlight_config, num_cores, parser_selection):
    ui_logger.logger.info(f"Starting APK processing")
    
    # Create a directory for the APK cache
    base_dir = Path(__file__).parent.parent.absolute()
    universal_cache_dir = os.path.join(base_dir, "apk_cache")
    os.makedirs(universal_cache_dir, exist_ok=True)

    # Download the APKs if needed
    ui_logger.logger.info(f"Downloading APKs for {package_name}")
    downloaded_apks = download_apks([package_name], apikey, universal_cache_dir, db_path, start_date, end_date, desired_versions)
    
    # Process cancellation check
    if downloaded_apks is None:
        ui_logger.logger.info("Process cancelled during download")
        return None
    
    result = {}
    # Process the APKs for this package
    ui_logger.logger.info(f"Processing APKs for {package_name}")
    processed_data = process_package_apks(universal_cache_dir, package_name, num_cores, parser_selection)
    
    if processed_data is None:
        ui_logger.logger.info("Process cancelled during processing")
        return None

    if processed_data:
        formatted_highlight_config = {}
        if highlight_config:
            formatted_highlight_config = {item['regex']: item['color'] for item in highlight_config}
            
        # Plot the data
        for data_type in ['urls', 'domains', 'subdomains']:
            ui_logger.logger.info(f"Plotting {data_type} for {package_name}")
            result[data_type] = plot_data(processed_data, package_name, formatted_highlight_config, data_type, 'version_ascending')
    
    return result

def download_apks(package_names, apikey, universal_cache_dir, db_path, start_date, end_date, desired_versions):
    os.makedirs(universal_cache_dir, exist_ok=True)
    all_downloaded_apks = []
    
    for package_name in package_names:
        # Get all SHA256s for this package
        apk_data = find_sha256_vercode_vtscandate(package_name, db_path, start_date, end_date)
        
        if not apk_data:
            UILogger.get_logger('default')['logger'].warning(f"No APKs found for {package_name} between {start_date} and {end_date}")
            continue
            
        # Determine how many and which versions to download
        if len(apk_data) > desired_versions:
            # If there are more versions than requested, sample them
            frequency = calculate_sampling_frequency(len(apk_data), desired_versions)
            samples = apk_data[::frequency]
        else:
            # Use all available versions
            samples = apk_data
            
        # Download each APK
        downloaded_for_package = []
        for i, (sha256, vercode, vtscandate) in enumerate(samples):
            # Check for cancellation
            if threading.current_thread() != threading.current_thread():
                return None
                
            apk_path = check_apk_in_cache(sha256, universal_cache_dir)
            
            if not apk_path:
                # Download if not in cache
                try:
                    download_apk(sha256, vercode, vtscandate, package_name, apikey, universal_cache_dir)
                    downloaded_for_package.append((sha256, vercode, vtscandate))
                except Exception as e:
                    UILogger.get_logger('default')['logger'].error(f"Error downloading APK {sha256}: {str(e)}")
            else:
                downloaded_for_package.append((sha256, vercode, vtscandate))
                
        all_downloaded_apks.extend(downloaded_for_package)
        
    return all_downloaded_apks

def should_cancel():
    return False

def save_uploaded_files(stored_data, temp_dir):
    apk_files = []
    for item in stored_data:
        content_type, content_string = item['content'].split(',')
        decoded = base64.b64decode(content_string)
        file_path = os.path.join(temp_dir, item['filename'])
        with open(file_path, 'wb') as f:
            f.write(decoded)
        # Return tuple of (filename, filepath) to match expected format
        apk_files.append((item['filename'], file_path))
    return apk_files

def save_uploaded_file_to_server(content, filename):
    # Create directory to store uploaded APKs if needed
    upload_dir = "uploaded_apks"
    os.makedirs(upload_dir, exist_ok=True)
    
    # Decode the base64 content
    content_type, content_string = content.split(',')
    decoded = base64.b64decode(content_string)
    
    # Create unique filename to avoid conflicts
    unique_filename = f"{uuid.uuid4()}_{filename}"
    file_path = os.path.join(upload_dir, unique_filename)
    
    # Write the file
    with open(file_path, 'wb') as f:
        f.write(decoded)
    
    return file_path

def plot_data(all_data, package_name, highlight_config, data_type, sort_order):
    print(f"Preparing data for plotting {data_type}...")
    
    MAX_STRING_LENGTH = 100

    if not all_data:
        print(f"No data available for {package_name}")
        return None

    df = pd.DataFrame(all_data)
    
    if 'Data' not in df.columns:
        print(f"Error: 'Data' not found in the data. Available columns: {df.columns.tolist()}")
        return None

    df['Data'] = df['Data'].apply(lambda x: truncate_string(x, MAX_STRING_LENGTH))
    df['Count'] = 1
    df = df.groupby(['version', 'Data', 'ui_order']).sum().reset_index()

    if df.empty:
        print(f"No data to plot for {data_type}.")
        return None

    # Sort versions based on sort order
    if sort_order == 'ui':
        sorted_versions = df.sort_values('ui_order')['version'].unique()
    else:  # 'vercode'
        sorted_versions = sorted(df['version'].unique(), key=lambda x: int(x) if x.isdigit() else x)

    # Pivot the count data
    df_count_pivot = df.pivot_table(index='Data', columns='version', values='Count', aggfunc='sum', fill_value=0)
    df_count_pivot = df_count_pivot[sorted_versions]

    # Create x-axis labels
    sorted_versions_with_dates = sorted_versions

    # Evolutionary sorting logic
    # 1: Count appearances of each domain across all versions
    data_appearances = {}
    for version in sorted_versions:
        for item in df[df['version'] == version]['Data'].unique():
            data_appearances[item] = data_appearances.get(item, 0) + 1

    # 2: Sort domains within each version based on appearances
    version_sorted_data = {}
    for version in sorted_versions:
        current_version_data = df[df['version'] == version]['Data'].unique().tolist()
        # Sort domains within current version by total appearances (descending)
        sorted_data = sorted(current_version_data, key=lambda x: (-data_appearances[x], x))
        version_sorted_data[version] = sorted_data

    # 3: Build master list of domains, maintaining staircase effect
    master_data_list = []
    seen_data = set()

    for version in sorted_versions:
        current_version_sorted_data = version_sorted_data[version]
        new_or_readded_data = [item for item in current_version_sorted_data if item not in seen_data]
        master_data_list.extend(new_or_readded_data)
        seen_data.update(new_or_readded_data)

    sorted_data = master_data_list

    # Create hover text matrix
    hover_text = []
    for item in sorted_data:
        hover_text_row = []
        for version in sorted_versions:
            count = df_count_pivot.at[item, version] if version in df_count_pivot.columns else 0
            hover_text_data = f"Feature: {truncate_string(item, MAX_STRING_LENGTH)}<br>Version: {version}<br>Count: {count}"
            hover_text_row.append(hover_text_data)
        hover_text.append(hover_text_row)

    # Create feature info list
    feature_info = []
    for item in sorted_data:
        info = {
            'feature': truncate_string(item, MAX_STRING_LENGTH),
            'alienvault_link': f"https://otx.alienvault.com/indicator/domain/{item}",
            'whois_link': f"https://www.whois.com/whois/{item}"
        }
        feature_info.append(info)

    # Set threshold for max features to display
    MAX_FEATURES_TO_DISPLAY = 250

    if len(sorted_data) > MAX_FEATURES_TO_DISPLAY:
        # Create figure without displaying it
        fig = go.Figure(data=go.Heatmap(
            showscale=False,
            z=df_count_pivot.reindex(sorted_data).values,
            x=sorted_versions,
            y=sorted_data,
            text=hover_text,
            hoverinfo='text',
            colorscale=[[0, 'white'], [0.01, 'grey'], [0.4, '#505050'], [1, 'black']],
            zmin=0,
            zmax=df_count_pivot.max().max(),
            xgap=1,
            ygap=1
        ))

        # Update layout
        fig.update_layout(
            title=f"{data_type.capitalize()} Presence and Frequency Across Versions, {package_name}",
            xaxis=dict(tickmode='array', tickvals=sorted_versions, ticktext=sorted_versions_with_dates),
            yaxis=dict(autorange="reversed")
        )

        # Create shapes for highlighting
        shapes = []
        if highlight_config:  # Check if highlight config exists
            for data_idx, item in enumerate(sorted_data):
                for version_idx, version in enumerate(sorted_versions):
                    count = df_count_pivot.loc[item, version]
                    if count > 0:
                        matched_color = None
                        for highlight in reversed(highlight_config):
                            if re.search(highlight['regex'], item, re.IGNORECASE):
                                matched_color = highlight['color']
                                break
                        if matched_color:
                            shapes.append({
                                'type': 'rect',
                                'x0': version_idx - 0.5,
                                'y0': data_idx - 0.5,
                                'x1': version_idx + 0.5,
                                'y1': data_idx + 0.5,
                                'fillcolor': matched_color,
                                'opacity': 0.3,
                                'line': {'width': 0},
                            })

        fig.update_layout(shapes=shapes)

        return {
            'figure': fig,
            'feature_info': feature_info,
            'too_large_to_display': True,
            'feature_count': len(sorted_data)
        }
    else:
        # Create heatmap
        fig = go.Figure(data=go.Heatmap(
            showscale=False,
            z=df_count_pivot.reindex(sorted_data).values,
            x=sorted_versions,
            y=sorted_data,
            text=hover_text,
            hoverinfo='text',
            colorscale=[[0, 'white'], [0.01, 'grey'], [0.4, '#505050'], [1, 'black']],
            zmin=0,
            zmax=df_count_pivot.max().max(),
            xgap=1,
            ygap=1
        ))

        # Create shapes for highlighting
        shapes = []
        if highlight_config:  # Check if highlight config exists
            for data_idx, item in enumerate(sorted_data):
                for version_idx, version in enumerate(sorted_versions):
                    count = df_count_pivot.loc[item, version]
                    if count > 0:
                        matched_color = None
                        for highlight in reversed(highlight_config):
                            if re.search(highlight['regex'], item, re.IGNORECASE):
                                matched_color = highlight['color']
                                break
                        if matched_color:
                            shapes.append({
                                'type': 'rect',
                                'x0': version_idx - 0.5,
                                'y0': data_idx - 0.5,
                                'x1': version_idx + 0.5,
                                'y1': data_idx + 0.5,
                                'fillcolor': matched_color,
                                'opacity': 0.3,
                                'line': {'width': 0},
                            })

        # Update layout
        fig.update_layout(
            shapes=shapes,
            title=f"{data_type.capitalize()} Presence and Frequency Across Versions, {package_name}",
            xaxis=dict(tickmode='array', tickvals=list(range(len(sorted_versions))), ticktext=sorted_versions_with_dates),
            yaxis=dict(autorange="reversed")
        )

        return {
            'figure': fig,
            'feature_info': feature_info,
            'too_large_to_display': False,
            'feature_count': len(sorted_data)
        }

# Old implementation for backwards compatibility

def generate_download_link(fig, package_name, data_type):
    # Generate unique filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{package_name}_{data_type}_{timestamp}.html"
    
    # Convert figure to HTML
    plot_html = pio.to_html(fig, full_html=False)
    
    # Encode HTML content
    encoded = base64.b64encode(plot_html.encode()).decode()
    
    # Create download link
    href = f"data:text/html;base64,{encoded}"
    
    return html.Div(children=[
        html.A(
            children='Download Figure',
            id=f'download-link-{data_type}',
            download=filename,
            href=href,
            target="_blank",
            className="btn btn-primary mt-2"
        )
    ])
