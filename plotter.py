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
import shutil
from datetime import datetime
import csv
import requests
from collections import defaultdict
from androguard.misc import AnalyzeAPK
import pandas as pd
from androguard.core.bytecodes import apk, dvm
import tldextract
import re
import multiprocessing as mp
import plotly.graph_objects as go
import urllib.request
import gzip
import plotly.io as pio
import zipfile
import os
import uuid
from flask import session
import time
import glob
from pathlib import Path
import os
import urllib.request
import gzip
from tqdm import tqdm


filename = "latest_with-added-date.csv"

def download_file_with_progress(url, output_path):
    class DownloadProgressBar(tqdm):
        def update_to(self, b=1, bsize=1, tsize=None):
            if tsize is not None:
                self.total = tsize
            self.update(b * bsize - self.n)

    with DownloadProgressBar(unit='B', unit_scale=True, miniters=1, desc=url.split('/')[-1]) as t:
        urllib.request.urlretrieve(url, filename=output_path, reporthook=t.update_to)

def check_file_corruption(file_path):
    try:
        with open(file_path, 'rb') as f:
            # Try to read a chunk of the file to check for corruption
            f.read(1024)
        return False
    except:
        return True

# Update CSV file if it doesn't exist
if not os.path.isfile(filename) or check_file_corruption(filename):
    url = "https://androzoo.uni.lu/static/lists/latest_with-added-date.csv.gz"
    print("Downloading file...")
    try:
        download_file_with_progress(url, filename + ".gz")
        print("File downloaded.")

        # Extract the gzip file
        print("Extracting file...")
        with gzip.open(filename + ".gz", "rb") as f_in:
            with open(filename, "wb") as f_out:
                f_out.write(f_in.read())
        print("File extracted.")

        # Clean up the gzip file
        os.remove(filename + ".gz")

        if check_file_corruption(filename):
            print("File is corrupt after extraction. Please try downloading again.")
        else:
            print("File is successfully downloaded and extracted.")
    except Exception as e:
        print(f"An error occurred: {e}")
else:
    print("File already exists and is not corrupt.")



# Function to find SHA256, version code, and VT scan date
def find_sha256_vercode_vtscandate(package_name, csv_path, start_date, end_date):
    print("Searching for SHA256, version code, and VT scan date in the CSV file...")
    sha256_vercode_vtscandate_values = []
    start_date = datetime.strptime(start_date, '%Y-%m-%d %H:%M:%S.%f')
    end_date = datetime.strptime(end_date, '%Y-%m-%d %H:%M:%S.%f')

    with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for row in reader:
            if row[5] == package_name:
                vt_scan_date = datetime.strptime(row[10], '%Y-%m-%d %H:%M:%S.%f')
                if start_date <= vt_scan_date <= end_date:
                    sha256_vercode_vtscandate_values.append((row[0], row[6], row[10]))

    # Sort by vt_scan_date in ascending order
    sha256_vercode_vtscandate_values.sort(key=lambda x: datetime.strptime(x[2], '%Y-%m-%d %H:%M:%S.%f'))
    return sha256_vercode_vtscandate_values

