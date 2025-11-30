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
import gc
import json
import logging
import multiprocessing as mp
import os
import re
import shutil
import time
import zipfile
from datetime import datetime
from pathlib import Path
import pandas as pd
import requests
import tldextract
from androguard.core.bytecodes import dvm
from androguard.misc import AnalyzeAPK
from dash import html
from tqdm import tqdm
import threading
from utils.dex_parser import DEXParser, extract_apk_dex_files
from utils.ui_logger import UILogger, ui_logger, register_process, should_cancel as session_should_cancel
import plotly.io as pio
from dash.exceptions import PreventUpdate
from utils.db_connection import initialize_pool, execute_query
import uuid
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
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
_mp_context = mp.get_context('spawn')
download_semaphore = _mp_context.Semaphore(3)

def initialize_database(db_path):
    """Initialise the database and connection pool"""
    # Initialise the connection pool
    initialize_pool(db_path, max_connections=20)
    
    # Create table if it doesn't exist
    execute_query('''
    CREATE TABLE IF NOT EXISTS apks (
        sha256 TEXT PRIMARY KEY,
        pkg_name TEXT,
        vercode TEXT,
        vt_scan_date TEXT
    )
    ''', commit=True)
    
    logger.info(f"Database initialised: {db_path}")

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

def process_apks(n_clicks, api_key, start_date, end_date, package_list_input, desired_versions, highlight_config, num_cores, parser_selection, session_id=None):
    """
    Process APKs for analysis with session tracking
    
    Args:
        n_clicks: Button click count
        api_key: AndroZoo API key
        start_date: Start date for analysis
        end_date: End date for analysis
        package_list_input: Package name to analyse
        desired_versions: Number of versions to analyse
        highlight_config: Configuration for highlighting
        num_cores: Number of CPU cores to use
        parser_selection: Parser to use (digisilk or androguard)
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

    if n_clicks is None:
        raise PreventUpdate

    package_list = [package_list_input.strip()]  # Only accept one package
    
    logger.info("Starting APK processing")

    start_date_str = datetime.strptime(start_date, '%Y-%m-%d').strftime('%Y-%m-%d ') + "23:59:59.999999"
    end_date_str = datetime.strptime(end_date, '%Y-%m-%d').strftime('%Y-%m-%d ') + "23:59:59.999999"

    # Validate and clean APKs
    base_dir = Path(__file__).parent.parent.absolute()
    universal_cache_dir = os.path.join(base_dir, "apk_cache")
    trash_dir = os.path.join(base_dir, "trash")
    # Skip validation for now
    logger.info("APK cache validated and cleaned")

    results = {}

    for package_name in package_list:
        logger.info(f"Processing package: {package_name}")

        if package_name:
            try:
                logger.info(f"Downloading APKs for {package_name}")
                
                # Check for cancellation
                if session_should_cancel(session_id):
                    logger.info("Process cancelled")
                    return None
                
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
                    parser_selection,
                    session_id
                )

                # Check for cancellation after each major step
                if session_should_cancel(session_id):
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

def process_package(package_name, base_directory, apikey, db_path, start_date, end_date, desired_versions, highlight_config, num_cores, parser_selection, session_id=None):
    # Get the session logger
    if session_id:
        logger_data = UILogger.get_logger(session_id)
        logger = logger_data['logger']
    else:
        logger = ui_logger.logger
        
    # Register this thread with the session if provided
    if session_id:
        register_process(session_id, threading.current_thread())
        
    logger.info(f"Processing package: {package_name}")
    
    # Initialise database and connection pool
    initialize_database(db_path)
    
    # Create cache directory
    universal_cache_dir = os.path.join(base_directory, "apk_cache")
    os.makedirs(universal_cache_dir, exist_ok=True)
    
    # Download the required APKs
    logger.info(f"Downloading APKs for {package_name}")
    downloaded_apks = download_apks([package_name], apikey, universal_cache_dir, db_path, start_date, end_date, desired_versions, session_id)
    
    # Check for cancellation
    if session_id and session_should_cancel(session_id):
        logger.info("Process cancelled during download")
        return None
    
    if not downloaded_apks:
        logger.warning(f"No APKs downloaded for {package_name}")
        return None
        
    # Process the downloaded APKs
    logger.info(f"Processing APKs for {package_name}")
    all_data = process_package_apks(universal_cache_dir, package_name, num_cores, parser_selection)
    
    # Check for cancellation
    if session_id and session_should_cancel(session_id):
        logger.info("Process cancelled during processing")
        return None
    
    if not all_data:
        logger.warning(f"No data extracted from APKs for {package_name}")
        return None
    
    # Plot the data for each data type
    figs = {}
    for data_type in ['urls', 'subdomains', 'domains']:
        # Check for cancellation
        if session_id and session_should_cancel(session_id):
            logger.info(f"Process cancelled during plotting {data_type}")
            return None
            
        logger.info(f"Plotting {data_type} for {package_name}")
        
        # Convert highlight_config to the format for plot_data
        formatted_highlight_config = {}
        if highlight_config:
            formatted_highlight_config = {item['regex']: item['color'] for item in highlight_config}
            
        # Plot the data
        fig = plot_data(all_data, package_name, formatted_highlight_config, data_type)
        figs[data_type] = fig
    
    logger.info(f"Completed processing for {package_name}")
    return figs

def download_apks(package_names, apikey, universal_cache_dir, db_path, start_date, end_date, desired_versions, session_id=None):
    """Download APKs for a list of packages within a date range with session tracking"""
    # Get the logger
    if session_id:
        logger_data = UILogger.get_logger(session_id)
        logger = logger_data['logger']
    else:
        logger = ui_logger.logger
    
    # Ensure cache directory exists
    os.makedirs(universal_cache_dir, exist_ok=True)
    
    download_tasks = []
    apk_log = {}
    
    for package_name in package_names:
        # Check if we should cancel
        if session_id and session_should_cancel(session_id):
            logger.info("Download cancelled - session check")
            return None
            
        # Get the list of APKs for this package
        sha256_vercode_vtscandate_list = find_sha256_vercode_vtscandate(package_name, db_path, start_date, end_date)
        
        if not sha256_vercode_vtscandate_list:
            logger.warning(f"No APKs found for {package_name} in date range")
            continue
            
        # Log the number of APKs found
        logger.info(f"Found {len(sha256_vercode_vtscandate_list)} APKs for {package_name}")
        
        # Always include the latest app version
        latest_app = sha256_vercode_vtscandate_list[-1]
        download_tasks.append((*latest_app, package_name, apikey, universal_cache_dir))
        
        # Sample the remaining versions
        sampling_frequency = calculate_sampling_frequency(len(sha256_vercode_vtscandate_list) - 1, desired_versions - 1)
        sampled_apps = sha256_vercode_vtscandate_list[:-1][::sampling_frequency]
        
        for sha256, vercode, vtscandate in sampled_apps:
            download_tasks.append((sha256, vercode, vtscandate, package_name, apikey, universal_cache_dir))
        
        # Record the apps we're going to download
        apk_log[package_name] = [
            {"sha256": sha256, "vercode": vercode, "vtscandate": vtscandate}
            for sha256, vercode, vtscandate in [latest_app] + sampled_apps
        ]
    
    # Log how many APKs we're downloading
    logger.info(f"Downloading {len(download_tasks)} APKs")
    
    # Download each APK sequentially to have better control over cancellation
    results = []
    for i, task in enumerate(download_tasks):
        # Check if we should cancel
        if session_id and session_should_cancel(session_id):
            logger.info("Download cancelled during task execution")
            return None
            
        logger.info(f"Downloading APK {i+1}/{len(download_tasks)}: {task[0]}")
        result = download_apk_worker(*task)
        if result:
            results.append(result)
    
    # Save the APK log as JSON
    with open(os.path.join(universal_cache_dir, 'apk_log.json'), 'w') as f:
        json.dump(apk_log, f, indent=2)
    
    logger.info(f"Downloaded {len(results)} APKs successfully")
    return results

def check_apk_in_cache_(sha256, universal_cache_dir):
    apk_path = os.path.join(universal_cache_dir, f"{sha256}.apk")
    return os.path.exists(apk_path)

def plot_data(all_data, package_name, highlight_config, data_type):
    print(f"Preparing data for plotting {data_type}...")
    
    MAX_STRING_LENGTH = 100

    if not all_data:
        print(f"No data available for {package_name}")
        return None

    df = pd.DataFrame(all_data)
    
    if data_type not in df.columns:
        print(f"Error: '{data_type}' not found in the data. Available columns: {df.columns.tolist()}")
        return None

    df = df[['version', 'vtscandate', data_type]].rename(columns={data_type: 'Data'})
    df['Data'] = df['Data'].apply(lambda x: truncate_string(x, MAX_STRING_LENGTH))
    df['Count'] = 1
    df = df.groupby(['version', 'vtscandate', 'Data']).sum().reset_index()

    if df.empty:
        print(f"No data to plot for {data_type}.")
        return None

    # convert date to datetime and format it as a string
    df['vtscandate'] = pd.to_datetime(df['vtscandate']).dt.strftime('%Y-%m-%d')
    df['version'] = df['version'].astype(str)

    # pivot the count and date data
    df_count_pivot = df.pivot_table(index='Data', columns='version', values='Count', aggfunc='sum', fill_value=0)
    df_date_pivot = df.pivot_table(index='Data', columns='version', values='vtscandate', aggfunc='first')

    sorted_versions = sorted(df_count_pivot.columns,
                             key=lambda s: [int(u) if u.isdigit() else u for u in re.split('(\d+)', s)])
    df_count_pivot = df_count_pivot[sorted_versions]
    df_date_pivot = df_date_pivot[sorted_versions]

    # create a new list for x-axis labels combining version and date
    sorted_versions_with_dates = []
    for version in sorted_versions:
        #find the earliest date for this version
        earliest_date = df[df['version'] == version]['vtscandate'].min()
        label = f"{version} ({earliest_date})"
        sorted_versions_with_dates.append(label)

    sorted_versions = sorted(df['version'].unique(),
                             key=lambda x: [int(part) if part.isdigit() else part for part in re.split('([0-9]+)', x)])

    #evolutionary sorting logic
    # 1: count appearances of each domain across all versions
    data_appearances = {}
    for version in sorted_versions:
        for item in df[df['version'] == version]['Data'].unique():
            data_appearances[item] = data_appearances.get(item, 0) + 1

    # 2: sort domains within each version based on appearances and re-addition
    version_sorted_data = {}
    for version in sorted_versions:
        current_version_data = df[df['version'] == version]['Data'].unique().tolist()
        # sort domains within the current version based on their total appearances (descending)
        sorted_data = sorted(current_version_data, key=lambda x: (-data_appearances[x], x))
        version_sorted_data[version] = sorted_data

    # 3: build the master list of domains, maintaining the staircase effect
    #initialize a master list of domains across all versions
    master_data_list = []
    seen_data = set()

    for version in sorted_versions:
        #retrieve the sorted list of domains for the current version
        current_version_sorted_data = version_sorted_data[version]
        #filter to include only new or re-added domains not already in master_domain_list
        new_or_readded_data = [item for item in current_version_sorted_data if item not in seen_data]
        master_data_list.extend(new_or_readded_data)
        #update the seen_domains set
        seen_data.update(new_or_readded_data)

    sorted_data = master_data_list

    # Reverse the highlight_config items
    highlight_config_items = list(highlight_config.items())[::-1]

    #create the hover text matrix
    hover_text = []
    for item in sorted_data:
        hover_text_row = []
        for version in sorted_versions:
            count = df_count_pivot.at[item, version] if version in df_count_pivot.columns else 0
            date = df_date_pivot.at[item, version] if version in df_date_pivot.columns else ''
            hover_text_data = f"Feature: {truncate_string(item, MAX_STRING_LENGTH)}<br>Version: {version}<br>Count: {count}<br>Date: {date}"
            hover_text_row.append(hover_text_data)
        hover_text.append(hover_text_row)

    # Prepare text summary
    text_summary = "Feature Analysis Summary:\n"
    for item in df_count_pivot.index:
        highlighted = False
        highlight_details = ""
        # Check for regex matches and prepare highlighting
        for pattern, color in highlight_config_items:
            if re.search(pattern, item, re.IGNORECASE):
                highlighted = True
                highlight_details = f"Highlight: {pattern} (Colour: {color})\n"

        text_summary += f"\nFeature: {item}\n"
        if highlighted:
            text_summary += f"  {highlight_details}"

        for version in sorted_versions:
            count = df_count_pivot.at[item, version]
            date = df_date_pivot.at[item, version] if df_date_pivot.at[item, version] is not None else "nan"
            text_summary += f"  Version {version} ({date}): Count = {count}\n"

    # Save summary to text file
    with open(f"{package_name}_data_summary.txt", 'w', encoding='utf-8') as file:
        file.write(text_summary)

    text_summary = "Feature Analysis Summary by Version:\n"
    # Iterate through each version
    for version in sorted_versions:
        date = df[df['version'] == version]['vtscandate'].min()  # Get date for version
        text_summary += f"\nVersion {version} ({date if date != 'nan' else 'No Date Available'}):\n"
        # Check each subdomain for current version
        for item in df_count_pivot.index:
            count = df_count_pivot.at[item, version]
            if count > 0:  # Only list subdomains with count > 0
                text_summary += f" {item}   Count: {count}\n"
                # Check for regex matches and add them
                for pattern, color in highlight_config_items:
                    if re.search(pattern, item, re.IGNORECASE):
                        text_summary += f" MATCH: {pattern} (Colour: {color})\n"

    # Save condensed summary to text file
    with open(f"{package_name}_condensed_summary.txt", 'w', encoding='utf-8') as file:
        file.write(text_summary)

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

        # Add colour highlighting config, workaround for plotly
        shapes = []
        for data_idx, item in enumerate(sorted_data):
            for version_idx, version in enumerate(sorted_versions):
                count = df_count_pivot.loc[item, version]
                if count > 0:
                    for pattern, color in highlight_config_items:
                        if re.search(pattern, item, re.IGNORECASE):
                            shapes.append({
                                'type': 'rect',
                                'x0': version_idx - 0.5,
                                'y0': data_idx - 0.5,
                                'x1': version_idx + 0.5,
                                'y1': data_idx + 0.5,
                                'fillcolor': color,
                                'opacity': 0.3,
                                'line': {'width': 0},
                            })
                            break  # Stop after first match to avoid overlapping shapes

        title_description = data_type.capitalize()

        # Update x-axis labels
        fig.update_layout(
            shapes=shapes,
            title=f"{title_description} Presence and Frequency Across Versions, {package_name}",
            xaxis=dict(tickmode='array', tickvals=sorted_versions, ticktext=sorted_versions_with_dates),
            yaxis=dict(autorange="reversed"))  # Reverse y-axis to show earliest versions at top
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

        # Add colour highlighting config, workaround for plotly
        shapes = []
        for data_idx, item in enumerate(sorted_data):
            for version_idx, version in enumerate(sorted_versions):
                count = df_count_pivot.loc[item, version]
                if count > 0:
                    for pattern, color in highlight_config_items:
                        if re.search(pattern, item, re.IGNORECASE):
                            shapes.append({
                                'type': 'rect',
                                'x0': version_idx - 0.5,
                                'y0': data_idx - 0.5,
                                'x1': version_idx + 0.5,
                                'y1': data_idx + 0.5,
                                'fillcolor': color,
                                'opacity': 0.3,
                                'line': {'width': 0},
                            })
                            break  # Stop after first match to avoid overlapping shapes

        title_description = data_type.capitalize()

        # Update x-axis labels
        fig.update_layout(
            shapes=shapes,
            title=f"{title_description} Presence and Frequency Across Versions, {package_name}",
            xaxis=dict(tickmode='array', tickvals=sorted_versions, ticktext=sorted_versions_with_dates),
            yaxis=dict(autorange="reversed")  # Reverse y-axis to show earliest versions at top
        )

        return {
            'figure': fig,
            'feature_info': feature_info,
            'too_large_to_display': False,
            'feature_count': len(sorted_data)
        }

def generate_download_link(fig, package_name, data_type):
    # Unique filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{package_name}_{data_type}_{timestamp}.html"
    
    # Convert figure to HTML
    plot_html = pio.to_html(fig, full_html=False)
    
    # Encode HTML content
    encoded = base64.b64encode(plot_html.encode()).decode()
    
    # Create download link
    href = f"data:text/html;base64,{encoded}"
    
    return html.Div([
        html.A(
            'Download Figure',
            id=f'download-link-{data_type}',
            download=filename,
            href=href,
            target="_blank",
            className="btn btn-primary mt-2"
        )
    ])


