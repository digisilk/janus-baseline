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
# callbacks/user_apk_analysis_callbacks.py
from dash import dcc, html, callback_context
from dash.dependencies import Input, Output, State, ALL, MATCH
from app import app

from logic.user_apk_analysis_logic import (
    process_uploaded_apks,
    generate_download_link,
    extract_apk_features,
    plot_data,
    save_uploaded_file_to_server
)
from dash.exceptions import PreventUpdate

from dash import dcc, html, callback_context
from dash.dependencies import Input, Output, State, ALL, MATCH
from dash.exceptions import PreventUpdate
import dash
from app import app
from logic.user_apk_analysis_logic import process_uploaded_apks, generate_download_link, extract_apk_features
import logging
import json
import re
from layouts.user_apk_analysis_layout import preset_configs
import dash_bootstrap_components as dbc
from androguard.core.bytecodes.apk import APK
import base64
import os
import uuid
from utils.ui_logger import UILogger
import datetime
import tldextract

# Concurrency controls
from utils.concurrency_manager import active_sessions, MAX_CONCURRENT_USERS, register_session, remove_session, has_capacity

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.callback(
    Output('user-apk-upload-output', 'children'),
    Input('user-apk-upload', 'contents'),
    State('user-apk-upload', 'filename')
)
def update_output(list_of_contents, list_of_names):
    if list_of_contents is not None:
        children = [
            html.Div([
                html.H5(f'Uploaded file: {name}')
            ]) for name in list_of_names
        ]
        return children
    return []