# Function to calculate sampling frequency
def calculate_sampling_frequency(total_versions, desired_versions):
    print("Calculating sampling frequency...")
    return max(1, total_versions // desired_versions)

# Function to download APK
def download_apk(sha256, vercode, vtscandate, package_name, apikey, folder, max_retries=20, retry_cycles=3):
    print(f"Downloading APK with SHA256: {sha256}...")
    os.makedirs(folder, exist_ok=True)
    url = f"https://androzoo.uni.lu/api/download?apikey={apikey}&sha256={sha256}"

    for cycle in range(retry_cycles):  # Implement retry cycles
        attempts = 0
        while attempts < max_retries:
            response = requests.get(url, stream=True)
            if response.status_code == 200:
                filename = os.path.join(folder, f"{package_name}_{vercode}_{vtscandate}.apk")
                filename = filename.replace(':', '_')  # Quick fix for Windows file name compatibility

                with open(filename, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=1024):
                        if chunk:  # filter out keep-alive new chunks
                            f.write(chunk)

                # Check if the file size is more than 1000 bytes
                if os.path.getsize(filename) > 1000:
                    print(f"Successfully downloaded: {filename}")
                    return
                else:
                    print(f"Downloaded file is too small, retrying... (Attempt {attempts + 1} of {max_retries})")
            else:
                print(f"Failed to download APK with SHA256: {sha256}. HTTP status code: {response.status_code}")

            attempts += 1
            if attempts >= max_retries:
                print(f"Attempt {attempts} failed. Retrying after a 5-minute wait...")
                time.sleep(80)  # Wait for 5 minutes before the next cycle of retries
            else:
                print(f"Retrying... (Attempt {attempts + 1} of {max_retries})")

    print(f"Failed to download APK after {max_retries * retry_cycles} attempts.")

# Function to download multiple APKs
def download_apks(package_names, apikey, folder, csv_path, start_date, end_date, desired_versions):
    print("Starting to download APKs...")
    for package_name in package_names:
        sha256_vercode_vtscandate_list = find_sha256_vercode_vtscandate(package_name, csv_path, start_date, end_date)
        sampling_frequency = calculate_sampling_frequency(len(sha256_vercode_vtscandate_list), desired_versions)
        sha256_vercode_vtscandate_list = sha256_vercode_vtscandate_list[::sampling_frequency]
        for sha256, vercode, vtscandate in sha256_vercode_vtscandate_list:
            download_apk(sha256, vercode, vtscandate, package_name, apikey, folder)

'''# Function to analyze APK folder
def analyze_folder(folder_path):
    print("Analyzing folder for APK files...")
    cores = max(1, mp.cpu_count()-4)
    cores = 1
    print(f'Using {cores} to process apps')
    pool = mp.Pool(cores)

    # Generate file paths
    file_names = os.listdir(folder_path)
    print(file_names)
    # Process the files
    results = pool.starmap(process_file, [(file_name, folder_path) for file_name in file_names])

    # Update the version_subdomains and version_vtscandates dicts
    version_vtscandate_subdomains_counts = []
    for result in results:
        if result is not None:
            version_vtscandate_subdomains_counts.extend(result)

    return version_vtscandate_subdomains_counts'''

# Function to extract elements from APK file
def extract_elements(file_path):
    print(f"Extracting domains, subdomains, and URLs from file: {file_path}...")
    try:
        a = apk.APK(file_path)
        domains = []
        subdomains = []
        urls = []
        for dex in a.get_all_dex():
            dv = dvm.DalvikVMFormat(dex)
            for string in dv.get_strings():
                found_urls = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+\{\}]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', string)
                for url in found_urls:
                    urls.append(url)  # Collect each URL
                    parsed_url = tldextract.extract(url)
                    domain = '.'.join([part for part in [parsed_url.domain, parsed_url.suffix] if part])
                    subdomain = '.'.join([part for part in parsed_url if part])
                    domains.append(domain)
                    subdomains.append(subdomain)
        print(domains)
        print(subdomain)
        print(urls)
        return domains, subdomains, urls
    except Exception as e:
        print(f'Error while extracting domains, subdomains, and URLs from {file_path}: {str(e)}')
        return [], [], []

# Function to check valid entry (for beginner Janus)
def valid_entry(entry):
    invalid_chars = ['$', '[', ']', '#', '%s']
    if any(char in entry for char in invalid_chars):
        return False
    if '.' not in entry:
        return False
    return True

# Function to analyze elements in APK files
def analyze_elements(folder_path):
    print(f"Analyzing folder for APK files and extracting domains, subdomains, and URLs...")
    cores = 2
    #pool = mp.Pool(max(1, mp.cpu_count() - 1))  # Use one less than the total number of cores
    pool = mp.Pool(cores)

    file_names = os.listdir(folder_path)
    results = pool.starmap(process_file, [(file_name, folder_path) for file_name in file_names])

    version_vtscandate_domains_counts = []
    version_vtscandate_subdomains_counts = []
    version_vtscandate_url_counts = []

    for result in results:
        if result is not None:
            version = result["version"]
            vt_scan_date = result["vt_scan_date"]
            for domain, count in result["domains"]:
                version_vtscandate_domains_counts.append((version, vt_scan_date, domain, count))
            for subdomain, count in result["subdomains"]:
                version_vtscandate_subdomains_counts.append((version, vt_scan_date, subdomain, count))
            for url, count in result["urls"]:
                version_vtscandate_url_counts.append((version, vt_scan_date, url, count))

    return version_vtscandate_domains_counts, version_vtscandate_subdomains_counts, version_vtscandate_url_counts

