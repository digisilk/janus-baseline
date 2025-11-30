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
# callbacks/apk_historical_analysis_callbacks.py
from dash import dcc, html, callback_context, no_update
import dash
from dash.dependencies import Input, Output, State, ALL
from app import app
from logic.historical_connectivity_logic import process_apks, generate_download_link
import json
import dash_bootstrap_components as dbc
import re
from dash.exceptions import PreventUpdate
import logging
from functools import lru_cache
from layouts.historical_connectivity_layout import preset_configs
import uuid
from utils.ui_logger import UILogger
import config
import requests
import time

# Concurrency controls
from utils.concurrency_manager import active_sessions, MAX_CONCURRENT_USERS, register_session, remove_session, has_capacity

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def is_valid_color(color):
    # Check for valid hex colour
    if re.match(r'^#(?:[0-9a-fA-F]{3}){1,2}$', color):
        return True
    # Check for valid colour name
    valid_color_names = ['red', 'blue', 'green', 'yellow', 'purple', 'orange', 'black', 'white']
    return color.lower() in valid_color_names

# Load package IDs with counts
try:
    with open('filtered_package_ids_with_counts10_ver.json', 'r') as f:
        package_data = json.load(f)
    package_dict = {pkg['name']: pkg['count'] for pkg in package_data}
    logger.info(f"Loaded {len(package_dict)} package IDs")
except Exception as e:
    logger.error(f"Error loading package IDs: {str(e)}")
    package_dict = {}

@lru_cache(maxsize=100)
def custom_search(search_value, limit=100):
    search_value = search_value.lower()
    
    def match_score(pkg):
        pkg_lower = pkg.lower()
        pkg_parts = pkg_lower.split('.')
        score = 0
        
        # Exact match gets highest score
        if search_value == pkg_lower:
            return 1000000 + package_dict[pkg]
        
        # Match start of any part
        if any(part.startswith(search_value) for part in pkg_parts):
            score += 10000
        
        # Substring match
        elif search_value in pkg_lower:
            score += 1000
        
        # Add version count to score
        score += package_dict[pkg]
        
        return score
    
    # Filter and sort packages
    matched_packages = [(pkg, match_score(pkg)) for pkg in package_dict.keys() if match_score(pkg) > 0]
    sorted_packages = sorted(matched_packages, key=lambda x: -x[1])
    
    return [pkg for pkg, _ in sorted_packages[:limit]]

@app.callback(
    [Output("highlight-list", "children"),
     Output("highlight-config-store", "data")],
    [Input(f"highlight-checklist-{category.lower().replace(' ', '-')}", "value")
     for category in preset_configs.keys()] +
    [Input("add-highlight", "n_clicks"),
     Input({"type": "remove-btn", "index": ALL}, "n_clicks")],  # Pattern matching for remove buttons
    [State("highlight-terms", "value"),
     State("highlight-color-picker", "value"),
     State("highlight-config-store", "data")],
    prevent_initial_call=True
)
def update_highlight_config(*args):
    n_categories = len(preset_configs)
    checklist_values = args[:n_categories]
    add_clicks = args[n_categories]
    remove_clicks = args[n_categories + 1:-3] if len(args) > n_categories + 1 else []
    custom_terms = args[-3]
    custom_color = args[-2]
    stored_config = args[-1] or []

    ctx = dash.callback_context
    if not ctx.triggered:
        raise PreventUpdate
        
    triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    try:
        triggered_id = json.loads(triggered_id) if '{' in triggered_id else triggered_id
    except:
        pass

    # Handle remove button clicks
    if isinstance(triggered_id, dict) and triggered_id.get('type') == 'remove-btn':
        index = triggered_id.get('index')
        if index is not None and 0 <= index < len(stored_config):
            stored_config = [item for i, item in enumerate(stored_config) if i != index]

    # Handle preset selections
    elif "highlight-checklist" in str(triggered_id):
        category = next(cat for cat in preset_configs.keys() 
                      if cat.lower().replace(' ', '-') in str(triggered_id))
        # Clear existing presets for this category
        stored_config = [h for h in stored_config 
                        if h.get('type') != 'preset' or 
                        not h.get('name', '').startswith(f"{category}:")]
        
        # Add selected presets
        cat_index = list(preset_configs.keys()).index(category)
        if checklist_values[cat_index]:
            for selected_value in checklist_values[cat_index]:
                config = preset_configs[category][selected_value]
                stored_config.append({
                    "type": "preset",
                    "name": f"{category}: {selected_value}",
                    "terms": config["terms"],
                    "color": config["color"]
                })

    # Handle custom highlight addition
    elif triggered_id == "add-highlight" and custom_terms and custom_color:
        terms = [term.strip() for term in custom_terms.split(",") if term.strip()]
        if terms:
            stored_config.append({
                "type": "custom",
                "name": f"Custom: {', '.join(terms[:2])}{'...' if len(terms) > 2 else ''}",
                "terms": terms,
                "color": custom_color
            })

    # Create display list
    highlight_list = []
    for i, item in enumerate(stored_config):
        highlight_list.append(
            dbc.Card(
                dbc.CardBody([
                    html.Div([
                        html.Span(
                            "●",
                            style={
                                "color": item["color"],
                                "marginRight": "8px",
                                "fontSize": "20px"
                            }
                        ),
                        html.Span(
                            item["name"],
                            style={"flex": "1"}
                        ),
                        html.Button(  # Remove button with pattern-matching ID
                            "×",
                            id={"type": "remove-btn", "index": i},
                            className="btn-close",
                            **{
                                "aria-label": "Remove highlight",
                                "style": {
                                    "padding": "0.25rem",
                                    "fontSize": "1.2rem",
                                    "border": "none",
                                    "background": "none",
                                    "cursor": "pointer",
                                    "color": "#666"
                                }
                            }
                        )
                    ], style={
                        "display": "flex",
                        "alignItems": "center",
                        "justifyContent": "space-between"
                    })
                ]),
                className="mb-2"
            )
        )

    return highlight_list, stored_config