@app.callback(
    [Output("user-apk-results", "children"),
     Output("user-apk-error-message", "children"),
     Output("user-apk-error-message", "style"),
     Output("user-apk-error-message", "is_open"),
     Output("user-apk-submit-button", "disabled"),
     Output("user-apk-loading-output", "children"),
     Output('user-apk-feature-info-store', 'data'),
     Output('user-apk-session-id-store', 'data'),
     Output("user-apk-status-message", "children"),
     Output("user-apk-status-message", "color"),
     Output("user-apk-spinner-wrapper", "style")],
    [Input("user-apk-submit-button", "n_clicks")],
    [State("user-apk-upload-store", "data"),
     State("user-apk-highlight-config-store", "data"),
     State("user-apk-num-cores-slider", "value"),
     State("user-apk-parser-selection", "value"),
     State("user-apk-sort-order", "value")]
)
def process_apks_callback(n_clicks, stored_data, highlight_config, num_cores, parser_selection, sort_order):
    if n_clicks is None or not stored_data:
        raise PreventUpdate
    
    # Unique session ID for this request
    session_id = str(uuid.uuid4())
    
    try:
        # Session logger
        logger_data = UILogger.get_logger(session_id)
        logger = logger_data['logger']
        logger.info("Starting new APK processing")
        
        # Check server capacity
        if not has_capacity():
            logger.warning("Server is busy. Please try again later.")
            status_message = "Server is busy. Please try again later."
            status_color = "warning"
            spinner_style = {"display": "none"}
            return [], "", {"display": "none"}, False, False, None, {}, session_id, status_message, status_color, spinner_style
        
        # Register this session
        register_session(session_id, {
            'num_apks': len(stored_data)
        })
        logger.info(f"Registered session {session_id}. Current active sessions: {len(active_sessions)}")
        
        # Show processing status
        status_message = f"Processing {len(stored_data)} APK files... This may take a few minutes."
        status_color = "primary"
        spinner_style = {"display": "block"}
        
        logger.info(f"Processing {len(stored_data)} uploaded APK files")
        
        # Process the uploaded APKs
        results = process_uploaded_apks(
            stored_data, 
            highlight_config, 
            num_cores, 
            parser_selection, 
            sort_order,
            session_id
        )
        
        if results is None:
            logger.warning("Processing was cancelled or no data to display")
            status_message = "Processing was cancelled or no data to display. Please check your inputs and try again."
            status_color = "warning"
            spinner_style = {"display": "none"}
            # Clean up session
            remove_session(session_id)
            logger.info(f"Removed session {session_id}. Current active sessions: {len(active_sessions)}")
            return [], "", {"display": "none"}, False, False, None, {}, session_id, status_message, status_color, spinner_style
        
        output_results = []
        feature_info_store = {}  # Store feature info for dropdowns

        for data_type, result in results.items():
            if result is None:
                output_results.append(html.P(f"No {data_type} found in the uploaded APK(s)."))
            elif result.get('too_large_to_display', False):
                output_results.extend([
                    html.H4(f"{data_type.capitalize()} Analysis"),
                    html.P(f"The {data_type} dataset is too large to display ({result['feature_count']} features). Please download the figure to view."),
                    generate_download_link(result['figure'], "user_uploaded_apks", data_type),
                    html.Hr()
                ])
            else:
                dropdown_options = [{'label': info['feature'], 'value': i} for i, info in enumerate(result['feature_info'])]
                
                output_results.extend([
                    html.H4(f"{data_type.capitalize()} Analysis"),
                    dcc.Graph(figure=result['figure'], style={'height': '800px'}),
                    html.Div([
                        generate_download_link(result['figure'], "user_uploaded_apks", data_type),
                    ], style={"display": "flex", "alignItems": "center", "marginTop": "10px"}),
                    html.H5("Feature Information"),
                    dcc.Dropdown(
                        id={'type': 'user-apk-feature-dropdown', 'index': data_type},
                        options=dropdown_options,
                        value=0 if dropdown_options else None,
                        placeholder="Select a feature",
                        style={'marginBottom': '10px'}
                    ),
                    html.Div(id={'type': 'user-apk-feature-info', 'index': data_type}),
                    html.Hr()
                ])
                
                # Store feature info for this data type
                feature_info_store[data_type] = result['feature_info']

        if not output_results:
            output_results.append(html.P("No data found in the uploaded APK(s)."))

        logger.info("APK processing complete")
        
        # Update status to complete
        status_message = "Analysis complete!"
        status_color = "success"
        spinner_style = {"display": "none"}
        
        # Clean up session
        remove_session(session_id)
        logger.info(f"Removed session {session_id}. Current active sessions: {len(active_sessions)}")
        
        return output_results, "", {"display": "none"}, False, False, None, feature_info_store, session_id, status_message, status_color, spinner_style
    except Exception as e:
        error_message = f"An error occurred: {str(e)}"
        logger.error(error_message)
        
        # Clean up session on error
        remove_session(session_id)
        logger.info(f"Removed session {session_id} due to error. Current active sessions: {len(active_sessions)}")
        
        # Update status to error
        status_message = "Error during analysis. See details below."
        status_color = "danger"
        spinner_style = {"display": "none"}
        
        return [], error_message, {"display": "block"}, True, False, None, {}, session_id, status_message, status_color, spinner_style

@app.callback(
    Output('user-apk-progress', 'children'),
    [Input('user-apk-progress-interval', 'n_intervals')],
    [State('user-apk-session-id-store', 'data')]
)
def update_progress(n, session_id):
    if session_id:
        return UILogger.get_logs(session_id)
    else:
        # Show placeholder when no session is active
        return html.Div("No active session. Upload and analyse APKs to see progress.")

