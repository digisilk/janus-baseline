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
from dash import Input, Output, State
from dash.exceptions import PreventUpdate
import flask
from flask_login import login_user, logout_user
import os
import json



# TODO: Basic login for demo - replace with proper auth later
def get_credentials():
    # Default login details
    default_credentials = {
    "admin": "humanities_informatics_2025",
    "elisa": "janus_25_androzoo",
    "ashwin": "janus_25_androzoo", 
    "researcher": "janus_andro_analysis25",
    "analyst": "janus_andro_analysis25"
    }
    
    # Check for credentials file
    credentials_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'credentials.json')
    if os.path.exists(credentials_file):
        try:
            with open(credentials_file, 'r') as f:
                return json.load(f)
        except:
            return default_credentials
    return default_credentials

def register_callbacks(app, User):
    @app.callback(
        [Output("url", "pathname"),
         Output("login-error", "children")],
        [Input("login-button", "n_clicks")],
        [State("username-input", "value"),
         State("password-input", "value")]
    )
    def login(n_clicks, username, password):
        if n_clicks is None:
            raise PreventUpdate
            
        credentials = get_credentials()
        
        if username in credentials and credentials[username] == password:
            user = User(username)
            login_user(user)
            return "/historical-connectivity", ""
        else:
            return "/login", "Invalid username or password"
            
    @app.server.route('/logout')
    def logout():
        logout_user()
        return flask.redirect('/') 