# Convert highlight config to regex patterns
def convert_highlight_config_to_regex(config):
    if not config:
        return []
        
    regex_config = []
    for item in config:
        # Escape special regex characters in terms
        escaped_terms = [re.escape(term) for term in item["terms"]]
        # Join terms with OR operator
        regex_pattern = "|".join(escaped_terms)
        regex_config.append({
            "regex": regex_pattern,
            "color": item["color"]
        })
    return regex_config

@app.callback(
    [Output("results-historical-connectivity", "children"),
     Output("historical-error-message", "children"),
     Output("historical-error-message", "style"),
     Output("historical-error-message", "is_open"),
     Output("submit-button", "disabled"),
     Output("submit-button", "children"),
     Output("loading-output", "children"),
     Output("session-id-store", "data"),
     Output("historical-status-message", "children"),
     Output("historical-status-message", "color"),
     Output("historical-spinner-wrapper", "style")],
    [Input("submit-button", "n_clicks")],
    [State("api-key", "value"),
     State("start-date", "value"),
     State("end-date", "value"),
     State("package-list-dropdown", "value"),
     State("desired-versions", "value"),
     State("highlight-config-store", "data"),
     State("num-cores-slider", "value"),
     State("parser-selection", "value")]
)
def process_apks_callback(n_clicks, api_key, start_date, end_date, package_list_input, desired_versions, highlight_config, num_cores, parser_selection):
    if n_clicks is None:
        raise PreventUpdate

    ctx = callback_context
    if not ctx.triggered:
        raise PreventUpdate
    
    # Check if a package is selected
    if not package_list_input:
        return [], "Please select an app to analyse", {"display": "block"}, True, False, "Analyse App", None, None, "Waiting for app selection...", "warning", {"display": "none"}
    
    # Check if API key is provided and appears valid (additional safety check)
    from utils.apk_analysis_core import get_ui_config
    cfg = get_ui_config()
    if cfg.get('show_api_key_input', True):  # Only check if API key input is visible
        if not api_key or len(api_key.strip()) == 0:
            return [], "AndroZoo API key is required", {"display": "block"}, True, False, "Analyse App", None, None, "Missing API key", "danger", {"display": "none"}
        if len(api_key.strip()) != 64 or not all(c in '0123456789abcdefABCDEF' for c in api_key.strip()):
            return [], "Invalid AndroZoo API key format", {"display": "block"}, True, False, "Analyse App", None, None, "Invalid API key", "danger", {"display": "none"}
    
    # Generate a unique session ID for this request
    session_id = str(uuid.uuid4())
    
    try:
        # Get session-specific logger
        logger_data = UILogger.get_logger(session_id)
        logger = logger_data['logger']
        logger.info("Starting new Historical Connectivity analysis")
        
        # Check if we have too many active sessions
        if not has_capacity():
            logger.warning("Server is busy. Please try again later.")
            status_message = "Server is busy. Please try again later."
            status_color = "warning"
            spinner_style = {"display": "none"}
            return [], "Server is busy. Please try again later.", {"display": "block"}, True, False, "Analyse App", None, session_id, status_message, status_color, spinner_style
        
        # Register this session as active
        register_session(session_id, {
            'num_apks': desired_versions or 0,
            'package': package_list_input
        })
        logger.info(f"Registered session {session_id}. Current active sessions: {len(active_sessions)}")
        
        # Show "processing" status and disable submit button
        status_message = "Processing APK data... This may take a few minutes."
        status_color = "primary"
        spinner_style = {"display": "block"}
        
        # Convert the new highlight config format to the expected regex format
        if highlight_config:
            highlight_config = convert_highlight_config_to_regex(highlight_config)
        
        # Process the APKs directly
        results = process_apks(
            n_clicks, 
            api_key, 
            start_date, 
            end_date, 
            package_list_input, 
            desired_versions, 
            highlight_config, 
            num_cores, 
            parser_selection,
            session_id
        )

        output_results = []
        # Define the desired order
        display_order = ['domains', 'subdomains', 'urls']
        
        # Process results in the specified order
        for data_type in display_order:
            if data_type not in results:
                continue
                
            result = results[data_type]
            if result['too_large_to_display']:
                output_results.extend([
                    html.H4(f"{data_type.capitalize()} Analysis"),
                    html.P(f"The {data_type} dataset is too large to display ({result['feature_count']} features). Please download the figure to view."),
                    generate_download_link(result['figure'], package_list_input, data_type),
                    html.Hr()
                ])
            else:
                dropdown_options = [{'label': info['feature'], 'value': i} for i, info in enumerate(result['feature_info'])]
                
                output_results.extend([
                    html.H4(f"{data_type.capitalize()} Analysis"),
                    dcc.Graph(figure=result['figure'], style={'height': '800px'}),
                    html.Div([
                        generate_download_link(result['figure'], package_list_input, data_type),
                    ], style={"display": "flex", "alignItems": "center", "marginTop": "10px"}),
                    dcc.Store(id=f'feature-info-store-{data_type}', data=result['feature_info']),
                    html.H5("Feature Information"),
                    dcc.Dropdown(
                        id=f'feature-dropdown-{data_type}',
                        options=dropdown_options,
                        value=0 if dropdown_options else None,
                        placeholder="Select a feature",
                        style={'marginBottom': '10px'}
                    ),
                    html.Div(id=f'feature-info-{data_type}'),
                    html.Hr()
                ])

        if not output_results:
            output_results.append(html.P("No data found for the selected package."))
        
        logger.info("Historical Connectivity processing complete")
        
        # Update status to "complete" and re-enable submit button
        status_message = "Analysis complete!"
        status_color = "success"
        spinner_style = {"display": "none"}
        
        # Remove from active sessions since we're done
        remove_session(session_id)
        logger.info(f"Removed session {session_id}. Current active sessions: {len(active_sessions)}")
        
        return output_results, "", {"display": "none"}, False, False, "Analyse App", None, session_id, status_message, status_color, spinner_style
    except Exception as e:
        error_message = f"An error occurred: {str(e)}"
        logger.error(error_message)
        
        # Remove from active sessions in case of error
        remove_session(session_id)
        logger.info(f"Removed session {session_id} due to error. Current active sessions: {len(active_sessions)}")
        
        # Update status to "error" and re-enable submit button
        status_message = "Error during analysis. See details below."
        status_color = "danger"
        spinner_style = {"display": "none"}
        
        return [], error_message, {"display": "block"}, True, False, "Analyse App", None, session_id, status_message, status_color, spinner_style