# Function to process APK file
def process_file(file_name, folder_path):
    if file_name.endswith('.apk'):
        print(f"Processing file: {file_name}...")
        file_path = os.path.join(folder_path, file_name)
        a, _, _ = AnalyzeAPK(file_path)
        version = a.get_androidversion_code()
        vt_scan_date = file_name.split('_')[2].split('.')[0]
        domains, subdomains, urls = extract_elements(file_path)
        domain_counts = defaultdict(int)
        subdomain_counts = defaultdict(int)
        url_counts = defaultdict(int)
        for domain in domains:
            domain_counts[domain] += 1
        for subdomain in subdomains:
            subdomain_counts[subdomain] += 1
        for url in urls:
            url_counts[url] += 1
        return {
            "version": version,
            "vt_scan_date": vt_scan_date,
            "domains": [(domain, count) for domain, count in domain_counts.items()],
            "subdomains": [(subdomain, count) for subdomain, count in subdomain_counts.items()],
            "urls": [(url, count) for url, count in url_counts.items()]
        }
    else:
        return None


def plot_data(version_vtscandate_elements_counts, element_type, binary=False):
    print("Preparing data for plotting...")
    data = [{'Version': str(version), 'vt_scan_date': vt_scan_date, element_type.capitalize(): element, 'Count': count}
            for version, vt_scan_date, element, count in version_vtscandate_elements_counts]
    df = pd.DataFrame(data)
    if df.empty:
        print("No data to plot.")
        return None

    print("Plotting data...")
    df['Version'] = df['Version'].astype(str)
    df['vt_scan_date'] = pd.to_datetime(df['vt_scan_date'], errors='coerce').dt.strftime('%Y-%m-%d')
    #df['vt_scan_date'] = pd.to_datetime(df['vt_scan_date']).dt.strftime('%Y-%m-%d')

    df_count_pivot = df.pivot_table(index=element_type.capitalize(), columns='Version', values='Count', aggfunc='sum',
                                    fill_value=0)
    df_date_pivot = df.pivot_table(index=element_type.capitalize(), columns='Version', values='vt_scan_date',
                                   aggfunc='first')

    sorted_versions = sorted(df_count_pivot.columns,
                             key=lambda s: [int(u) if u.isdigit() else u for u in re.split('(\d+)', s)])
    df_count_pivot = df_count_pivot[sorted_versions]
    df_date_pivot = df_date_pivot[sorted_versions]

    sorted_versions_with_dates = []
    for version in sorted_versions:
        earliest_date = df[df['Version'] == version]['vt_scan_date'].min()
        label = f"{version} ({earliest_date})"
        sorted_versions_with_dates.append(label)

    sorted_versions = sorted(df['Version'].unique(),
                             key=lambda x: [int(part) if part.isdigit() else part for part in re.split('([0-9]+)', x)])

    element_appearances = {element: df[df[element_type.capitalize()] == element]['Version'].nunique() for element in
                           df[element_type.capitalize()].unique()}

    version_sorted_elements = {version: sorted(df[df['Version'] == version][element_type.capitalize()].unique(),
                                               key=lambda x: (-element_appearances.get(x, 0), x)) for version in
                               sorted_versions}

    master_element_list = []
    seen_elements = set()
    for version in sorted_versions:
        new_elements = [elem for elem in version_sorted_elements[version] if elem not in seen_elements]
        master_element_list.extend(new_elements)
        seen_elements.update(new_elements)

    df_count_pivot = df_count_pivot.reindex(master_element_list)
    df_date_pivot = df_date_pivot.reindex(master_element_list)

    if binary:
        colorscale = [[0, 'white'], [0.01, 'grey'], [1, 'grey']]
        zmax = 1
        title = f'{element_type.capitalize()} Presence Across Versions'
        legend = False
    else:
        colorscale = [[0, 'white'], [0.01, 'grey'], [0.2, 'grey'], [1, 'black']]
        zmax = df_count_pivot.values.max()
        title = f'{element_type.capitalize()} Frequency Across Versions'
        legend = True

    fig = go.Figure(data=go.Heatmap(
        z=df_count_pivot.values,
        x=sorted_versions,
        y=df_count_pivot.index,
        text=df_date_pivot.values,
        hoverinfo='z+x+y+text',
        colorscale=colorscale,
        zmin=0,
        zmax=zmax,
        xgap=1,
        ygap=1,
        showscale=legend
    ))

    version_labels = [
        f"{version}<br>{datetime.strptime(df[df['Version'] == version]['vt_scan_date'].iloc[0].split()[0], '%Y-%m-%d').strftime('%Y-%m-%d') if not df[df['Version'] == version].empty else 'N/A'}"
        for version in sorted_versions]

    fig.update_layout(
        title=title,
        xaxis=dict(tickmode='array', tickvals=sorted_versions, ticktext=version_labels),
        yaxis=dict(autorange="reversed")
    )

    plot_html = fig.to_html(full_html=False)
    return plot_html