@app.callback(
    Output({'type': 'user-apk-feature-info', 'index': MATCH}, 'children'),
    Input({'type': 'user-apk-feature-dropdown', 'index': MATCH}, 'value'),
    State('user-apk-feature-info-store', 'data'),
    State({'type': 'user-apk-feature-dropdown', 'index': MATCH}, 'id')
)
def update_feature_info(selected_index, feature_info_store, dropdown_id):
    if selected_index is None or not feature_info_store:
        return html.Div("No feature selected")
    
    data_type = dropdown_id['index']
    info = feature_info_store[data_type][selected_index]
    feature = info['feature']
    
    return html.Div([
        html.P(f"Feature: {feature}"),
        html.Div([
            html.A("Open URL", href=f"https://{feature}", target="_blank", className="me-2"),
            html.A("AlienVault", href=info['alienvault_link'], target="_blank", className="me-2"),
            html.A("WHOIS", href=info['whois_link'], target="_blank", className="me-2"),
            html.A("VirusTotal", href=f"https://www.virustotal.com/gui/domain/{feature}", target="_blank", className="me-2"),
            html.A("Shodan", href=f"https://www.shodan.io/search?query={feature}", target="_blank", className="me-2"),
            html.A("URLScan", href=f"https://urlscan.io/search/#{feature}", target="_blank", className="me-2"),
        ])
    ])

@app.callback(
    [Output("user-apk-highlight-list", "children"),
     Output("user-apk-highlight-config-store", "data"),
     Output("user-apk-highlight-dropdown", "value")],
    [Input("user-apk-highlight-dropdown", "value"),
     Input("user-apk-add-highlight", "n_clicks"),
     Input({"type": "user-apk-remove-highlight", "index": ALL}, "n_clicks")],
    [State("user-apk-highlight-pattern", "value"),
     State("user-apk-highlight-color", "value"),
     State("user-apk-highlight-config-store", "data")],
    prevent_initial_call=True
)
def update_highlight_config(selected_presets, add_clicks, remove_clicks, custom_pattern, custom_color, stored_config):
    ctx = dash.callback_context
    triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]

    if stored_config is None:
        stored_config = []

    if triggered_id == "user-apk-highlight-dropdown":
        # Add new selected presets
        for preset in selected_presets or []:
            if preset not in [item['name'] for item in stored_config]:
                stored_config.append({
                    "name": preset,
                    "regex": preset_configs[preset]["regex"],
                    "color": preset_configs[preset]["color"]
                })

    elif triggered_id == "user-apk-add-highlight":
        if custom_pattern and custom_color and is_valid_color(custom_color):
            stored_config.append({
                "name": f"Custom: {custom_pattern}",
                "regex": custom_pattern,
                "color": custom_color
            })

    elif "user-apk-remove-highlight" in triggered_id:
        remove_index = json.loads(triggered_id)['index']
        if 0 <= remove_index < len(stored_config):
            removed_item = stored_config.pop(remove_index)
            if not removed_item['name'].startswith("Custom:"):
                selected_presets = [preset for preset in (selected_presets or []) if preset != removed_item['name']]

    highlight_list = create_highlight_list(stored_config)
    return highlight_list, stored_config, selected_presets

def create_highlight_list(highlight_config):
    return [
        html.Div([
            html.Span(f"{item['name']}: ", style={"fontWeight": "bold"}),
            html.Span(f"{item['regex'][:30]}..." if len(item['regex']) > 30 else item['regex']),
            html.Span(f" ({item['color']})", style={"color": item['color']}),
            html.Button("×", id={"type": "user-apk-remove-highlight", "index": i}, n_clicks=0, style={"marginLeft": "10px"}),
        ], style={"marginBottom": "5px"})
        for i, item in enumerate(highlight_config)
    ]

def is_valid_color(color):
    if re.match(r'^#(?:[0-9a-fA-F]{3}){1,2}$', color):
        return True
    valid_color_names = ['red', 'blue', 'green', 'yellow', 'purple', 'orange', 'black', 'white']
    return color.lower() in valid_color_names