@app.callback(
    Output('progress-historical-connectivity', 'children'),
    [Input('progress-interval', 'n_intervals')],
    [State('session-id-store', 'data')]
)
def update_progress(n, session_id):
    if session_id:
        return UILogger.get_logs(session_id)
    else:
        # fallback to empty logs if no session_id
        # avoids the error when session_id is None
        return html.Div("No active session. Start an analysis to see progress.")

for data_type in ['urls', 'domains', 'subdomains']:
    @app.callback(
        Output(f'feature-info-{data_type}', 'children'),
        [Input(f'feature-dropdown-{data_type}', 'value')],
        [State(f'feature-info-store-{data_type}', 'data')]
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
    [Output("package-list-dropdown", "options"),
     Output("package-list-dropdown", "value"),
     Output("selected-package-store", "data")],
    [Input("package-list-dropdown", "search_value"),
     Input("package-list-dropdown", "value")],
    [State("selected-package-store", "data")]
)
def update_dropdown_and_store(search_value, dropdown_value, stored_value):
    ctx = callback_context
    triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]

    if triggered_id == "package-list-dropdown" and dropdown_value is not None:
        return no_update, dropdown_value, dropdown_value

    if not search_value:
        return [], no_update, stored_value

    try:
        matches = custom_search(search_value)
        filtered_options = [
            {
                "label": html.Div([
                    f"{pid} (Versions: {package_dict[pid]})",
                    html.A(
                        "🔗",
                        href=f"https://play.google.com/store/apps/details?id={pid}",
                        target="_blank",
                        style={"marginLeft": "10px"},
                        title="View on Google Play"
                    )
                ]),
                "value": pid
            } for pid in matches
        ]

        # The stored value is always in the options
        if stored_value and not any(option["value"] == stored_value for option in filtered_options):
            stored_count = package_dict.get(stored_value, 0)
            filtered_options.insert(0, {
                "label": html.Div([
                    f"{stored_value} (Versions: {stored_count})",
                    html.A(
                        "🔗",
                        href=f"https://play.google.com/store/apps/details?id={stored_value}",
                        target="_blank",
                        style={"marginLeft": "10px"},
                        title="View on Google Play"
                    )
                ]),
                "value": stored_value
            })

        logger.info(f"Found {len(filtered_options)} matches for search value: {search_value}")
        return filtered_options, no_update, stored_value
    except Exception as e:
        logger.error(f"Error in update_dropdown_and_store: {str(e)}")
        return [], no_update, stored_value

