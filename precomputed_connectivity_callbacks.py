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
# callbacks/precomputed_connectivity_callbacks.py
from dash import dcc, html, callback_context
import dash
from dash.dependencies import Input, Output, State, ALL, MATCH
from app import app
import json
import re
import os
import plotly.graph_objects as go
from dash.exceptions import PreventUpdate
import logging
from layouts.precomputed_connectivity_layout import preset_configs
import base64
from datetime import datetime
import plotly.io as pio

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
PRECOMPUTED_DATA_DIR = 'precomputed_data'

# Domain metadata cache
_domain_metadata = None
def get_domain_metadata():
    """Load domain metadata from JSON file"""
    global _domain_metadata
    if _domain_metadata is None:
        try:
            metadata_path = os.path.join('utils', 'domain_metadata.json')
            if os.path.exists(metadata_path):
                with open(metadata_path, 'r') as f:
                    _domain_metadata = json.load(f)
                    logger.info(f"Loaded domain metadata with {len(_domain_metadata['patterns'])} patterns")
            else:
                logger.warning(f"Domain metadata file not found: {metadata_path}")
                _domain_metadata = {"patterns": []}
        except Exception as e:
            logger.error(f"Error loading domain metadata: {e}")
            _domain_metadata = {"patterns": []}
    return _domain_metadata

def match_domain_metadata(domain):
    """Match domain against metadata patterns"""
    metadata = get_domain_metadata()
    for pattern_data in metadata["patterns"]:
        if re.search(pattern_data["pattern"], domain, re.IGNORECASE):
            return pattern_data
    return None

def is_valid_color(color):
    # Check for valid hex colour
    if re.match(r'^#(?:[0-9a-fA-F]{3}){1,2}$', color):
        return True
    # Check for valid colour name
    valid_color_names = ['red', 'blue', 'green', 'yellow', 'purple', 'orange', 'black', 'white']
    return color.lower() in valid_color_names

def get_precomputed_packages():
    """Get packages that have been pre-computed"""
    try:
        metadata_path = os.path.join(PRECOMPUTED_DATA_DIR, 'metadata.json')
        if os.path.exists(metadata_path):
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
                packages = metadata['processed_packages']
                # Sort alphabetically
                return sorted(packages)
        return []
    except Exception as e:
        logger.error(f"Error loading precomputed packages: {e}")
        return []
@app.callback(
    Output('precomputed-package-dropdown', 'options'),
    Input('url', 'pathname')
)
def populate_precomputed_package_dropdown(pathname):
    """Populate the dropdown with available packages"""
    if pathname != '/precomputed-connectivity':
        return []
    
    try:
        # Use absolute path for metadata
        metadata_path = '/var/www/janus/precomputed_data/metadata.json'
        
        if os.path.exists(metadata_path):
            logger.info(f"Found metadata at: {metadata_path}")
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
                packages = metadata.get('processed_packages', [])
                
                if packages:
                    logger.info(f"Loaded {len(packages)} packages from precomputed metadata")
                    return [{'label': pkg, 'value': pkg} for pkg in sorted(packages)]
                else:
                    logger.warning("No processed_packages in metadata.json")
        else:
            logger.warning(f"Metadata file not found at: {metadata_path}")
        
        # FALLBACK: Load from filtered_package_ids JSON
        json_path = '/var/www/janus/filtered_package_ids_with_counts10_ver.json'
        
        if os.path.exists(json_path):
            logger.info(f"Loading from fallback: {json_path}")
            with open(json_path, 'r') as f:
                data = json.load(f)
                
                if isinstance(data, list) and data and isinstance(data[0], dict) and 'name' in data[0]:
                    packages = [pkg['name'] for pkg in data]
                elif isinstance(data, list):
                    packages = data
                elif isinstance(data, dict):
                    packages = list(data.keys())
                else:
                    packages = []
                
                logger.info(f"Loaded {len(packages)} packages from filtered JSON")
                return [{'label': pkg, 'value': pkg} for pkg in sorted(packages)]
        
        logger.error("No package data found in either location")
        return []
        
    except Exception as e:
        logger.error(f"Error loading package dropdown options: {e}", exc_info=True)
        return []
        
    except Exception as e:
        logger.error(f"Error loading package dropdown options: {e}")
        return []