def count_apps(package_name, csv_path, start_date, end_date):
    print("Counting apps in the CSV file between given dates...")
    count = 0
    start_date = datetime.strptime(start_date, '%Y-%m-%d %H:%M:%S.%f')
    end_date = datetime.strptime(end_date, '%Y-%m-%d %H:%M:%S.%f')

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for row in reader:
            if row[5] == package_name:
                vt_scan_date = datetime.strptime(row[10], '%Y-%m-%d %H:%M:%S.%f')
                if start_date <= vt_scan_date <= end_date:
                    count += 1

    return count





# Function to plot grouped bar data
def plot_data_grouped_bar(version_vtscandate_elements_counts, element_type):
    print("Preparing data for plotting...")
    data = [{'Version': str(version), 'vt_scan_date': vt_scan_date, element_type.capitalize(): element, 'Count': count}
            for version, vt_scan_date, element, count in version_vtscandate_elements_counts]
    df = pd.DataFrame(data)
    if df.empty:
        print("No data to plot.")
        return None

    print("Plotting data...")
    df['Version'] = df['Version'].astype(str)
    df_count_pivot = df.pivot_table(index=element_type.capitalize(), columns='Version', values='Count', aggfunc='sum',
                                    fill_value=0)
    df_date_pivot = df.pivot_table(index=element_type.capitalize(), columns='Version', values='vt_scan_date',
                                   aggfunc='first')

    df_count_pivot = df_count_pivot[sorted(df_count_pivot.columns, key=int)]
    df_date_pivot = df_date_pivot[sorted(df_date_pivot.columns, key=int)]

    df_count_pivot.index = df_count_pivot.index.map(lambda x: '.'.join(reversed(x.split('.'))))

    bars = []
    for version in df_count_pivot.columns:
        counts = df_count_pivot[version].values.tolist()
        bars.append(go.Bar(name=version, x=df_count_pivot.index.tolist(), y=counts))

    title = f'{element_type.capitalize()} Count Across Versions'

    fig = go.Figure(data=bars)
    fig.update_layout(barmode='group', title=title, xaxis_title=element_type, yaxis_title="Count")

    plot_html = pio.to_html(fig, full_html=False)
    return plot_html


