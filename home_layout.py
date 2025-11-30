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
from dash import html, dcc
import dash_bootstrap_components as dbc

layout = dbc.Container([
    dbc.Row([
        dbc.Col([
            html.H1("THE DIGITAL SILK ROAD", className="text-center my-4 display-3"),
            html.Div([
                html.Span("数字丝绸之路", className="mx-2"),
                html.Span("•", className="mx-2"),
                html.Span("Цифровой Шелковый Путь", className="mx-2"),
                html.Span("•", className="mx-2"),
                html.Span("ဒီဂျစ်တယ် ပိုးလမ်းမ", className="mx-2"),
            ], className="text-center h3 mb-3"),
            html.H4("An exploration of China's Digital Expansion in Borderland Regions",
                    className="text-center mb-5 text-muted"),
        ], width=12)
    ]),

    dbc.Row([
        dbc.Col(html.Img(src="assets/digisilk_countries.png", className="img-fluid rounded shadow"), width=3),
        dbc.Col([
            html.H2("Janus:", className="mb-3"),
            html.P(
                "Janus is a software tool developed by DIGISILK to help understand the evolution of mobile applications over time. It focuses on changes in backend connectivity across different versions of apps. Janus helps us understand how apps evolve in response to various factors, including changes in ownership, investment, market conditions, sanctions and regional policies.",
                className="text-justify mb-4"
            ),
            html.H2("Research Context of the Digisilk Project", className="mb-3"),
            html.P(
                "In 2013, China launched the Belt and Road Initiative (BRI), a set of policies and mostly infrastructural investments in countries along a loosely reimagined Silk Road. An increasingly discussed part of the BRI is the Digital Silk Road (DSR) which, at least on paper, is focused on investments in the digital field in BRI countries, from building physical infrastructures to localizing digital services and devices. This project studies the implementation of the DSR from the bottom up in China and three neighboring countries: Cambodia, Myanmar and Kazakhstan. It starts from a simple question whose answer is very unclear: What is the Digital Silk Road, exactly? What projects does it consist of and how are they coordinated? Who is investing in it, and how much? How are these projects connected with the goals of the Chinese State, and directly supported by it, and how do they deviate, following instead the goals of the corporations or people who materialize them? What specific consequences do they have on the daily lives of people who live in the three countries we focus on, as well as on the countries' economies and societies?",
                className="text-justify"
            ),
        ], width=9),
    ], className="mb-5 bg-light p-4 rounded"),

    dbc.Row([
        dbc.Col(html.Img(src="assets/sponsors.png", className="img-fluid rounded shadow"), width=3),
        dbc.Col([
            html.H3("About the Project", className="mb-3"),
            html.P(
                "Our team employs field research based on qualitative methods, digital methods, and document analysis to understand the emergence of the Digital Silk Road from the ground-up and from the comparative perspective of businesses, governments and ordinary people in the four countries. In China, where policies, finances, devices, online platforms and apps originate, we look at the strategies of tech companies, especially SME, to succeed in the markets of the three countries, and explore how they are linked to a general DSR strategy and how they diverge from it. In Kazakhstan, Myanmar and Cambodia, we focus on traders and small markets as well as people's use of Chinese tech. At the heart of our exploration are ethnographic methods, which we triangulate with document analysis and digital methods to bring a multi-layered perspective on the ground-up implementation of the DSR.",
                className="text-justify"
            ),
            html.P("Digisilk is an ERC-funded project, find out more at digisilk.eu. Copyright 2025 Elisa Oreglia. The Code is licensed under the Apache License, Version 2.0.", className="font-italic mt-3"),
        ], width=9),
    ], className="mb-5 bg-light p-4 rounded"),

    dbc.Row(dbc.Col(html.Hr())),

    dbc.Row([
        dbc.Col(html.P("© 2024 Janus. All rights reserved.", className="text-center text-muted")),
    ], className="mt-4"),
], fluid=True, className="px-4 py-3")