@app.callback(
    [Output("historical-spinner-wrapper", "style", allow_duplicate=True),
     Output("historical-status-message", "children", allow_duplicate=True),
     Output("historical-status-message", "color", allow_duplicate=True),
     Output("historical-error-message", "style", allow_duplicate=True),
     Output("historical-error-message", "is_open", allow_duplicate=True),
     Output("submit-button", "disabled", allow_duplicate=True),
     Output("submit-button", "children", allow_duplicate=True)],
    [Input("submit-button", "n_clicks"),
     Input("package-list-dropdown", "value"),
     Input("api-key", "valid"),
     Input("api-key", "invalid")],
    [State("api-key", "value")],
    prevent_initial_call=True
)
def show_spinner_on_click(n_clicks, package_value, api_key_valid, api_key_invalid, api_key_value):
    """Show the spinner immediately when the submit button is clicked and disable the button"""
    from utils.apk_analysis_core import get_ui_config
    cfg = get_ui_config()
    
    ctx = callback_context
    triggered_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    # Check if API key input is hidden (meaning it's configured elsewhere)
    api_key_hidden = not cfg.get('show_api_key_input', True)
    
    # Determine if we need a valid API key
    needs_api_key = not api_key_hidden
    api_key_ready = api_key_hidden or (api_key_valid and not api_key_invalid and api_key_value and len(api_key_value.strip()) > 0)

    # Check for missing package
    if not package_value:
        return {"display": "none"}, "Please select a package", "warning", {"display": "none"}, False, True, "Analyse App"
    
    # Check for missing or invalid API key
    if needs_api_key and not api_key_ready:
        if not api_key_value or len(api_key_value.strip()) == 0:
            return {"display": "none"}, "Please enter a valid AndroZoo API key", "warning", {"display": "none"}, False, True, "Analyse App"
        elif api_key_invalid:
            return {"display": "none"}, "Invalid API key - please check your AndroZoo API key", "danger", {"display": "none"}, False, True, "Analyse App"
        else:
            return {"display": "none"}, "Validating API key...", "warning", {"display": "none"}, False, True, "Analyse App"
        
    if triggered_id == "submit-button" and n_clicks:
        return {"display": "block"}, "Starting analysis...", "primary", {"display": "none"}, False, True, "Processing..."
        
    return {"display": "none"}, "Ready to analyse", "success", {"display": "none"}, False, False, "Analyse App"