# Callbacks for each data type
for data_type in ['urls', 'domains', 'subdomains']:
    @app.callback(
        Output(f'user-apk-feature-info-{data_type}', 'children'),
        [Input(f'user-apk-feature-dropdown-{data_type}', 'value')],
        [State(f'user-apk-feature-info-store-{data_type}', 'data')]
    )
    def update_feature_info(selected_index, feature_info, data_type=data_type):
        if selected_index is None or not feature_info:
            return html.Div("No feature selected")
        
        info = feature_info[selected_index]
        feature = info['feature']
        
        return html.Div([
            html.P(f"Feature: {feature}"),
            html.Div([
                #html.A("Open URL", href=f"https://{feature}", target="_blank", className="me-2"),
                html.A("AlienVault", href=info['alienvault_link'], target="_blank", className="me-2"),
                html.A("WHOIS", href=info['whois_link'], target="_blank", className="me-2"),
                html.A("VirusTotal", href=f"https://www.virustotal.com/gui/domain/{feature}", target="_blank", className="me-2"),
                html.A("Shodan", href=f"https://www.shodan.io/search?query={feature}", target="_blank", className="me-2"),
                html.A("URLScan", href=f"https://urlscan.io/search/#{feature}", target="_blank", className="me-2"),
            ])
        ])

@app.callback(
    [Output('user-apk-upload-store', 'data'),
     Output('user-apk-upload-list', 'children')],
    [Input('user-apk-upload', 'contents'),
     Input('user-apk-upload', 'filename'),
     Input({'type': 'move-up', 'index': ALL}, 'n_clicks'),
     Input({'type': 'move-down', 'index': ALL}, 'n_clicks'),
     Input({'type': 'remove-apk', 'index': ALL}, 'n_clicks')],
    [State('user-apk-upload-store', 'data')]
)
def manage_uploaded_files(contents, filenames, move_up_clicks, move_down_clicks, remove_clicks, stored_data):
    ctx = callback_context
    if not ctx.triggered:
        raise PreventUpdate
    
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]

    if trigger_id == 'user-apk-upload':
        # Handle new file uploads
        stored_data = stored_data or []
        for content, filename in zip(contents or [], filenames or []):
            if content and filename:
                try:
                    # Save file to server and get path
                    server_path = save_uploaded_file_to_server(content, filename)
                    
                    # Extract APK info
                    apk = APK(server_path)
                    stored_data.append({
                        'filename': filename,
                        'package_name': apk.get_package(),
                        'version_code': apk.get_androidversion_code(),
                        'server_path': server_path
                    })
                except Exception as e:
                    logger.error(f"Error processing APK {filename}: {str(e)}")

    else:
        # Handle move/remove actions
        action, index = json.loads(trigger_id)['type'], json.loads(trigger_id)['index']

        if action == 'move-up' and index > 0:
            stored_data[index], stored_data[index-1] = stored_data[index-1], stored_data[index]
        elif action == 'move-down' and index < len(stored_data) - 1:
            stored_data[index], stored_data[index+1] = stored_data[index+1], stored_data[index]
        elif action == 'remove-apk':
            # Remove file from server when removing from list
            file_to_remove = stored_data.pop(index)
            try:
                os.remove(file_to_remove['server_path'])
            except Exception as e:
                logger.error(f"Error removing file {file_to_remove['filename']}: {str(e)}")

    upload_list = create_upload_list(stored_data)
    return stored_data, upload_list

def create_upload_list(stored_data):
    return html.Div([
        dbc.ListGroup([
            dbc.ListGroupItem([
                dbc.Row([
                    dbc.Col([
                        html.H5(truncate_string(item['filename'], 30), className='mb-1', title=item['filename']),
                        html.Small(f"Package: {item['package_name']}", className='text-muted d-block'),
                        html.Small(f"Version Code: {item['version_code']}", className='text-muted d-block'),
                    ], width=9),
                    dbc.Col([
                        dbc.ButtonGroup([
                            dbc.Button("↑", id={'type': 'move-up', 'index': i}, size="sm", color="light", className="mr-1"),
                            dbc.Button("↓", id={'type': 'move-down', 'index': i}, size="sm", color="light", className="mr-1"),
                            dbc.Button("×", id={'type': 'remove-apk', 'index': i}, size="sm", color="danger"),
                        ], size="sm")
                    ], width=3, className="d-flex align-items-center justify-content-end")
                ], className="g-0")
            ])
            for i, item in enumerate(stored_data)
        ])
    ])

