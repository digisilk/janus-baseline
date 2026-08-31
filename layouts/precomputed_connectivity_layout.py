from dash import dcc, html
import dash_bootstrap_components as dbc
from datetime import datetime
import json
import os
from config import ENABLE_CSV_EXPORT



ascii_logo = """
     ██  █████  ███    ██ ██    ██ ███████ 
     ██ ██   ██ ████   ██ ██    ██ ██      
     ██ ███████ ██ ██  ██ ██    ██ ███████ 
██   ██ ██   ██ ██  ██ ██ ██    ██      ██ 
 █████  ██   ██ ██   ████  ██████  ███████ """

def create_highlight_options(preset_configs):
    options = []
    for category, config in preset_configs.items():
        options.append({"label": category, "value": category})
    options.append({"label": "Custom", "value": "custom"})
    return options

# Load precomputed package metadata
def get_precomputed_packages():
    try:
        metadata_path = os.path.join('precomputed_data', 'metadata.json')
        if os.path.exists(metadata_path):
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
                return metadata['processed_packages']
        return []
    except Exception as e:
        print(f"Error loading precomputed packages: {e}")
        return []

preset_configs = {
    "Chinese Tech Giants": {"regex": "baidu|alibaba|tencent|huawei|xiaomi|bytedance|weibo|wechat|qq|douyin|\\.cn$|\\.中国$|\\.中國$", "color": "#0000FF"},
    "U.S. Tech Giants": {"regex": "google|facebook|amazon|apple|microsoft|twitter|linkedin|instagram|snapchat", "color": "#0000FF"},
    "Russian Tech Giants": {"regex": "yandex|mail\\.ru|vk\\.com|kaspersky|sberbank|rambler|\\.ru$|\\.рф$", "color": "#0000FF"},
    
    "U.S. Cloud Services": {"regex": "aws\\.amazon|amazonwebservices|azure|microsoft\\.com|googlecloud|cloud\\.google|digitalocean|heroku|cloudflare|akamai|fastly", "color": "#0000FF"},
    "Chinese Cloud Services": {"regex": "aliyun|alicloud|tencentcloud|huaweicloud|baiduyun|qcloud", "color": "#0000FF"},
    "Russian Cloud Services": {"regex": "selectel|cloudmts|sbercloud|mail\\.ru", "color": "#0000FF"},

    "Education": {"regex": "edu|\\.edu$|university|school|college", "color": "#4B0082"},
}

