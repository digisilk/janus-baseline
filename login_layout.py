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

layout = html.Div([
    # Add Font Awesome for icons
    html.Link(
        rel="stylesheet",
        href="https://use.fontawesome.com/releases/v5.15.4/css/all.css",
        integrity="sha384-DyZ88mC6Up2uqS4h/KRgHuoeGwBcD4Ng9SiP4dIRy0EXTlnuz47vAwmeGwVChigm",
        crossOrigin="anonymous"
    ),
    dbc.Container([
        dbc.Row([
            dbc.Col([
                html.Div([
                    # Project logo/name
                    html.Div([
                        html.H1("Janus", className="text-primary text-center mb-1"),
                        html.H5("A Social Science-Oriented App Analysis Suite", className="text-center text-muted mb-4"),
                        # Digisilk logo
                        html.Div([
                            html.Img(src="/assets/digisilk_countries.png", className="img-fluid", style={"maxHeight": "100px"}),
                        ], className="text-center mb-4"),
                    ], className="mb-4"),
                    
                    html.Div([
                        dbc.Card([
                            dbc.CardHeader([
                                html.H4([html.I(className="fas fa-lock me-2"), "Sign In"], className="text-center m-0")
                            ], className="bg-primary text-white"),
                            dbc.CardBody([
                                dbc.Form([
                                    html.Div([
                                        dbc.Label("Username", html_for="username-input", className="mb-2"),
                                        dbc.InputGroup([
                                            dbc.InputGroupText(html.I(className="fas fa-user")),
                                            dbc.Input(
                                                type="text",
                                                id="username-input",
                                                placeholder="Enter username",
                                            ),
                                        ], className="mb-3"),
                                    ]),
                                    html.Div([
                                        dbc.Label("Password", html_for="password-input", className="mb-2"),
                                        dbc.InputGroup([
                                            dbc.InputGroupText(html.I(className="fas fa-key")),
                                            dbc.Input(
                                                type="password",
                                                id="password-input",
                                                placeholder="Enter password",
                                            ),
                                        ], className="mb-3"),
                                    ]),
                                    dbc.Button(
                                        [html.I(className="fas fa-sign-in-alt me-2"), "Login"],
                                        id="login-button",
                                        color="primary",
                                        className="mt-3 w-100",
                                    ),
                                    html.Div(id="login-error", className="text-danger mt-2")
                                ])
                            ])
                        ], className="shadow")
                    ], className="d-flex justify-content-center"),
                    
                    # Sponsors
                    html.Div([
                        html.Img(src="/assets/sponsors.png", className="img-fluid mt-4", style={"maxHeight": "50px"}),
                    ], className="text-center mt-4"),
                ], className="p-3 p-md-5")
            ], width=12, sm=10, md=8, lg=6, xl=4, className="mx-auto")
        ], className="align-items-center", style={"minHeight": "100vh"})
    ], fluid=True)
]) 