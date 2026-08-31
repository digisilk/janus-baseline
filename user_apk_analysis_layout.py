from dash import dcc, html
import dash_bootstrap_components as dbc
import multiprocessing as mp
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


preset_configs = {
    "Chinese Tech Giants": {
        "regex": "baidu|alibaba|tencent|huawei|xiaomi|bytedance|weibo|wechat|qq|douyin|\\.cn$|\\.中国$|\\.中國$",
        "color": "#0000FF"},
    "U.S. Tech Giants": {"regex": "google|facebook|amazon|apple|microsoft|twitter|linkedin|instagram|snapchat",
                         "color": "#0000FF"},
    "Russian Tech Giants": {"regex": "yandex|mail\\.ru|vk\\.com|kaspersky|sberbank|rambler|\\.ru$|\\.рф$",
                            "color": "#0000FF"},

    "U.S. Cloud Services": {
        "regex": "aws\\.amazon|amazonwebservices|azure|microsoft\\.com|googlecloud|cloud\\.google|digitalocean|heroku|cloudflare|akamai|fastly",
        "color": "#0000FF"},
    "Chinese Cloud Services": {"regex": "aliyun|alicloud|tencentcloud|huaweicloud|baiduyun|qcloud", "color": "#0000FF"},
    "Russian Cloud Services": {"regex": "selectel|cloudmts|sbercloud|mail\\.ru", "color": "#0000FF"},

    "Education": {"regex": "edu|\\.edu$|university|school|college", "color": "#4B0082"},
}
layout = dbc.Container([
    dbc.Row(dbc.Col(html.Pre(ascii_logo, style={'font-family': 'monospace', 'color': 'blue'}))),
    dbc.Row(dbc.Col(html.Img(src="/assets/sponsors.png",
                             style={'height': '71px', 'display': 'inline-block', 'margin-bottom': '0px',
                                    'margin-top': '0px'}))),
    dbc.Row([
        dbc.Col([
            dbc.Form([
                html.H4("User APK Analysis", className="mb-3"),
                dcc.Upload(
                    id='user-apk-upload',
                    children=html.Div([
                        'Drag and Drop or ',
                        html.A('Select APK Files')
                    ]),
                    style={
                        'width': '100%',
                        'height': '60px',
                        'lineHeight': '60px',
                        'borderWidth': '1px',
                        'borderStyle': 'dashed',
                        'borderRadius': '5px',
                        'textAlign': 'center',
                        'margin': '10px 0'
                    },
                    multiple=True
                ),
                html.Div(id='user-apk-upload-list', style={'marginTop': '10px', 'marginBottom': '10px'}),
                
                # Highlight configuration dropdown
                html.Label("Preset Highlight Patterns"),
                dbc.Alert([
                    html.I(className="fas fa-info-circle me-2"),
                    "Changes to highlight settings require reanalysing the APKs to take effect."
                ], color="info", className="mb-2", style={"padding": "8px 12px", "fontSize": "0.875rem"}),
                dcc.Dropdown(
                    id='user-apk-highlight-dropdown',
                    options=[{'label': k, 'value': k} for k in preset_configs.keys()],
                    multi=True,
                    placeholder="Select preset highlight patterns",
                    style={'marginBottom': '10px'}
                ),
                
                # Custom highlight input section (always visible)
                html.Label("Custom Highlight Pattern"),
                dbc.Input(id="user-apk-highlight-pattern", type="text", placeholder="Enter regex pattern", className="mb-2"),
                dbc.Input(id="user-apk-highlight-color", type="text", placeholder="Enter color (e.g., #FF0000)", className="mb-2"),
                dbc.Button("Add Custom Highlight", id="user-apk-add-highlight", color="secondary", size="sm", className="mb-2"),
                
                # List of selected highlights
                html.Div(id="user-apk-highlight-list", style={'maxHeight': '200px', 'overflowY': 'auto'}),
                
                # Modify the number of cores slider
                html.Label("Number of Cores"),
                dcc.Slider(
                    id='user-apk-num-cores-slider',
                    min=1,
                    max=4,
                    step=1,
                    value=2,  # Default to 2 cores
                    marks={i: str(i) for i in range(1, 5)}
                ),
                
                # Modify the parser selection dropdown
                html.Label("Parser Selection"),
                dcc.Dropdown(
                    id='user-apk-parser-selection',
                    options=[
                        {'label': 'Custom DEX Parser', 'value': 'custom_dex'},
                        {'label': 'Androguard', 'value': 'androguard'}
                    ],
                    value='custom_dex',  # Set default to custom DEX parser
                    clearable=False
                ),
                
                # Add the sort order radio items
                html.Label("Sort Order"),
                dcc.RadioItems(
                    id='user-apk-sort-order',
                    options=[
                        {'label': 'UI Order', 'value': 'ui'},
                        {'label': 'Version Code', 'value': 'vercode'}
                    ],
                    value='vercode',
                    inline=True
                ),
                
                dbc.Button("Analyse APKs", id="user-apk-submit-button", color="primary", size="md", className="mt-3", style={'width': '100%'}),
                
                # Server capacity indicator
                html.Div([
                    html.Hr(className="my-2"),
                    html.Label("Server Capacity:", className="mt-2"),
                    dbc.Progress(
                        id="server-capacity-indicator",
                        value=0,  # Will be updated via callback
                        color="success",
                        style={"height": "20px"},
                        className="mt-1 mb-1"
                    ),
                    html.Div(id="server-capacity-text", className="text-muted small")
                ], className="mt-3")
            ])
        ], width=12, lg=4, className="mb-4"),
        dbc.Col([
            html.H4("Analysis Status"),
            dbc.Alert(
                "Waiting for input...",
                id="user-apk-status-message",
                color="secondary",
                className="mb-3"
            ),
            # Add error message alert that will be hidden until needed
            dbc.Alert(
                "",
                id="user-apk-error-message",
                color="danger",
                className="mb-3",
                style={"display": "none"},
                is_open=False
            ),
            html.Div([
                dbc.Spinner(
                    html.Div(id="user-apk-spinner-container", style={"height": "50px"}),
                    id="user-apk-spinner",
                    color="primary",
                    type="border"
                ),
            ], id="user-apk-spinner-wrapper", style={"display": "none"}),
            html.H4("Analysis Log"),
            html.Pre(
                id='user-apk-progress', 
                style={
                    'whiteSpace': 'pre-wrap', 
                    'wordBreak': 'break-word', 
                    'maxHeight': '200px', 
                    'overflowY': 'scroll',
                    'backgroundColor': '#f8f9fa',
                    'padding': '10px',
                    'border': '1px solid #ddd',
                    'borderRadius': '5px'
                }
            ),
            dcc.Interval(id='user-apk-progress-interval', interval=1000, n_intervals=0),
            html.H4("Results"),
            # CSV download buttons — enabled by analysis callback once results are available
            html.Div([
                *(
                    [
                        html.Button(
                            'Download URLs CSV',
                            id='user-apk-btn-csv-urls',
                            className='btn btn-outline-secondary btn-sm mt-1 me-2',
                            disabled=True,
                        ),
                        html.Button(
                            'Download Subdomains CSV',
                            id='user-apk-btn-csv-subdomains',
                            className='btn btn-outline-secondary btn-sm mt-1 me-2',
                            disabled=True,
                        ),
                        html.Button(
                            'Download Domains CSV',
                            id='user-apk-btn-csv-domains',
                            className='btn btn-outline-secondary btn-sm mt-1',
                            disabled=True,
                        ),
                    ] if ENABLE_CSV_EXPORT else [
                        html.Div(id='user-apk-btn-csv-urls'),
                        html.Div(id='user-apk-btn-csv-subdomains'),
                        html.Div(id='user-apk-btn-csv-domains'),
                    ]
                ),
            ], className='mb-2'),
            html.Div([
                dcc.Loading(
                    id="user-apk-loading",
                    type="default",
                    children=html.Div(id="user-apk-loading-output")
                ),

                html.Div(id="user-apk-results")
            ], style={'minHeight': '100px'})
        ], width=12, lg=8)
    ]),
    dcc.Store(id='user-apk-upload-store', data=[]),
    dcc.Store(id='user-apk-highlight-config-store', data=[]),
    dcc.Store(id='user-apk-feature-info-store', data={}),
    dcc.Store(id='user-apk-session-id-store', data=None),
    # CSV export stores — hold csv_export dicts between analysis and download callbacks
    dcc.Store(id='user-apk-csv-store-urls'),
    dcc.Store(id='user-apk-csv-store-subdomains'),
    dcc.Store(id='user-apk-csv-store-domains'),
    # dcc.Download components — invisible; activated by download callbacks
    dcc.Download(id='user-apk-download-csv-urls'),
    dcc.Download(id='user-apk-download-csv-subdomains'),
    dcc.Download(id='user-apk-download-csv-domains'),
], fluid=True)