def truncate_string(string, max_length):
    return string[:max_length] + '...' if len(string) > max_length else string

def process_uploaded_apks(stored_data, highlight_config, num_cores, parser_selection, sort_order, session_id):
    results = {
        'urls': [],
        'domains': [],
        'subdomains': []
    }
    
    for i, item in enumerate(stored_data):
        # Use the server-side file path directly
        apk_path = item['server_path']
        features = extract_apk_features(apk_path, 'urls', False, parser_selection)
        
        version = item['filename'] if sort_order == 'ui' else item['version_code']
        ui_index = i
        
        for feature in features:
            # Parse the URL to extract components
            parsed_url = tldextract.extract(feature)
            subdomain = '.'.join(filter(None, [parsed_url.subdomain, parsed_url.domain, parsed_url.suffix]))
            domain = '.'.join(filter(None, [parsed_url.domain, parsed_url.suffix]))
            
            # Add to each data type
            if feature:  # URLs
                results['urls'].append({'Data': feature, 'version': version, 'ui_order': ui_index})
            if domain:  # Domains
                results['domains'].append({'Data': domain, 'version': version, 'ui_order': ui_index})
            if subdomain:  # Subdomains
                results['subdomains'].append({'Data': subdomain, 'version': version, 'ui_order': ui_index})
    
    # Generate plots for each data type
    plot_results = {}
    for data_type in ['urls', 'domains', 'subdomains']:
        if results[data_type]:
            plot_result = plot_data(results[data_type], "User Uploaded APKs", highlight_config, data_type, sort_order)
            plot_results[data_type] = plot_result
        else:
            plot_results[data_type] = None
    
    return plot_results

def save_uploaded_file(item, temp_dir):
    content_type, content_string = item['content'].split(',')
    decoded = base64.b64decode(content_string)
    file_path = os.path.join(temp_dir, item['filename'])
    with open(file_path, 'wb') as f:
        f.write(decoded)
    return file_path

@app.callback(
    [Output("user-apk-spinner-wrapper", "style", allow_duplicate=True),
     Output("user-apk-status-message", "children", allow_duplicate=True),
     Output("user-apk-status-message", "color", allow_duplicate=True),
     Output("user-apk-error-message", "style", allow_duplicate=True),
     Output("user-apk-error-message", "is_open", allow_duplicate=True)],
    [Input("user-apk-submit-button", "n_clicks")],
    [State("user-apk-upload-store", "data")],
    prevent_initial_call=True
)
def show_spinner_on_click(n_clicks, stored_data):
    """Show spinner when submit button is clicked"""
    if n_clicks and stored_data:
        return {"display": "block"}, "Starting analysis...", "primary", {"display": "none"}, False
    return {"display": "none"}, "Waiting for input...", "secondary", {"display": "none"}, False

# Server capacity indicator callback
@app.callback(
    [Output("server-capacity-indicator", "value"),
     Output("server-capacity-indicator", "color"),
     Output("server-capacity-text", "children")],
    [Input("user-apk-progress-interval", "n_intervals")]
)
def update_server_capacity(n_intervals):
    """Update server capacity indicator"""
    num_active = len(active_sessions)
    capacity_percentage = (num_active / MAX_CONCURRENT_USERS) * 100
    
    # Choose colour based on load
    if capacity_percentage < 50:
        color = "success"
        status = "Low Load"
    elif capacity_percentage < 80:
        color = "warning"
        status = "Medium Load"
    else:
        color = "danger"
        status = "High Load"
    
    # Create status text
    text = f"{status}: {num_active}/{MAX_CONCURRENT_USERS} active analyses"
    
    return capacity_percentage, color, text



