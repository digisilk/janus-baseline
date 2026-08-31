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
import csv
import gc
import io
import json
import logging
import multiprocessing as mp
import numpy as np
import os
import re
import shutil
import time
import uuid
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
import plotly.graph_objects as go
import threading
from utils.dex_parser import DEXParser, extract_apk_dex_files
from utils.ui_logger import UILogger, ui_logger, register_process, should_cancel as session_should_cancel
from utils.apk_analysis_core import (
    apply_config_overrides,
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
progress = {
    'current_task': '',
    'total_tasks': 0,
    'completed_tasks': 0
}
import plotly.io as pio
from dash.exceptions import PreventUpdate
from utils.db_connection import initialize_pool, execute_query
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
from config import PROCESSING_TIMEOUT

# ---------------------------------------------------------------------------
# Spurious-entry filter
# ---------------------------------------------------------------------------
#
# Strategy: reject only what is unambiguously NOT a network indicator.
# We do NOT apply strict structural patterns for domains/urls because real
# APK traffic includes IP addresses, internal hostnames, non-standard ports,
# and SDK-internal paths that are legitimate indicators.
#
# What we DO reject (unconditionally, all data_types):
#   - Strings containing code/template characters: { } ( ) [ ] < > \ or whitespace
#     These are JS template literals, XML fragments, Java stack traces, etc.
#     e.g. "exa...domString()}" — the ) and } alone are enough to discard it.
#
# What we additionally reject per data_type:
#   urls       — must have a scheme (http:// or https://).  Schemeless strings
#                belong in domains/subdomains, not urls.
#   domains    — must contain at least one dot and must NOT contain "://",
#                which would make it a url fragment rather than a bare domain.
#   subdomains — same as domains.
#
# ---------------------------------------------------------------------------

# Characters that unambiguously flag a string as a code/template artefact.
_REJECT_CHARS = re.compile(r'[{}\(\)\[\]<>\s\\]')

# Minimal per-type guards — deliberately permissive so legitimate indicators
# are never silently discarded.
_SCHEME_RE   = re.compile(r'^https?://', re.IGNORECASE)   # urls must have scheme
_HAS_DOT_RE  = re.compile(r'\.')                          # domains/subdomains need a dot
_HAS_SCHEME_IN_DOMAIN = re.compile(r'://')                # reject if looks like a url fragment


def _is_valid_entry(value: str, data_type: str) -> bool:
    """Return True if *value* should be kept for *data_type*.

    Rejects:
      - non-strings and empty strings
      - anything containing code/template characters (braces, parens, whitespace …)
      - urls that have no http(s):// scheme
      - domains/subdomains that contain no dot, or that contain "://"
    Everything else is kept — we prefer false negatives (showing a borderline
    entry) over false positives (hiding a real indicator).
    """
    if not isinstance(value, str) or not value.strip():
        return False

    # Code/template artefact guard — applies to all types
    if _REJECT_CHARS.search(value):
        return False

    if data_type == 'urls':
        return bool(_SCHEME_RE.match(value))

    if data_type in ('domains', 'subdomains'):
        if not _HAS_DOT_RE.search(value):
            return False
        if _HAS_SCHEME_IN_DOMAIN.search(value):
            return False
        return True

    # Unknown data_type — pass through
    return True


def _normalise_domain(value: str, data_type: str) -> str:
    """Canonicalise *value* to prevent www-variants appearing as separate rows.

    Rules (non-destructive — if anything fails the original value is returned):
      domains    — use tldextract to strip subdomains including www, leaving
                   only registered_domain.suffix.  If tldextract cannot parse
                   it (e.g. bare IP, internal hostname) the original is kept.
      subdomains — lower-case and strip a leading "www." only.
      urls       — lower-case scheme and host; path/query preserved as-is.
    """
    if data_type == 'domains':
        try:
            ext = tldextract.extract(value)
            if ext.domain and ext.suffix:
                return f"{ext.domain}.{ext.suffix}".lower()
        except Exception:
            pass
        # tldextract failed or returned empty parts — keep original lowercased
        return value.lower()

    if data_type == 'subdomains':
        normalised = value.lower()
        if normalised.startswith('www.'):
            normalised = normalised[4:]
        return normalised

    if data_type == 'urls':
        try:
            from urllib.parse import urlparse, urlunparse
            parsed = urlparse(value)
            lowered = parsed._replace(
                scheme=parsed.scheme.lower(),
                netloc=parsed.netloc.lower()
            )
            return urlunparse(lowered)
        except Exception:
            pass
        return value.lower()

    return value


def _clean_dataframe(df: pd.DataFrame, data_type: str, max_len: int) -> pd.DataFrame:
    """Apply the full cleaning pipeline to the 'Data' column of *df*:

    1. Truncate to *max_len* characters.
    2. Reject code/template artefacts and per-type structural invalids.
    3. Normalise (www-stripping, domain canonicalisation, case).
       Normalisation is non-destructive — a value that cannot be normalised
       is kept as-is rather than dropped.
    4. Drop rows that are empty strings (should not occur after step 3, but
       kept as a safety net).

    Returns a cleaned copy — does not mutate the input.
    """
    df = df.copy()

    # Step 1 — truncate
    df['Data'] = df['Data'].apply(lambda x: truncate_string(x, max_len))

    # Step 2 — reject artefacts
    valid_mask = df['Data'].apply(lambda x: _is_valid_entry(x, data_type))
    dropped = (~valid_mask).sum()
    if dropped:
        logger.info(
            f"[{data_type}] Dropped {dropped} spurious entries "
            f"(code fragments, template literals, SDK artefacts)"
        )
    df = df[valid_mask].copy()

    # Step 3 — normalise (non-destructive)
    df['Data'] = df['Data'].apply(lambda x: _normalise_domain(x, data_type))

    # Step 4 — safety net: drop any empty strings
    df = df[df['Data'].str.len() > 0].copy()

    return df


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def initialize_database(db_path):
    """Initialise the database and connection pool"""
    initialize_pool(db_path, max_connections=20)
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


# ---------------------------------------------------------------------------
# Top-level APK processing entry point
# ---------------------------------------------------------------------------

def process_apks(n_clicks, api_key, start_date, end_date, package_list_input,
                 desired_versions, highlight_config, num_cores, parser_selection,
                 session_id=None):
    """
    Process APKs for analysis with session tracking.

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
    api_key, parser_selection, desired_versions, num_cores = apply_config_overrides(
        api_key, parser_selection, desired_versions, num_cores
    )

    if session_id is None:
        session_id = str(uuid.uuid4())

    register_process(session_id, threading.current_thread())

    logger_data = UILogger.get_logger(session_id)
    logger = logger_data['logger']

    if n_clicks is None:
        raise PreventUpdate

    package_list = [package_list_input.strip()]

    logger.info("Starting APK processing")

    start_date_str = datetime.strptime(start_date, '%Y-%m-%d').strftime('%Y-%m-%d ') + "23:59:59.999999"
    end_date_str   = datetime.strptime(end_date,   '%Y-%m-%d').strftime('%Y-%m-%d ') + "23:59:59.999999"

    base_dir = Path(__file__).parent.parent.absolute()
    universal_cache_dir = os.path.join(base_dir, "apk_cache")
    trash_dir = os.path.join(base_dir, "trash")
    logger.info("APK cache validated and cleaned")

    results = {}

    for package_name in package_list:
        logger.info(f"Processing package: {package_name}")

        if package_name:
            try:
                logger.info(f"Downloading APKs for {package_name}")

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

                if session_should_cancel(session_id):
                    logger.info("Process cancelled")
                    return None

                if figs:
                    results.update(figs)
                    logger.info(f"Figures generated for {package_name}")
                else:
                    logger.warning(f"No figures generated for {package_name}")
            except Exception as e:
                logger.error(f"Error processing {package_name}: {str(e)}")

    logger.info("APK processing complete")
    return results


# ---------------------------------------------------------------------------
# Package-level orchestration
# ---------------------------------------------------------------------------

def process_package(package_name, base_directory, apikey, db_path, start_date,
                    end_date, desired_versions, highlight_config, num_cores,
                    parser_selection, session_id=None):
    if session_id:
        logger_data = UILogger.get_logger(session_id)
        logger = logger_data['logger']
    else:
        logger = ui_logger.logger

    if session_id:
        register_process(session_id, threading.current_thread())

    logger.info(f"Processing package: {package_name}")

    initialize_database(db_path)

    universal_cache_dir = os.path.join(base_directory, "apk_cache")
    os.makedirs(universal_cache_dir, exist_ok=True)

    download_start_time = time.time()

    logger.info(f"Downloading APKs for {package_name}")
    downloaded_apks = download_apks(
        [package_name], apikey, universal_cache_dir, db_path,
        start_date, end_date, desired_versions, session_id
    )

    if downloaded_apks is None:
        if time.time() - download_start_time > PROCESSING_TIMEOUT:
            logger.warning("Time limit reached during downloads")
        else:
            logger.info("Process cancelled during download")
        return None

    if not downloaded_apks:
        logger.warning(f"No APKs downloaded for {package_name}")
        return None

    logger.info(f"Processing {len(downloaded_apks)} downloaded APKs")
    all_data = process_package_apks(universal_cache_dir, package_name, num_cores, parser_selection)

    if session_id and session_should_cancel(session_id):
        logger.info("Process cancelled during processing")
        return None

    if not all_data:
        logger.warning(f"No data extracted from APKs for {package_name}")
        return None

    figs = {}
    for data_type in ['urls', 'subdomains', 'domains']:
        if session_id and session_should_cancel(session_id):
            logger.info(f"Process cancelled during plotting {data_type}")
            return figs if figs else None

        logger.info(f"Plotting {data_type} for {package_name}")

        formatted_highlight_config = {}
        if highlight_config:
            formatted_highlight_config = {item['regex']: item['color'] for item in highlight_config}

        fig = plot_data(all_data, package_name, formatted_highlight_config, data_type)
        if fig:
            figs[data_type] = fig
            logger.info(f"Generated figure for {data_type}")

    total_time = time.time() - download_start_time
    logger.info(f"Completed full processing for {package_name} in {total_time:.2f} seconds")
    return figs


# ---------------------------------------------------------------------------
# APK download orchestration
# ---------------------------------------------------------------------------

def download_apks(package_names, apikey, universal_cache_dir, db_path,
                  start_date, end_date, desired_versions, session_id=None):
    """Download APKs for a list of packages within a date range."""
    if session_id:
        logger_data = UILogger.get_logger(session_id)
        logger = logger_data['logger']
    else:
        logger = ui_logger.logger

    start_time = time.time()
    os.makedirs(universal_cache_dir, exist_ok=True)

    download_tasks = []
    apk_log = {}

    for package_name in package_names:
        if session_id and session_should_cancel(session_id):
            logger.info("Download cancelled - session check")
            return None

        sha256_vercode_vtscandate_list = find_sha256_vercode_vtscandate(
            package_name, db_path, start_date, end_date
        )

        if not sha256_vercode_vtscandate_list:
            logger.warning(f"No APKs found for {package_name} in date range")
            continue

        logger.info(f"Found {len(sha256_vercode_vtscandate_list)} APKs for {package_name}")

        if len(sha256_vercode_vtscandate_list) <= desired_versions:
            selected_apks = sha256_vercode_vtscandate_list
            logger.info(
                f"Using all {len(selected_apks)} available versions "
                f"(fewer than requested {desired_versions})"
            )
        else:
            indices = np.linspace(
                0, len(sha256_vercode_vtscandate_list) - 1, desired_versions, dtype=int
            )
            selected_apks = [sha256_vercode_vtscandate_list[i] for i in indices]
            logger.info(
                f"Selected {len(selected_apks)} evenly spaced versions "
                f"from {len(sha256_vercode_vtscandate_list)} available"
            )

        for sha256, vercode, vtscandate in selected_apks:
            download_tasks.append((sha256, vercode, vtscandate, package_name, apikey, universal_cache_dir))

    logger.info(f"Attempting to download {len(download_tasks)} APKs (target: {desired_versions})")

    results = []
    successful_downloads = []

    for i, task in enumerate(download_tasks):
        if time.time() - start_time > PROCESSING_TIMEOUT:
            logger.warning(
                f"Time limit ({PROCESSING_TIMEOUT}s) reached after downloading "
                f"{len(results)}/{len(download_tasks)} APKs"
            )
            logger.info(f"Proceeding with partial results: {len(results)} APKs downloaded")
            break

        if session_id and session_should_cancel(session_id):
            logger.info("Download cancelled during task execution")
            return None

        logger.info(f"Downloading APK {i+1}/{len(download_tasks)}: {task[0]}")
        result = download_apk_worker(*task)
        if result:
            results.append(result)
            successful_downloads.append(task)

    for package_name in package_names:
        apk_log[package_name] = [
            {"sha256": sha256, "vercode": vercode, "vtscandate": vtscandate}
            for sha256, vercode, vtscandate, pkg, _, _ in successful_downloads
            if pkg == package_name
        ]

    with open(os.path.join(universal_cache_dir, 'apk_log.json'), 'w') as f:
        json.dump(apk_log, f, indent=2)

    elapsed_time = time.time() - start_time
    if len(results) < desired_versions:
        logger.warning(
            f"Only downloaded {len(results)}/{desired_versions} desired versions "
            f"in {elapsed_time:.2f} seconds"
        )
        if elapsed_time >= PROCESSING_TIMEOUT:
            logger.info(f"This was due to reaching the {PROCESSING_TIMEOUT}s time limit")
    else:
        logger.info(f"Successfully downloaded all {len(results)} APKs in {elapsed_time:.2f} seconds")

    return results if results else None


def check_apk_in_cache_(sha256, universal_cache_dir):
    apk_path = os.path.join(universal_cache_dir, f"{sha256}.apk")
    return os.path.exists(apk_path)


# ---------------------------------------------------------------------------
# Core plotting function
# ---------------------------------------------------------------------------

def plot_data(all_data, package_name, highlight_config, data_type):
    """Build a Plotly heatmap for *data_type* (urls / subdomains / domains).

    Changes vs. original
    --------------------
    1. Spurious / SDK-artefact entries are dropped via _clean_dataframe() which
       applies _is_valid_entry() before aggregation — not after — so they never
       contaminate pivot tables or counts.
    2. www normalisation and domain canonicalisation are handled by
       _normalise_domain() inside _clean_dataframe(); www.example.com and
       example.com now collapse into a single row before the groupby, so the
       heatmap never shows both forms.
    3. truncate_string() is still called first but validation happens on the
       truncated value, so the 100-char cap cannot hide invalid content.
    """
    print(f"Preparing data for plotting {data_type}...")

    MAX_STRING_LENGTH = 100

    if not all_data:
        print(f"No data available for {package_name}")
        return None

    df = pd.DataFrame(all_data)

    if data_type not in df.columns:
        print(
            f"Error: '{data_type}' not found in the data. "
            f"Available columns: {df.columns.tolist()}"
        )
        return None

    # -----------------------------------------------------------------------
    # Build working frame and apply the full cleaning pipeline
    # (truncate → validate → normalise → drop empties) BEFORE aggregation.
    # This is the critical difference from the original code where truncation
    # happened but no validation or normalisation was performed.
    # -----------------------------------------------------------------------
    df = df[['version', 'vtscandate', data_type]].rename(columns={data_type: 'Data'})
    df = _clean_dataframe(df, data_type, MAX_STRING_LENGTH)
    df['Count'] = 1
    df = df.groupby(['version', 'vtscandate', 'Data']).sum().reset_index()

    if df.empty:
        print(f"No data to plot for {data_type} after cleaning.")
        return None

    df['vtscandate'] = pd.to_datetime(df['vtscandate']).dt.strftime('%Y-%m-%d')
    df['version']    = df['version'].astype(str)

    df_count_pivot = df.pivot_table(
        index='Data', columns='version', values='Count',
        aggfunc='sum', fill_value=0
    )
    df_date_pivot = df.pivot_table(
        index='Data', columns='version', values='vtscandate',
        aggfunc='first'
    )

    sorted_versions = sorted(
        df_count_pivot.columns,
        key=lambda s: [int(u) if u.isdigit() else u for u in re.split(r'(\d+)', s)]
    )
    df_count_pivot = df_count_pivot[sorted_versions]
    df_date_pivot  = df_date_pivot[sorted_versions]

    sorted_versions_with_dates = []
    for version in sorted_versions:
        earliest_date = df[df['version'] == version]['vtscandate'].min()
        sorted_versions_with_dates.append(f"{version} ({earliest_date})")

    sorted_versions = sorted(
        df['version'].unique(),
        key=lambda x: [int(p) if p.isdigit() else p for p in re.split(r'([0-9]+)', x)]
    )

    # Evolutionary sorting — staircase effect across versions
    data_appearances = {}
    for version in sorted_versions:
        for item in df[df['version'] == version]['Data'].unique():
            data_appearances[item] = data_appearances.get(item, 0) + 1

    version_sorted_data = {}
    for version in sorted_versions:
        current_version_data = df[df['version'] == version]['Data'].unique().tolist()
        version_sorted_data[version] = sorted(
            current_version_data, key=lambda x: (-data_appearances[x], x)
        )

    master_data_list = []
    seen_data = set()
    for version in sorted_versions:
        new_items = [i for i in version_sorted_data[version] if i not in seen_data]
        master_data_list.extend(new_items)
        seen_data.update(new_items)
    sorted_data = master_data_list

    highlight_config_items = list(highlight_config.items())[::-1]

    # Hover text matrix
    hover_text = []
    for item in sorted_data:
        hover_text_row = []
        for version in sorted_versions:
            count = df_count_pivot.at[item, version] if version in df_count_pivot.columns else 0
            date  = df_date_pivot.at[item, version]  if version in df_date_pivot.columns  else ''
            hover_text_row.append(
                f"Feature: {truncate_string(item, MAX_STRING_LENGTH)}"
                f"<br>Version: {version}"
                f"<br>Count: {count}"
                f"<br>Date: {date}"
            )
        hover_text.append(hover_text_row)

    # Feature info for sidebar / CSV
    feature_info = [
        {
            'feature':          truncate_string(item, MAX_STRING_LENGTH),
            'alienvault_link':  f"https://otx.alienvault.com/indicator/domain/{item}",
            'whois_link':       f"https://www.whois.com/whois/{item}",
        }
        for item in sorted_data
    ]

    MAX_FEATURES_TO_DISPLAY = 250

    def _build_shapes(sorted_data, sorted_versions, df_count_pivot, highlight_config_items):
        shapes = []
        for data_idx, item in enumerate(sorted_data):
            for version_idx, version in enumerate(sorted_versions):
                count = df_count_pivot.loc[item, version]
                if count > 0:
                    for pattern, color in highlight_config_items:
                        if re.search(pattern, item, re.IGNORECASE):
                            shapes.append({
                                'type':      'rect',
                                'x0':        version_idx - 0.5,
                                'y0':        data_idx   - 0.5,
                                'x1':        version_idx + 0.5,
                                'y1':        data_idx   + 0.5,
                                'fillcolor': color,
                                'opacity':   0.3,
                                'line':      {'width': 0},
                            })
                            break
        return shapes

    def _base_heatmap(sorted_data, sorted_versions, df_count_pivot, hover_text):
        return go.Figure(data=go.Heatmap(
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
            ygap=1,
        ))

    title = (
        f"{data_type.capitalize()} Presence and Frequency "
        f"Across Versions, {package_name}"
    )
    xaxis_cfg = dict(
        tickmode='array',
        tickvals=sorted_versions,
        ticktext=sorted_versions_with_dates,
    )

    fig = _base_heatmap(sorted_data, sorted_versions, df_count_pivot, hover_text)
    shapes = _build_shapes(sorted_data, sorted_versions, df_count_pivot, highlight_config_items)
    fig.update_layout(
        shapes=shapes,
        title=title,
        xaxis=xaxis_cfg,
        yaxis=dict(autorange="reversed"),
    )

    csv_export = generate_csv_export_with_highlights(
        all_data, package_name, data_type, highlight_config
    )

    return {
        'figure':              fig,
        'feature_info':        feature_info,
        'too_large_to_display': len(sorted_data) > MAX_FEATURES_TO_DISPLAY,
        'feature_count':       len(sorted_data),
        'csv_export':          csv_export,
    }


# ---------------------------------------------------------------------------
# CSV export helpers
# ---------------------------------------------------------------------------

def generate_csv_export(all_data, package_name, data_type):
    """Build a base64-encoded CSV download payload for *data_type*.

    The cleaning pipeline (_clean_dataframe) is applied here too so that the
    CSV export is consistent with what the heatmap displays — spurious entries
    and www-duplicates are absent from both.

    Returns a dict with keys: content, filename, summary.
    Returns None if there is no data to export.
    """
    if not all_data:
        return None

    MAX_STRING_LENGTH = 100

    try:
        df = pd.DataFrame(all_data)

        if data_type not in df.columns:
            return None

        df_work = df[['version', 'vtscandate', data_type]].copy()
        df_work.rename(columns={data_type: 'Data'}, inplace=True)

        # Apply the same cleaning pipeline used in plot_data
        df_work = _clean_dataframe(df_work, data_type, MAX_STRING_LENGTH)
        df_work.rename(columns={'Data': 'value'}, inplace=True)

        df_work['count'] = 1
        df_work = df_work.groupby(['version', 'vtscandate', 'value'], as_index=False).sum()
        df_work['vtscandate'] = pd.to_datetime(df_work['vtscandate']).dt.strftime('%Y-%m-%d')
        df_work['version']    = df_work['version'].astype(str)

        df_work['package_name']     = package_name
        df_work['data_type']        = data_type
        df_work['alienvault_link']  = df_work['value'].apply(
            lambda v: f"https://otx.alienvault.com/indicator/domain/{v}"
        )
        df_work['whois_link']       = df_work['value'].apply(
            lambda v: f"https://www.whois.com/whois/{v}"
        )
        df_work['highlight_match']  = ''

        columns = [
            'package_name', 'data_type', 'value',
            'version', 'vtscandate', 'count',
            'highlight_match', 'alienvault_link', 'whois_link',
        ]
        df_export = df_work[columns].sort_values(['version', 'data_type', 'value'])

        csv_buffer = io.StringIO()
        df_export.to_csv(csv_buffer, index=False, quoting=csv.QUOTE_ALL)
        encoded = base64.b64encode(
            csv_buffer.getvalue().encode('utf-8')
        ).decode('utf-8')

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return {
            'content':  f"data:text/csv;base64,{encoded}",
            'filename': f"{package_name}_{data_type}_{timestamp}.csv",
            'summary':  (
                f"{len(df_export)} rows · "
                f"{df_export['version'].nunique()} versions"
            ),
        }

    except Exception as e:
        logger.error(f"CSV export failed for {package_name}/{data_type}: {e}")
        return None


def generate_csv_export_with_highlights(all_data, package_name, data_type, highlight_config):
    """Variant of generate_csv_export that populates the highlight_match column.

    highlight_config: dict {regex_pattern: colour_string}
    """
    result = generate_csv_export(all_data, package_name, data_type)
    if result is None or not highlight_config:
        return result

    try:
        raw_bytes = base64.b64decode(result['content'].split(',')[1])
        df = pd.read_csv(io.BytesIO(raw_bytes))

        def find_match(value):
            for pattern, colour in highlight_config.items():
                if re.search(pattern, str(value), re.IGNORECASE):
                    return f"{pattern} ({colour})"
            return ''

        df['highlight_match'] = df['value'].apply(find_match)

        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False, quoting=csv.QUOTE_ALL)
        encoded = base64.b64encode(
            csv_buffer.getvalue().encode('utf-8')
        ).decode('utf-8')
        result['content'] = f"data:text/csv;base64,{encoded}"
        return result

    except Exception as e:
        logger.error(f"CSV highlight annotation failed: {e}")
        return result


# ---------------------------------------------------------------------------
# Figure download helper
# ---------------------------------------------------------------------------

def generate_download_link(fig, package_name, data_type):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename  = f"{package_name}_{data_type}_{timestamp}.html"
    plot_html = pio.to_html(fig, full_html=False)
    encoded   = base64.b64encode(plot_html.encode()).decode()

    return html.Div([
        html.A(
            'Download Figure',
            id=f'download-link-{data_type}',
            download=filename,
            href=f"data:text/html;base64,{encoded}",
            target="_blank",
            className="btn btn-primary mt-2",
        )
    ])