layout = dbc.Container([
    dbc.Row(dbc.Col(html.Pre(ascii_logo, style={'font-family': 'monospace', 'color': 'blue'}))),
    dbc.Row(dbc.Col(html.Img(src="/assets/sponsors.png",
                             style={'height': '71px', 'display': 'inline-block', 'margin-bottom': '0px',
                                    'margin-top': '0px'}))),
    # Add the script for the custom JavaScript
    html.Script(src='/assets/custom.js'),
    # Add empty div with ID for copy button container
    dbc.Row([
        dbc.Col([
            dbc.Form([
                html.H4("Precomputed Connectivity Analysis", className="mb-3"),
                html.Div([
                    html.P([
                        "This view uses ",
                        html.Strong("pre-computed data"),
                        " for faster analysis. Each package has 10 APK versions pre-processed."
                    ], className="alert alert-info")
                ]),
                
                dbc.Label("Package Name"),
                dcc.Dropdown(
                    id="precomputed-package-dropdown",
                    options=[],
                    value=None,
                    placeholder="Select a pre-computed package",
                    searchable=True,
                    clearable=True,
                ),
                
                dbc.Label("Highlight Configuration"),
                dbc.Alert([
                    html.I(className="fas fa-info-circle me-2"),
                    "Changes to highlight settings require regenerating the visualization to take effect."
                ], color="info", className="mb-2", style={"padding": "8px 12px", "fontSize": "0.875rem"}),
                dcc.Dropdown(
                    id='precomputed-highlight-dropdown',
                    options=[{'label': k, 'value': k} for k in preset_configs.keys()],
                    multi=True,
                    placeholder="Select preset highlight patterns",
                    style={'marginBottom': '10px'}
                ),
                html.Div([
                    dbc.Input(id="precomputed-highlight-pattern", type="text", placeholder="Enter regex pattern", className="mb-2"),
                    dbc.Input(id="precomputed-highlight-color", type="text", placeholder="Enter color (e.g., #FF0000)", className="mb-2"),
                    dbc.Button("Add Custom Highlight", id="precomputed-add-highlight", color="secondary", size="sm", className="mb-2"),
                ], id="precomputed-custom-highlight-inputs"),
                html.Div(id="precomputed-highlight-list", style={'maxHeight': '200px', 'overflowY': 'auto'}),
                
                dbc.Button("Generate Visualization", id="precomputed-submit-button", color="primary", size="md", className="mt-3", style={'width': '100%'}),
                
                # Stats section
                html.Div([
                    html.Hr(className="my-2"),
                    html.H5("Precomputed Data Stats", className="mt-3"),
                    html.Div(id="precomputed-stats-display")
                ], className="mt-4"),
                
                # Domains filter section
                html.Div([
                    html.Hr(className="my-2"),
                    html.H5("Domains Filter", className="mt-3"),
                    dbc.Checkbox(
                        id="precomputed-show-only-metadata-domains",
                        label="Show only domains with metadata",
                        value=False,
                        className="mb-2"
                    ),
                    html.Small(
                        "When checked, the domains visualization will only show domains that have additional metadata.",
                        className="text-muted"
                    )
                ], className="mt-3", id="precomputed-domains-filter", style={"display": "none"})
            ])
        ], width=12, lg=4, className="mb-4"),
        dbc.Col([
            html.H4("Analysis Status"),
            dbc.Alert(
                children="Select a package to analyze",
                id="precomputed-status-message",
                color="secondary",
                className="mb-3"
            ),
            # Add error message alert that will be hidden until needed
            dbc.Alert(
                children="",
                id="precomputed-error-message",
                color="danger",
                className="mb-3",
                style={"display": "none"},
                is_open=False
            ),
            html.Div([
                dbc.Spinner(
                    children=html.Div(id="precomputed-spinner-container", style={"height": "50px"}),
                    id="precomputed-spinner",
                    color="primary",
                    type="border"
                ),
            ], id="precomputed-spinner-wrapper", style={"display": "none"}),
            
            html.H4("Results"),
            # CSV download buttons — enabled by analysis callback once results are available
            html.Div([
                *(
                    [
                        html.Button(
                            'Download URLs CSV',
                            id='precomputed-btn-csv-urls',
                            className='btn btn-outline-secondary btn-sm mt-1 me-2',
                            disabled=True,
                        ),
                        html.Button(
                            'Download Subdomains CSV',
                            id='precomputed-btn-csv-subdomains',
                            className='btn btn-outline-secondary btn-sm mt-1 me-2',
                            disabled=True,
                        ),
                        html.Button(
                            'Download Domains CSV',
                            id='precomputed-btn-csv-domains',
                            className='btn btn-outline-secondary btn-sm mt-1',
                            disabled=True,
                        ),
                    ] if ENABLE_CSV_EXPORT else [
                        html.Div(id='precomputed-btn-csv-urls'),
                        html.Div(id='precomputed-btn-csv-subdomains'),
                        html.Div(id='precomputed-btn-csv-domains'),
                    ]
                ),
            ], className='mb-2'),
            html.Div([  # New container for loading and results
                dcc.Loading(
                    id="precomputed-loading",
                    type="default",
                    children=html.Div(id="precomputed-loading-output")
                ),

                html.Div(id="precomputed-results")
            ], style={'minHeight': '100px'})  # minimum height for loading indicator
        ], width=12, lg=8)
    ]),
    dcc.Store(id='precomputed-highlight-config-store'),
    # CSV export stores — hold csv_export dicts between analysis and download callbacks
    dcc.Store(id='precomputed-csv-store-urls'),
    dcc.Store(id='precomputed-csv-store-subdomains'),
    dcc.Store(id='precomputed-csv-store-domains'),
    # dcc.Download components — invisible; activated by download callbacks
    dcc.Download(id='precomputed-download-csv-urls'),
    dcc.Download(id='precomputed-download-csv-subdomains'),
    dcc.Download(id='precomputed-download-csv-domains'),
], fluid=True)
