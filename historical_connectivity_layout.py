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
from dash import dcc, html
import dash_bootstrap_components as dbc
from datetime import datetime

ascii_logo = """
     ██  █████  ███    ██ ██    ██ ███████ 
     ██ ██   ██ ████   ██ ██    ██ ██      
     ██ ███████ ██ ██  ██ ██    ██ ███████ 
██   ██ ██   ██ ██  ██ ██ ██    ██      ██ 
 █████  ██   ██ ██   ████  ██████  ███████ """

def create_highlight_options(preset_configs):
    options = []
    for category, patterns in preset_configs.items():
        category_options = []
        for pattern, color in patterns.items():
            label = html.Span([
                html.Span(f"{category}: ", style={"fontWeight": "bold"}),
                html.Span(pattern, style={"color": color})
            ])
            category_options.append({"label": label, "value": f"{category}:{pattern}"})
        options.extend(category_options)
    options.append({"label": "Custom", "value": "custom"})
    return options

preset_configs = {
    "Global Cloud & Infrastructure": {
        "Western Cloud (AWS, Google Cloud, Azure)": {"terms": ["amazonaws.com", "cloud.google", "azure.com", "cloudflare.com", "digitalocean"], "color": "#FF9900"},
        "Asian Cloud (Aliyun, Tencent Cloud, Huawei Cloud)": {"terms": ["aliyun", "alicloud", "tencentcloud", "huaweicloud", "naver.com", "line.me"], "color": "#4285F4"},
        "Russian Cloud (Yandex Cloud, Mail.ru Cloud)": {"terms": ["cloud.yandex", "mail.ru", "sbercloud"], "color": "#CC0000"},
        "CDN Global (Akamai, Fastly, Cloudfront)": {"terms": ["akamai", "fastly.net", "cdn.jsdelivr", "cdnjs", "cloudfront.net", "cdn.aliyun"], "color": "#2C3E50"},
    },
    "Global Payment Systems": {
        "Western (Stripe, PayPal, Square)": {"terms": ["stripe.com", "paypal.com", "square.com", "checkout.com"], "color": "#8E44AD"},
        "China (Alipay, WeChat Pay, UnionPay)": {"terms": ["alipay.com", "weixin.qq.com", "unionpay.com"], "color": "#E74C3C"},
        "Russia (YooMoney, QIWI, SberPay)": {"terms": ["yoomoney.ru", "qiwi.com", "sberbank.ru"], "color": "#CC0000"},
        "India (Paytm, RazorPay, PhonePe)": {"terms": ["paytm.com", "razorpay.com", "phonepe.com", "bharatpe.com"], "color": "#F39C12"},
        "LATAM (MercadoPago, PagBank, Nubank)": {"terms": ["mercadopago", "pagbank", "pagseguro", "nubank"], "color": "#27AE60"},
        "Africa (M-Pesa, Paystack, Flutterwave)": {"terms": ["mpesa", "paystack.com", "flutterwave", "pesapal"], "color": "#16A085"},
        "SEA (GrabPay, GoPay, OVO)": {"terms": ["grab.com", "gopay", "ovo.id", "dana.id", "shopeepay"], "color": "#D35400"},
    },
    "Regional Tech Giants": {
        "China (Alibaba/Lazada/AliExpress, Tencent, ByteDance/TikTok)": {"terms": ["alibaba", "tencent", "baidu", "bytedance", "qq.com", "weibo.com", "douyin", "lazada", "aliexpress", "meituan"], "color": "#E74C3C"},
        "Russia (Yandex, Mail.ru, VK)": {"terms": ["yandex", "mail.ru", "vk.com", "sber.ru"], "color": "#CC0000"},
        "Korea (Naver, Kakao, Coupang)": {"terms": ["naver.com", "kakao", "coupang", "line.me"], "color": "#3498DB"},
        "Japan (Yahoo JP, Rakuten, Line)": {"terms": ["yahoo.co.jp", "rakuten", "line.me", "mercari.jp"], "color": "#9B59B6"},
        "India (Flipkart, Jio, Ola, Swiggy)": {"terms": ["flipkart", "jio.com", "ola.in", "zomato", "swiggy"], "color": "#F39C12"},
        "SEA (Grab, Gojek, Sea/Shopee)": {"terms": ["grab.com", "gojek", "sea.com", "shopee"], "color": "#D35400"},
    },
    "Social & Messaging": {
        "Global (Facebook, Twitter, Instagram)": {"terms": ["facebook.com", "twitter.com", "instagram", "telegram"], "color": "#3498DB"},
        "China (WeChat, QQ, Weibo, Douyin/TikTok)": {"terms": ["weixin", "qq.com", "weibo.com", "douyin.com", "tiktok.com", "xiaohongshu"], "color": "#E74C3C"},
        "Russia (VK, OK.ru, Telegram)": {"terms": ["vk.com", "ok.ru", "telegram.org", "mail.ru"], "color": "#CC0000"},
        "Korea/Japan (Line, Kakao, Band, Mixi)": {"terms": ["line.me", "kakao.com", "band.us", "mixi.jp"], "color": "#9B59B6"},
        "MENA (Moj, YallaLive, Tango)": {"terms": ["moj.io", "snackvideo", "yalla.live", "tango.me"], "color": "#16A085"},
    },
    "Analytics & Tracking": {
        "Global (Google Analytics, Firebase, Mixpanel)": {"terms": ["google-analytics", "firebase-analytics", "amplitude.com", "mixpanel"], "color": "#E49307"},
        "China (Umeng, TalkingData, Sensors Data)": {"terms": ["umeng", "sensors.data", "talkingdata"], "color": "#E74C3C"},
        "Russia (Yandex Metrika, Mail.ru)": {"terms": ["yandex.ru/metrika", "mail.ru/counter"], "color": "#CC0000"},
        "Regional (Kakao, Line)": {"terms": ["kakao.ad", "line-apps.com"], "color": "#3498DB"},
        "Ad Networks (AdMob, Unity, AppLovin)": {"terms": ["admob", "unity3d.com", "applovin", "mopub", "adcolony", "inmobi.com"], "color": "#9B59B6"},
    },
    "Top Level Domains": {
        "Commercial TLDs (.com, .org, .net)": {"terms": [".com", ".org", ".net", ".io"], "color": "#3498DB"},
        "China TLDs (.cn, .hk, .mo)": {"terms": [".cn", ".hk", ".mo"], "color": "#E74C3C"},
        "Russia TLDs (.ru, .su, .рф)": {"terms": [".ru", ".su", ".рф"], "color": "#CC0000"},
        "Asia Pacific TLDs (.jp, .kr, .sg, .in)": {"terms": [".jp", ".kr", ".sg", ".in", ".id", ".my", ".th", ".vn"], "color": "#27AE60"},
        "Europe TLDs (.eu, .de, .uk, .fr)": {"terms": [".eu", ".de", ".uk", ".fr", ".nl", ".es"], "color": "#9B59B6"}
    },
}