def validate_and_clean_apks(package_list, base_dir, trash_dir):
    for package_name in package_list:
        # find directories that start with the package name
        package_dirs = [d for d in glob.glob(os.path.join(base_dir, f"{package_name}*")) if os.path.isdir(d)]

        if not package_dirs:
            print(f"No directory found for package: {package_name}")
            continue

        for package_dir in package_dirs:
            print(f"Checking directory: {package_dir}")
            valid_apks_found = False  # asume no valid APKs initially
            corrupted_apks_found = False

            for apk_file in os.listdir(package_dir):
                apk_path = os.path.join(package_dir, apk_file)
                if apk_path.endswith('.apk'):
                    try:
                        with zipfile.ZipFile(apk_path, 'r') as zip_ref:
                            zip_ref.namelist()
                            valid_apks_found = True  # valid APK found
                    except zipfile.BadZipFile:
                        print(f"Corrupted APK detected: {apk_path}")
                        corrupted_apks_found = True
                        break  # found a corrupted APK, no need to check further

            # if no valid APKs found or a corrupted APK is detected, move directory to trash
            if not valid_apks_found or corrupted_apks_found:
                # prepare trash directory path
                trash_package_path = os.path.join(trash_dir, Path(package_dir).name)
                final_trash_path = trash_package_path
                counter = 1
                while os.path.exists(final_trash_path):
                    final_trash_path = f"{trash_package_path}_{counter}"
                    counter += 1

                print(f"Moving directory to trash: {package_dir}")
                shutil.move(package_dir, final_trash_path)


# Main run function
def run(apikey, packages, start_date, end_date):


    base_dir = Path(__file__).parent.absolute()
    trash_dir = os.path.join(base_dir, "trash")
    validate_and_clean_apks(['folder_'], base_dir, trash_dir)

    try:

        desired_versions = 10
        start_date += " 00:00:00.000000"
        end_date += " 00:00:00.000000"

        session_id = str(uuid.uuid4())
        session['id'] = session_id

        csv_path = "latest_with-added-date.csv"
        folder_path = f"folder_{session_id}"

        #folder_path = "folder_1afd80ae-8a9c-4162-bebe-11912ba5f70a" #hardcode for testing

        # Download APKs ***
        download_apks(packages, apikey, folder_path, csv_path, start_date, end_date, desired_versions)

        version_vtscandate_domains, version_vtscandate_subdomains, version_vtscandate_urls = analyze_elements(folder_path)

        plot_html_subdomains_heatmap = plot_data(version_vtscandate_subdomains, 'subdomain')
        plot_html_domains_heatmap = plot_data(version_vtscandate_domains, 'domain')
        plot_html_urls_heatmap = plot_data(version_vtscandate_urls, 'url')

        if plot_html_subdomains_heatmap is None:
            plot_html_subdomains_heatmap = "<p>No data to plot for subdomains</p>"
        if plot_html_domains_heatmap is None:
            plot_html_domains_heatmap = "<p>No data to plot for domains</p>"
        if plot_html_urls_heatmap is None:
            plot_html_urls_heatmap = "<p>No data to plot for URLs</p>"

        plot_html_domains_gb = plot_data_grouped_bar(version_vtscandate_domains, 'domain')
        plot_html_subdomains_gb = plot_data_grouped_bar(version_vtscandate_subdomains, 'subdomain')

        with open(f"plot_subdomains_heatmap_{session_id}.html", "w", encoding='utf-8') as file:
            file.write(plot_html_subdomains_heatmap)

        with open(f"plot_urls_heatmap_{session_id}.html", "w", encoding='utf-8') as file:
            file.write(plot_html_urls_heatmap)

        with open(f"plot_domains_heatmap_{session_id}.html", "w", encoding='utf-8') as file:
            file.write(plot_html_domains_heatmap)

        with open(f"plot_domains_grouped_bar_{session_id}.html", "w", encoding='utf-8') as file:
            file.write(plot_html_domains_gb)

        with open(f"plot_subdomains_grouped_bar_{session_id}.html", "w", encoding='utf-8') as file:
            file.write(plot_html_subdomains_gb)

        zip_file_path = f"plots_{session_id}.zip"

        with zipfile.ZipFile(zip_file_path, 'w') as zipf:
            zipf.write(f"plot_subdomains_heatmap_{session_id}.html")
            zipf.write(f"plot_urls_heatmap_{session_id}.html")
            zipf.write(f"plot_domains_heatmap_{session_id}.html")
            zipf.write(f"plot_domains_grouped_bar_{session_id}.html")
            zipf.write(f"plot_subdomains_grouped_bar_{session_id}.html")


        return zip_file_path
    except Exception as e:
        print(f"Sorry, something went wrong, please try again.")
