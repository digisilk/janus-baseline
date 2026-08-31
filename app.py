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
import dash
import dash_bootstrap_components as dbc
import os
from flask_login import LoginManager, UserMixin
import secrets

# Get environment variables with defaults
debug_mode = os.environ.get('DASH_DEBUG_MODE', 'True').lower() == 'true'

# Initialize the Dash app
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.JOURNAL], title="JANUS")
server = app.server
app.config.suppress_callback_exceptions = True

# Set a secret key for Flask session management
# In production, you should use a more secure method to generate and store this key
server.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(16))

# Configure Flask-Login
login_manager = LoginManager()
login_manager.init_app(server)
login_manager.login_view = '/login'

# User class for Flask-Login
class User(UserMixin):
    def __init__(self, username):
        self.id = username

# User loader callback
@login_manager.user_loader
def load_user(username):
    return User(username)