@app.callback(
    Output("precomputed-stats-display", "children"),
    Input("url", "pathname")
)
def update_precomputed_stats(pathname):
    """Display stats about precomputed data"""
    if pathname != '/precomputed-connectivity':
        return []
    
    stats = get_precomputed_stats()
    if not stats:
        # Try to count from filtered_package_ids_with_counts10_ver.json
        try:
            json_path = 'filtered_package_ids_with_counts10_ver.json'
            if os.path.exists(json_path):
                with open(json_path, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        count = len(data)
                    elif isinstance(data, dict):
                        count = len(data.keys())
                    else:
                        count = 0
                    
                    return html.Div([
                        html.P(f"Total Packages Available: {count}"),
                        html.P("10 versions per package", className="text-muted small")
                    ])
        except:
            pass
        
        return html.P("No statistics available")
    
    return html.Div([
        html.P(f"Total Packages: {stats.get('total_packages', 'N/A')}"),
        html.P(f"Total APKs: {stats.get('total_apks', 'N/A')}"),
        html.P(f"Last Updated: {stats.get('last_updated', 'N/A')}")
    ])

def get_precomputed_stats():
    """Get stats about precomputed data"""
    try:
        metadata_path = os.path.join(PRECOMPUTED_DATA_DIR, 'metadata.json')
        if os.path.exists(metadata_path):
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
                return metadata.get('stats', {})
        return {}
    except Exception as e:
        logger.error(f"Error loading precomputed stats: {e}")
        return {}

def load_package_data(package_name):
    """Load precomputed data for a specific package"""
    try:
        data_path = os.path.join(PRECOMPUTED_DATA_DIR, 'packages', package_name, 'data.json')
        if os.path.exists(data_path):
            with open(data_path, 'r') as f:
                return json.load(f)
        else:
            logger.warning(f"No precomputed data found for package: {package_name}")
            return None
    except Exception as e:
        logger.error(f"Error loading data for package {package_name}: {e}")
        return None

def truncate_string(s, max_length=100):
    """Shorten string to max length"""
    return s if len(s) <= max_length else s[:max_length] + "..."

def generate_download_link(fig, package_name, data_type):
    """Create download link for the figure"""
    # Unique filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{package_name}_{data_type}_{timestamp}.html"
    
    # Convert to HTML
    plot_html = pio.to_html(fig, full_html=False)
    
    # Encode HTML
    encoded = base64.b64encode(plot_html.encode()).decode()
    
    # Create download link
    href = f"data:text/html;base64,{encoded}"
    
    return html.Div(children=[
        html.A(
            children='Download Figure',
            id=f'precomputed-download-link-{data_type}',
            download=filename,
            href=href,
            target="_blank",
            className="btn btn-primary mt-2"
        )
    ])

@app.callback(
    Output("precomputed-domains-filter", "style"),
    Input("precomputed-submit-button", "n_clicks"),
    State("precomputed-package-dropdown", "value"),
    prevent_initial_call=True
)
def toggle_domains_filter(n_clicks, package_name):
    """Show/hide domains filter after visualisation is generated"""
    if n_clicks and package_name:
        return {"display": "block"}
    return {"display": "none"}

def create_figure_from_precomputed_data(package_data, data_type, highlight_config, show_only_metadata=False):
    """Create visualisation from precomputed data"""
    # Extract data from package
    apks = package_data['apks']
    
    # Convert highlight config for plotting
    highlight_colors = {}
    for item in highlight_config:
        highlight_colors[item['regex']] = item['color']
    
    # Prepare plotting data
    # Create matrix of features x versions
    all_features = package_data['features'][data_type]
    
    # Track features with metadata
    features_with_metadata = set()
    
    # Find features with metadata
    if data_type == 'domains':
        for feature in all_features:
            metadata = match_domain_metadata(feature)
            if metadata:
                features_with_metadata.add(feature)
                
    # Filter features if requested (domains only)
    if data_type == 'domains' and show_only_metadata and features_with_metadata:
        all_features = [f for f in all_features if f in features_with_metadata]
        
    # Return error if no features after filtering
    if data_type == 'domains' and show_only_metadata and not all_features:
        return {
            'figure': None,
            'feature_info': [],
            'too_large_to_display': False,
            'feature_count': 0,
            'error': "No domains with metadata found for this package."
        }
    
    # Sort versions by scan date
    sorted_apks = sorted(apks, key=lambda x: x['vtscandate'])
    
    # Extract versions and dates
    versions = [apk['vercode'] for apk in sorted_apks]
    dates = [apk['vtscandate'] for apk in sorted_apks]
    
    # Apply staircase effect sorting logic (same as real-time analysis)
    # 1: Count appearances of each feature across all versions
    feature_appearances = {}
    for apk in sorted_apks:
        for feature in apk['features'][data_type]:
            feature_appearances[feature] = feature_appearances.get(feature, 0) + 1
    
    # 2: Sort features within each version based on appearances  
    version_sorted_features = {}
    for apk in sorted_apks:
        version_features = apk['features'][data_type]
        # Sort features by total appearances (descending), then alphabetically
        sorted_features = sorted(version_features, key=lambda x: (-feature_appearances[x], x))
        version_sorted_features[apk['vercode']] = sorted_features
    
    # 3: Build master list maintaining staircase effect
    master_feature_list = []
    seen_features = set()
    
    for apk in sorted_apks:
        version_features = version_sorted_features[apk['vercode']]
        # Only add new features not already in master list
        new_features = [f for f in version_features if f not in seen_features]
        master_feature_list.extend(new_features)
        seen_features.update(new_features)
    
    # Use staircase-sorted features instead of raw order
    all_features = master_feature_list
    
    # Create x-axis labels
    x_labels = [f"{ver} ({date.split(' ')[0]})" for ver, date in zip(versions, dates)]
    
    # Create feature count matrix
    feature_matrix = []
    max_count = 1  # Track max count for scaling
    
    for feature in all_features:
        row = []
        for apk in sorted_apks:
            # Count how many times it appears in precomputed data
            features_list = apk['features'][data_type]
            count = features_list.count(feature)
            max_count = max(max_count, count)
            row.append(count)
        feature_matrix.append(row)
    
    # Create hover text
    hover_text = []
    
    for i, feature in enumerate(all_features):
        hover_row = []
        for j, apk in enumerate(sorted_apks):
            count = feature_matrix[i][j]
            hover_text_data = f"Feature: {truncate_string(feature)}<br>Version: {apk['vercode']}<br>Count: {count}<br>Date: {apk['vtscandate'].split(' ')[0]}"
            
            # Add domain metadata for domains
            if data_type == 'domains':
                metadata = match_domain_metadata(feature)
                if metadata:
                    hover_text_data += f"<br><br><b>Organisation:</b> {metadata['organization']}<br>"
                    hover_text_data += f"<b>Country:</b> {metadata['country']}<br>"
                    hover_text_data += f"<b>Category:</b> {metadata['category']}<br>"
                    hover_text_data += f"<b>Description:</b> {metadata['description']}"
            
            hover_row.append(hover_text_data)
        hover_text.append(hover_row)
    
    # Create heatmap
    fig = go.Figure(data=go.Heatmap(
        showscale=False,
        z=feature_matrix,
        x=versions,
        y=all_features,
        text=hover_text,
        hoverinfo='text',
        colorscale=[[0, 'white'], [0.01, 'grey'], [0.4, '#505050'], [1, 'black']],
        zmin=0,
        zmax=max_count,
        xgap=1,
        ygap=1
    ))
    
    # Add highlighting based on regex patterns
    shapes = []
    for feature_idx, feature in enumerate(all_features):
        for ver_idx, _ in enumerate(versions):
            if feature_matrix[feature_idx][ver_idx] > 0:  # If feature is present
                # Highlight based on config
                for pattern, color in highlight_colors.items():
                    if re.search(pattern, feature, re.IGNORECASE):
                        shapes.append({
                            'type': 'rect',
                            'x0': ver_idx - 0.5,
                            'y0': feature_idx - 0.5,
                            'x1': ver_idx + 0.5,
                            'y1': feature_idx + 0.5,
                            'fillcolor': color,
                            'opacity': 0.3,
                            'line': {'width': 0},
                        })
                        break  # Stop after first match
                        
    # For domains: add special border for features with metadata
    if data_type == 'domains':
        for feature_idx, feature in enumerate(all_features):
            if feature in features_with_metadata:
                # Special border for feature name (y-axis)
                shapes.append({
                    'type': 'rect',
                    'x0': -0.5,  # Before first version
                    'y0': feature_idx - 0.5,
                    'x1': -0.1,  # Close to y-axis
                    'y1': feature_idx + 0.5,
                    'fillcolor': '#4CAF50',  # Green indicator
                    'opacity': 0.8,
                    'line': {'width': 0},
                })
    
    # Update layout
    title_text = f"{data_type.capitalize()} Presence and Frequency Across Versions for {package_data['metadata']['package_name']}"
    if data_type == 'domains' and show_only_metadata:
        title_text += " (Filtered: Only domains with metadata)"
        
    fig.update_layout(
        title=title_text,
        xaxis=dict(tickmode='array', tickvals=versions, ticktext=x_labels),
        yaxis=dict(autorange="reversed"),  # Reverse y-axis
        shapes=shapes
    )
    
    # Add legend if domains with metadata exist
    if data_type == 'domains' and features_with_metadata:
        fig.add_annotation(
            xref="paper", yref="paper",
            x=0.01, y=0.99,
            text="ðŸŸ© Domains with metadata",
            showarrow=False,
            font=dict(color="#333333"),
            bgcolor="#FFFFFF",
            bordercolor="#4CAF50",
            borderwidth=2,
            borderpad=4,
            opacity=0.8
        )
    
    # Create feature info for dropdown
    feature_info = []
    for feature in all_features:
        # Basic info for link generation
        info = {
            'feature': truncate_string(feature),
            'alienvault_link': f"https://otx.alienvault.com/indicator/domain/{feature}",
            'whois_link': f"https://www.whois.com/whois/{feature}"
        }
        
        # Add domain metadata if available
        if data_type == 'domains':
            metadata = match_domain_metadata(feature)
            if metadata:
                info['metadata'] = metadata
        
        feature_info.append(info)
    
    # Create chart data
    chart_data = {
        'features': all_features,
        'versions': versions,
        'dates': dates,
        'feature_matrix': feature_matrix,
        'package_name': package_data['metadata']['package_name'],
        'data_type': data_type,
        'sorted_apks': [{'vercode': apk['vercode'], 'vtscandate': apk['vtscandate']} for apk in sorted_apks]
    }
    
    return {
        'figure': fig,
        'feature_info': feature_info,
        'too_large_to_display': len(all_features) > 250,
        'feature_count': len(all_features),
        'chart_data': chart_data
    }

@app.callback(
    [Output("precomputed-highlight-list", "children"),
     Output("precomputed-highlight-config-store", "data"),
     Output("precomputed-highlight-dropdown", "value")],
    [Input("precomputed-highlight-dropdown", "value"),
     Input("precomputed-add-highlight", "n_clicks"),
     Input({"type": "precomputed-remove-highlight", "index": ALL}, "n_clicks")],
    [State("precomputed-highlight-pattern", "value"),
     State("precomputed-highlight-color", "value"),
     State("precomputed-highlight-config-store", "data")],
    prevent_initial_call=True
)
def update_highlight_config(selected_presets, add_clicks, remove_clicks, custom_pattern, custom_color, stored_config):
    """Update highlight config based on user selections"""
    ctx = dash.callback_context
    triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]

    if stored_config is None:
        stored_config = []

    if triggered_id == "precomputed-highlight-dropdown":
        # Add newly selected presets
        for preset in selected_presets or []:
            if not any(h['name'] == preset for h in stored_config):
                stored_config.append({
                    "name": preset,
                    "regex": preset_configs[preset]["regex"],
                    "color": preset_configs[preset]["color"]
                })

    elif triggered_id == "precomputed-add-highlight":
        if custom_pattern and custom_color and is_valid_color(custom_color):
            stored_config.append({
                "name": f"Custom: {custom_pattern}",
                "regex": custom_pattern,
                "color": custom_color
            })

    elif "precomputed-remove-highlight" in triggered_id:
        remove_index = json.loads(triggered_id)['index']
        if 0 <= remove_index < len(stored_config):
            removed_item = stored_config.pop(remove_index)
            if not removed_item['name'].startswith("Custom:"):
                selected_presets = [preset for preset in (selected_presets or []) if preset != removed_item['name']]

    highlight_list = create_highlight_list(stored_config)
    return highlight_list, stored_config, selected_presets