# callback to update the server capacity indicator
@app.callback(
    [Output("historical-server-capacity-indicator", "value"),
     Output("historical-server-capacity-indicator", "color"),
     Output("historical-server-capacity-text", "children")],
    [Input("progress-interval", "n_intervals")]
)
def update_historical_server_capacity(n_intervals):
    """Update the server capacity indicator for historical connectivity page"""
    num_active = len(active_sessions)
    capacity_percentage = (num_active / MAX_CONCURRENT_USERS) * 100
    
    # Pick color based on load
    if capacity_percentage < 50:
        color = "success"
        status = "Low Load"
    elif capacity_percentage < 80:
        color = "warning"
        status = "Medium Load"
    else:
        color = "danger"
        status = "High Load"
    
    # Create text info
    text = f"{status}: {num_active}/{MAX_CONCURRENT_USERS} active analyses"
    
    return capacity_percentage, color, text

# Add callback to reset checklist values
@app.callback(
    [Output(f"highlight-checklist-{category.lower().replace(' ', '-')}", "value")
     for category in preset_configs.keys()],
    [Input("url", "pathname")]  # Only trigger on page refresh
)
def reset_checklists(pathname):
    """Reset all checklist values when the page refreshes"""
    return [[] for _ in preset_configs.keys()]

# Simplified callback for highlight feedback
@app.callback(
    [Output("highlight-terms", "value"),
     Output("highlight-feedback", "children")],
    [Input("add-highlight", "n_clicks")],
    [State("highlight-terms", "value")]
)
def handle_highlight_feedback(n_clicks, terms):
    if not n_clicks or not terms:
        return "", ""
    
    # Clear input and show feedback
    return "", f"✓ Added: {terms}"

@app.callback(
    [Output("settings-collapse", "is_open"),
     Output("settings-collapse-button", "children")],
    [Input("settings-collapse-button", "n_clicks")],
    [State("settings-collapse", "is_open")],
)
def toggle_settings_collapse(n_clicks, is_open):
    if n_clicks:
        return not is_open, f"Advanced Settings {'▼' if is_open else '▲'}"
    return False, "Advanced Settings ▼"  # Default state is closed

@app.callback(
    [Output("desired-versions", "max"),
     Output("desired-versions", "placeholder"),
     Output("versions-help-text", "children")],
    [Input("url", "pathname")]  # Trigger on page load
)
def set_version_limits(pathname):
    """Set the maximum versions based on config"""
    cfg = config.get_effective_config()
    max_versions = cfg.get('max_versions', 4)
    
    placeholder = f"Max {max_versions} versions"
    help_text = f"Number of app versions to analyze (older versions first). Max: {max_versions}"
    return max_versions, placeholder, help_text

@app.callback(
    Output("api-key", "value"),
    [Input("url", "pathname")]  # Trigger on page load
)
def set_api_key_from_config(pathname):
    """Set the API key from config if available and not overridden"""
    cfg = config.get_effective_config()
    if not cfg.get('override_api_key') and cfg.get('api_key'):
        return cfg['api_key']
    return ""

@app.callback(
    [Output("api-key-heading", "style"),
     Output("api-key-input-group", "style")],
    [Input("url", "pathname")],  # Trigger on page load
    prevent_initial_call=False  # Allow initial call so it runs on page load
)
def control_api_key_visibility(pathname):
    """Show/hide API key input based on config"""
    from utils.apk_analysis_core import get_ui_config
    cfg = get_ui_config()
    
    if cfg.get('show_api_key_input', True):
        # Show the API key input
        return {}, {}
    else:
        # Hide the API key input completely
        return {"display": "none"}, {"display": "none"}

@app.callback(
    [Output("desired-versions", "value"),
     Output("desired-versions", "invalid"),
     Output("desired-versions", "valid")],
    [Input("desired-versions", "value")],
    [State("desired-versions", "max"),
     State("desired-versions", "min")]
)
def validate_versions_input(value, max_versions, min_versions):
    """Validate and correct the versions input"""
    if value is None or value == "":
        return 4, False, True  # Default to 4
    
    try:
        int_value = int(value)
    except (ValueError, TypeError):
        return 4, True, False  # Invalid input, reset to default
    
    # Enforce limits and correct if needed
    if int_value < min_versions:
        return min_versions, True, False  # Too low, correct to minimum
    elif int_value > max_versions:
        return max_versions, True, False  # Too high, correct to maximum
    else:
        return int_value, False, True  # Valid input