# Define a color palette for the color picker
color_palette = [
    "#4285F4", "#DB4437", "#F4B400", "#0F9D58",  # Google colors
    "#1877F2", "#FF9900", "#00A4EF", "#7CBB00",  # Corporate blues and accents
    "#FF0000", "#00FF00", "#0000FF", "#FFFF00",  # Primary colors
    "#FF69B4", "#800080", "#FFA500", "#008000",  # Vibrant colors
]

layout = dbc.Container([
    # ASCII art and sponsors at the very top
    dbc.Row(dbc.Col(html.Pre(ascii_logo, style={'font-family': 'monospace', 'color': 'blue'}))),
    dbc.Row(dbc.Col(html.Img(src="/assets/sponsors.png",
                             style={'height': '71px', 'display': 'inline-block', 'margin-bottom': '0px',
                                    'margin-top': '0px'}))),
    # Add the script for the custom JavaScript
    html.Script(src='/assets/custom.js'),
    
    # Main content row - responsive layout
    dbc.Row([
        dbc.Col([
            dbc.Form([
                # AndroZoo API Key input
                html.H5("AndroZoo API Key", id="api-key-heading", className="mt-4 mb-2"),
                dbc.InputGroup([
                    dbc.Input(
                        id="api-key",
                        type="password",
                        placeholder="Enter your AndroZoo API key",
                        debounce=True,
                        valid=False,
                        invalid=False
                    ),
                    dbc.InputGroupText(
                        id="api-key-status",
                        children="⏳",
                        style={"minWidth": "40px", "justifyContent": "center"}
                    )
                ], id="api-key-input-group", className="mb-2"),
                html.Small(
                    id="api-key-help-text",
                    children="Required for downloading APKs from AndroZoo database.",
                    className="text-muted",
                    style={"display": "block", "marginBottom": "15px"}
                ),
                
                # Search section heading
                html.H5("Search for Package", className="mt-4 mb-2"),
                
                # Main search section
                dcc.Dropdown(
                    id="package-list-dropdown",
                    options=[],
                    value=None,
                    placeholder="Enter package name (e.g., com.duolingo)",
                    searchable=True,
                    clearable=True,
                    className="mb-3"
                ),
                dcc.Store(id="selected-package-store"),
                
                # Submit button
                dbc.Button("Analyse App", id="submit-button", color="primary", size="lg", className="mb-4 w-100"),
                html.Div(id="error-message", className="text-danger"),

                # Advanced settings button
                dbc.Button(
                    "Advanced Settings ▼",
                    id="settings-collapse-button",
                    color="secondary",
                    className="mb-3 w-100",
                ),
                
                # Wrap existing settings in Collapse
                dbc.Collapse(
                    dbc.Card(
                        dbc.CardBody([
                            # Original date settings
                            html.H5("Date Range", className="mb-3"),
                            dbc.Label("Start Date"),
                            dbc.Input(id="start-date", type="date", value="2013-01-01"),
                            html.Small(
                                "Leave as default (2013) to analyse from earliest available data.",
                                className="text-muted",
                                style={"display": "block", "marginBottom": "15px"}
                            ),
                            dbc.Label("End Date"),
                            dbc.Input(id="end-date", type="date", value=datetime.now().strftime("%Y-%m-%d")),
                            html.Small(
                                "Leave as default (today) to include latest available data.",
                                className="text-muted",
                                style={"display": "block", "marginBottom": "15px"}
                            ),
                    
                            # DESIRED VERSIONS INPUT
                            html.H5("App Versions", className="mb-3 mt-4"),
                            html.Div([
                                dbc.Label("Number of Versions"),
                                dbc.Input(
                                    id="desired-versions", 
                                    type="number", 
                                    value=4,
                                    min=1,
                                    max=4,  # This will be set by config
                                    step=1,
                                    debounce=True,
                                    valid=True,
                                    invalid=False
                                ),
                                html.Small(
                                    id="versions-help-text",
                                    children="Number of app versions to analyze (older versions first). Max: 4",
                                    className="text-muted",
                                    style={"display": "block", "marginBottom": "15px"}
                                ),
                            ]),
                            
                            html.H5("Highlight Connections With Colors", className="mb-3 mt-4"),
                            html.P("Choose what types of connections to highlight in the analysis (from the preset menu, or add your own):", className="text-muted small"),
                            dbc.Alert([
                                html.I(className="fas fa-info-circle me-2"),
                                "Changes to highlight settings require resubmitting the analysis to take effect."
                            ], color="info", className="mb-3", style={"padding": "8px 12px", "fontSize": "0.875rem"}),
                            
                            # Rest of the original highlight settings
                            dbc.Accordion([
                                dbc.AccordionItem([
                                    dbc.Checklist(
                                        options=[
                                            {"label": name, "value": name} 
                                            for name in items.keys()
                                        ],
                                        id=f"highlight-checklist-{category.lower().replace(' ', '-')}",
                                        className="gap-2",
                                        value=[]  # Initialize with empty selection
                                    )
                                ], title=category)
                                for category, items in preset_configs.items()
                            ], id="highlight-categories", start_collapsed=True),
                            
                            # Custom Highlight Section
                            dbc.Card([
                                dbc.CardHeader("Add Your Own Highlight Connections", className="fw-bold"),
                                dbc.CardBody([
                                    dbc.Label("What to look for:", className="mb-1"),
                                    dbc.Input(
                                        id="highlight-terms",
                                        type="text",
                                        placeholder="Enter words or domains (comma-separated)",
                                        className="mb-2"
                                    ),
                                    html.Div(id="highlight-feedback", className="text-success small mb-2"),
                                    dbc.Label("Choose a color:", className="mb-1"),
                                    dbc.RadioItems(
                                        id="highlight-color-picker",
                                        options=[{
                                            "label": html.Div(style={
                                                "backgroundColor": color,
                                                "width": "20px",
                                                "height": "20px",
                                                "border": "1px solid #dee2e6",
                                                "borderRadius": "4px",
                                                "display": "inline-block"
                                            }),
                                            "value": color
                                        } for color in color_palette],
                                        value=color_palette[0],
                                        inline=True,
                                        className="mb-2"
                                    ),
                                    dbc.Button(
                                        "Add Highlight",
                                        id="add-highlight",
                                        color="primary",
                                        size="sm",
                                        className="mt-2"
                                    ),
                                ])
                            ], className="mt-3 mb-3"),
                            
                            # Active Highlights Display
                            dbc.Card([
                                dbc.CardHeader("Active Highlights"),
                                dbc.CardBody(
                                    html.Div(id="highlight-list")
                                )
                            ]),
                            
                            # NUMBER OF CORES SLIDER - Currently hidden and hardcoded to 1
                            html.Div([
                                dbc.Label("Number of Cores"),
                                dcc.Slider(
                                    id="num-cores-slider",
                                    min=1,
                                    max=4,
                                    step=1,
                                    value=1,
                                    marks={i: str(i) for i in range(1, 5)},
                                ),
                            ], style={'display': 'none'}),
                        ]),
                    ),
                    id="settings-collapse",
                    is_open=False,  # Hidden by default
                ),
                
                # Server capacity indicator
                html.Div([
                    html.Hr(className="my-2"),
                    html.Label("Server Capacity:", className="mt-2"),
                    dbc.Progress(
                        id="historical-server-capacity-indicator",
                        value=0,  # Will be updated via callback
                        color="success",
                        style={"height": "20px"},
                        className="mt-1 mb-1"
                    ),
                    html.Div(id="historical-server-capacity-text", className="text-muted small")
                ], className="mt-3")
            ])
        ], width=12, lg=4, className="mb-4"),
        dbc.Col([
            # Service Notice at the top with original styling
            dbc.Alert([
                html.H5([html.I(className="fas fa-info-circle mr-2"), " Service Notice"]),
                html.P([
                    "This service connects to AndroZoo to fetch and analyse APK data. ",
                    "Processing times may vary and occasional delays are possible. ",
                    "If analysis is slow or fails, please be patient and try again later. ",
                    "We appreciate your understanding."
                ])
            ], color="secondary", className="mb-4"),

            # Analysis Status section
            html.H4("Status"),
            dbc.Alert(
                "Waiting for app selection...",
                id="historical-status-message",
                color="secondary",
                className="mb-3"
            ),
            dbc.Alert(
                "",
                id="historical-error-message",
                color="danger",
                className="mb-3",
                style={"display": "none"},
                is_open=False
            ),
            html.Div([
                dbc.Spinner(
                    html.Div(id="historical-spinner-container", style={"height": "50px"}),
                    id="historical-spinner",
                    color="primary",
                    type="border"
                ),
            ], id="historical-spinner-wrapper", style={"display": "none"}),
            
            # Analysis Log section (hidden)
            html.Div([
                html.H4("Analysis Log"),
                html.Pre(
                    id='progress-historical-connectivity', 
                    style={
                        'whiteSpace': 'pre-wrap', 
                        'wordBreak': 'break-word', 
                        'maxHeight': '300px', 
                        'overflowY': 'scroll',
                        'backgroundColor': '#f8f9fa',
                        'padding': '10px',
                        'border': '1px solid #ddd',
                        'borderRadius': '5px'
                    }
                ),
                dcc.Interval(id='progress-interval', interval=1000, n_intervals=0),
            ], style={'display': 'none'}),
            
            html.H4("Results"),
            html.Div([
                dcc.Loading(
                    id="loading-1",
                    type="default",
                    children=html.Div(id="loading-output")
                ),
                html.Div(id="results-historical-connectivity")
            ], style={'minHeight': '100px'})  # minimum height for loading indicator
        ], width=12, lg=8)
    ]),
    dcc.Store(id='historical-connectivity-progress'),
    dcc.Store(id='highlight-config-store'),
    dcc.Store(id='session-id-store'),
    # Add hidden inputs for backend processing
    dcc.Input(id="parser-selection", style={'display': 'none'}),
], fluid=True)