def create_highlight_list(highlight_config):
    """Create a list of highlight items for display"""
    return [
        html.Div([
            html.Span(f"{item['name']}: ", style={"fontWeight": "bold"}),
            html.Span(f"{item['regex'][:30]}..." if len(item['regex']) > 30 else item['regex']),
            html.Span(f" ({item['color']})", style={"color": item['color']}),
            html.Button(children="Ã—", id={"type": "precomputed-remove-highlight", "index": i}, n_clicks=0, style={"marginLeft": "10px"}),
        ], style={"marginBottom": "5px"})
        for i, item in enumerate(highlight_config)
    ]

@app.callback(
    [Output("precomputed-results", "children"),
     Output("precomputed-error-message", "children"),
     Output("precomputed-error-message", "style"),
     Output("precomputed-error-message", "is_open"),
     Output("precomputed-submit-button", "disabled"),
     Output("precomputed-loading-output", "children"),
     Output("precomputed-status-message", "children"),
     Output("precomputed-status-message", "color"),
     Output("precomputed-spinner-wrapper", "style")],
    [Input("precomputed-submit-button", "n_clicks"),
     Input("precomputed-show-only-metadata-domains", "value")],
    [State("precomputed-package-dropdown", "value"),
     State("precomputed-highlight-config-store", "data")]
)
def generate_visualizations(n_clicks, show_only_metadata, package_name, highlight_config):
    """Generate visualizations based on precomputed data"""
    ctx = callback_context
    triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    # If triggered by checkbox without previous n_clicks, prevent update
    if triggered_id == "precomputed-show-only-metadata-domains" and n_clicks is None:
        raise PreventUpdate

    # If no clicks or no package selected, prevent update
    if n_clicks is None or not package_name:
        raise PreventUpdate
    
    try:
        # Show spinner
        spinner_style = {"display": "block"}
        status_message = "Loading precomputed data..."
        status_color = "primary"
        
        # Load package data
        package_data = load_package_data(package_name)
        
        if not package_data:
            return (
                [], 
                f"No precomputed data found for package: {package_name}", 
                {"display": "block"}, 
                True, 
                False, 
                None, 
                "Error: Data not found", 
                "danger",
                {"display": "none"}
            )
        
        # Create visualizations for each data type
        data_types = ['urls', 'domains', 'subdomains']
        output_results = []
        
        for data_type in data_types:
            # Apply filtering only for domains
            current_show_only_metadata = False
            if data_type == 'domains':
                current_show_only_metadata = show_only_metadata
                
            # Create figure
            result = create_figure_from_precomputed_data(
                package_data, 
                data_type, 
                highlight_config or [],
                show_only_metadata=current_show_only_metadata
            )
            
            # Check for errors
            if 'error' in result:
                output_results.extend([
                    html.H4(f"{data_type.capitalize()} Analysis"),
                    html.P(result['error'], className="alert alert-warning"),
                    html.Hr()
                ])
                continue
                
            if result['too_large_to_display']:
                # For large datasets, provide basic chart data for LLM prompts
                basic_chart_data = {
                    'features': [info['feature'] for info in result['feature_info']],
                    'package_name': package_name,
                    'data_type': data_type,
                    'feature_count': result['feature_count'],
                    'versions': [],  # Empty for large datasets
                    'dates': [],
                    'feature_matrix': [],
                    'sorted_apks': []
                }
                
                output_results.extend([
                    html.H4(f"{data_type.capitalize()} Analysis"),
                    html.P(f"The {data_type} dataset is too large to display ({result['feature_count']} features). Please download the figure to view."),
                    html.Div([
                        generate_download_link(result['figure'], package_name, data_type),
                    ], style={"marginTop": "10px"}),
                    html.Hr()
                ])
            else:
                dropdown_options = [{'label': info['feature'], 'value': i} for i, info in enumerate(result['feature_info'])]
                
                output_results.extend([
                    html.H4(f"{data_type.capitalize()} Analysis"),
                    dcc.Graph(figure=result['figure'], style={'height': '800px'}),
                    html.Div([
                        generate_download_link(result['figure'], package_name, data_type),
                    ], style={"marginTop": "10px"}),
                    dcc.Store(id=f'precomputed-feature-info-store-{data_type}', data=result['feature_info']),
                    html.H5("Feature Information"),
                    dcc.Dropdown(
                        id=f'precomputed-feature-dropdown-{data_type}',
                        options=dropdown_options,
                        value=0 if dropdown_options else None,
                        placeholder="Select a feature",
                        style={'marginBottom': '10px'}
                    ),
                    html.Div(id=f'precomputed-feature-info-{data_type}'),
                    html.Hr()
                ])

        if not output_results:
            output_results.append(html.P("No data found for the selected package."))
        
        # Update status
        status_message = "Analysis complete!"
        status_color = "success"
        spinner_style = {"display": "none"}
        
        return (
            output_results, 
            "", 
            {"display": "none"}, 
            False, 
            False, 
            None, 
            status_message, 
            status_color,
            spinner_style
        )
    
    except Exception as e:
        error_message = f"An error occurred: {str(e)}"
        logger.error(error_message)
        
        return (
            [], 
            error_message, 
            {"display": "block"}, 
            True, 
            False, 
            None, 
            "Error during analysis", 
            "danger",
            {"display": "none"}
        )