@app.callback(
    [Output("api-key", "valid"),
     Output("api-key", "invalid"),
     Output("api-key-help-text", "children"),
     Output("api-key-help-text", "style"),
     Output("api-key-status", "children"),
     Output("api-key-status", "style")],
    [Input("api-key", "value"),
     Input("url", "pathname")]  # Also trigger on page load to check config
)
def validate_api_key(api_key, pathname):
    """Validate AndroZoo API key by making a test request"""
    # Check if API key input should be shown
    from utils.apk_analysis_core import get_ui_config
    cfg = get_ui_config()
    
    if not cfg.get('show_api_key_input', True):
        # API key input is hidden, so hide help text too
        return False, False, "", {"display": "none"}, "", {"display": "none"}
    
    # Normal validation logic when input is visible
    if not api_key or len(api_key.strip()) == 0:
        return False, False, "Required for downloading APKs from AndroZoo database.", {"display": "block", "marginBottom": "15px", "color": "#6c757d"}, "⏳", {"minWidth": "40px", "justifyContent": "center", "backgroundColor": "#f8f9fa", "color": "#6c757d"}
    
    # Basic format check - AndroZoo API keys are typically 64 character hex strings
    api_key = api_key.strip()
    if len(api_key) != 64 or not all(c in '0123456789abcdefABCDEF' for c in api_key):
        return False, True, "✗ Invalid API key format. Should be 64 character hex string.", {"display": "block", "marginBottom": "15px", "color": "#dc3545"}, "✗", {"minWidth": "40px", "justifyContent": "center", "backgroundColor": "#f8d7da", "color": "#721c24"}
    
    try:
        # Make a quick test request to AndroZoo API
        # Use the download endpoint with a dummy SHA256 to test the API key
        # This returns 400 "Invalid SHA256" for valid keys, or 400 "Invalid apikey" for invalid key
        test_url = "https://androzoo.uni.lu/api/download"
        params = {
            'apikey': api_key,
            'sha256': '0000000000000000000000000000000000000000000000000000000000000000'  # Dummy SHA256
        }
        
        response = requests.get(test_url, params=params, timeout=5)
        
        if response.status_code == 403:
            # Invalid API key
            return False, True, "✗ Invalid API key. Please check your AndroZoo API key.", {"display": "block", "marginBottom": "15px", "color": "#dc3545"}, "✗", {"minWidth": "40px", "justifyContent": "center", "backgroundColor": "#f8d7da", "color": "#721c24"}
        elif response.status_code == 404:
            # Valid API key (file not found for our dummy SHA256)
            return True, False, "✓ Valid AndroZoo API key", {"display": "block", "marginBottom": "15px", "color": "#28a745"}, "✓", {"minWidth": "40px", "justifyContent": "center", "backgroundColor": "#d4edda", "color": "#155724"}
        elif response.status_code == 200:
            # Shouldn't happen with dummy SHA256, but means API key works
            return True, False, "✓ Valid AndroZoo API key", {"display": "block", "marginBottom": "15px", "color": "#28a745"}, "✓", {"minWidth": "40px", "justifyContent": "center", "backgroundColor": "#d4edda", "color": "#155724"}
        else:
            # Other error (network, server, etc.)
            return False, False, f"⚠ Could not validate API key (HTTP {response.status_code}). Will try during analysis.", {"display": "block", "marginBottom": "15px", "color": "#ffc107"}, "⚠", {"minWidth": "40px", "justifyContent": "center", "backgroundColor": "#fff3cd", "color": "#856404"}
            
    except requests.exceptions.Timeout:
        return False, False, "⚠ Validation timeout. Will verify during analysis.", {"display": "block", "marginBottom": "15px", "color": "#ffc107"}, "⚠", {"minWidth": "40px", "justifyContent": "center", "backgroundColor": "#fff3cd", "color": "#856404"}
    except requests.exceptions.RequestException:
        return False, False, "⚠ Network error. Will verify during analysis.", {"display": "block", "marginBottom": "15px", "color": "#ffc107"}, "⚠", {"minWidth": "40px", "justifyContent": "center", "backgroundColor": "#fff3cd", "color": "#856404"}
    except Exception as e:
        return False, False, "⚠ Could not validate API key. Will try during analysis.", {"display": "block", "marginBottom": "15px", "color": "#ffc107"}, "⚠", {"minWidth": "40px", "justifyContent": "center", "backgroundColor": "#fff3cd", "color": "#856404"}


