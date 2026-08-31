"""
Configuration file

Edit the settings below to configure the application.
Can use environment variables if deployed on server.
"""

import os

# ============================================================================
# API Configuration
# ============================================================================

# CONFIGURATION SCENARIOS:
#
# Scenario 1: User Testing/Demo (Current Setup)
# - ANDROZOO_API_KEY = ""
# - SHOW_API_KEY_INPUT = False
# - OVERRIDE_API_KEY_FROM_UI = True
# Result: Users don't see API key input, shared key is used automatically
#
# Scenario 2: Personal Use 
# - ANDROZOO_API_KEY = None
# - SHOW_API_KEY_INPUT = True  
# - OVERRIDE_API_KEY_FROM_UI = False
# Result: Users must input their own API key in the UI
#
# Scenario 3: Production with Environment Variables
# - ANDROZOO_API_KEY = None
# - SHOW_API_KEY_INPUT = False
# - Set ANDROZOO_API_KEY environment variable
# Result: Uses environment variable, no UI input needed

# AndroZoo API Key
# Option 1: Set it directly here for shared/demo use
ANDROZOO_API_KEY = ""  # API key for testing

# Option 2: Leave as None to require user input or environment variable
#ANDROZOO_API_KEY = None

# UI Control: Show/hide the API key input field
SHOW_API_KEY_INPUT = False # Set to True if users should input their own API keys

# Whether to always use the configured API key (ignoring UI input)
# This should match SHOW_API_KEY_INPUT for logical consistency
OVERRIDE_API_KEY_FROM_UI = False # Set to False if you want users to input their own keys

# ============================================================================
# Processing Configuration
# ============================================================================

# Parser Selection
# Options: "digisilk", "androguard", or None (let user choose)
FORCE_PARSER = "digisilk"  # Set to None to show parser selection in UI

# Version Limits  
MAX_VERSIONS = 12  # Maximum versions to process (set to None for no limit)

# Core Processing
FORCE_SINGLE_CORE = True  # Set to False to allow multi-core processing

# ============================================================================
# Testing/Demo Mode
# ============================================================================

# Enable this for user testing sessions - locks all settings
TESTING_MODE = False  # Set to True to override all settings for consistent testing

# ============================================================================
# UI Configuration  
# ============================================================================

# Show/hide UI controls based on the above settings
# These are calculated automatically, but you can override them

SHOW_PARSER_SELECTION = False  # Set to True to show parser selection dropdown
SHOW_VERSION_CONTROL = False  # Set to True to show version number input
SHOW_CORE_CONTROL = False  # Set to True to show core count slider

# ---------------------------------------------------------------------------
# CSV Export Feature
# ---------------------------------------------------------------------------
# Set to True to show CSV download buttons in all analysis tabs.
# Set to False to hide them (e.g. in locked demo/testing mode).
# In TESTING_MODE, this is automatically forced to False.
ENABLE_CSV_EXPORT = True

# ============================================================================
# Backend
# ============================================================================

# Download and processing timeouts
PROCESSING_TIMEOUT = 1000  # seconds
DOWNLOAD_RETRY_CYCLES = 4
MAX_DOWNLOAD_RETRIES = 20

# Database settings
MAX_DB_CONNECTIONS = 20

# ============================================================================
# Helper Functions 
# ============================================================================

def get_api_key():
    """Get API key from config or environment"""
    # First priority: Configured API key
    if ANDROZOO_API_KEY:
        return ANDROZOO_API_KEY
    
    # Second priority: Environment variable
    env_key = os.environ.get('ANDROZOO_API_KEY')
    if env_key:
        return env_key
    
    # No API key configured - this should only happen if SHOW_API_KEY_INPUT=True
    # In that case, the UI input will be used
    return None


def get_effective_config():
    """Get the effective configuration with all overrides applied"""
    config = {
        'api_key': get_api_key(),
        'override_api_key': OVERRIDE_API_KEY_FROM_UI,
        'force_parser': FORCE_PARSER,
        'max_versions': MAX_VERSIONS,
        'force_single_core': FORCE_SINGLE_CORE,
        'testing_mode': TESTING_MODE,
        'show_api_key_input': SHOW_API_KEY_INPUT and not TESTING_MODE,
        'show_parser_selection': SHOW_PARSER_SELECTION and not FORCE_PARSER and not TESTING_MODE,
        'show_version_control': SHOW_VERSION_CONTROL and not MAX_VERSIONS and not TESTING_MODE,
        'show_core_control': SHOW_CORE_CONTROL and not FORCE_SINGLE_CORE and not TESTING_MODE,
        'enable_csv_export': ENABLE_CSV_EXPORT and not TESTING_MODE,
    }
    
    # Testing mode overrides everything
    if TESTING_MODE:
        config.update({
            'force_parser': 'digisilk',
            'max_versions': 4,
            'force_single_core': True,
            'show_api_key_input': False,
            'show_parser_selection': False,
            'show_version_control': False,
            'show_core_control': False,
            'enable_csv_export': False,
        })
    
    return config 