# Add callbacks for feature information
for data_type in ['urls', 'domains', 'subdomains']:
    @app.callback(
        Output(f'precomputed-feature-info-{data_type}', 'children'),
        [Input(f'precomputed-feature-dropdown-{data_type}', 'value')],
        [State(f'precomputed-feature-info-store-{data_type}', 'data')]
    )
    def update_feature_info(selected_index, feature_info, data_type=data_type):
        if selected_index is None or not feature_info:
            return html.Div(["No feature selected"])
        
        info = feature_info[selected_index]
        feature = info['feature']
        
        # Add metadata display for domains
        metadata_info = []
        if data_type == 'domains' and 'metadata' in info:
            metadata = info['metadata']
            metadata_info = [
                html.Div(children=[
                    html.H6(children="Domain Information", className="mt-3"),
                    html.Table(children=[
                        html.Tr(children=[
                            html.Td(children="Organization:", className="font-weight-bold pe-3"),
                            html.Td(children=metadata['organization'])
                        ]),
                        html.Tr(children=[
                            html.Td(children="Country:", className="font-weight-bold pe-3"),
                            html.Td(children=metadata['country'])
                        ]),
                        html.Tr(children=[
                            html.Td(children="Category:", className="font-weight-bold pe-3"),
                            html.Td(children=metadata['category'])
                        ]),
                        html.Tr(children=[
                            html.Td(children="Description:", className="font-weight-bold pe-3"),
                            html.Td(children=metadata['description'])
                        ])
                    ], className="table table-sm")
                ], className="mb-3 p-3 border rounded bg-light")
            ]
        
        # Build the components to return
        components = [
            html.P(f"Feature: {feature}"),
            html.Div([
                html.A("AlienVault", href=info['alienvault_link'], target="_blank", className="btn btn-sm btn-outline-primary me-2 mb-1"),
                html.A("WHOIS", href=info['whois_link'], target="_blank", className="btn btn-sm btn-outline-primary me-2 mb-1"),
                html.A("VirusTotal", href=f"https://www.virustotal.com/gui/domain/{feature}", target="_blank", className="btn btn-sm btn-outline-primary me-2 mb-1"),
                html.A("Shodan", href=f"https://www.shodan.io/search?query={feature}", target="_blank", className="btn btn-sm btn-outline-primary me-2 mb-1"),
                html.A("URLScan", href=f"https://urlscan.io/search/#{feature}", target="_blank", className="btn btn-sm btn-outline-primary me-2 mb-1"),
            ])
        ]
        
        # Add metadata components if available
        if metadata_info:
            components.extend(metadata_info)
            
        return html.Div(components)

@app.callback(
    [Output("precomputed-spinner-wrapper", "style", allow_duplicate=True),
     Output("precomputed-status-message", "children", allow_duplicate=True),
     Output("precomputed-status-message", "color", allow_duplicate=True),
     Output("precomputed-error-message", "style", allow_duplicate=True),
     Output("precomputed-error-message", "is_open", allow_duplicate=True)],
    [Input("precomputed-submit-button", "n_clicks")],
    prevent_initial_call=True
)
def show_spinner_on_click(n_clicks):
    """Show the spinner immediately when the submit button is clicked"""
    if n_clicks:
        return {"display": "block"}, "Generating visualizations...", "primary", {"display": "none"}, False
    return {"display": "none"}, "Waiting for input...", "secondary", {"display": "none"}, False

# Helper function
def both_nonzero(a, b):
    """Check if both values are non-zero"""
    return a > 0 and b > 0