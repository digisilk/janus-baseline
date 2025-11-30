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
import os
import zipfile
import struct
import re
from collections import defaultdict
import requests
import pandas as pd
import plotly.graph_objects as go
import sqlite3
import dash_bootstrap_components as dbc
from dash import html

class DEXParser:
    def __init__(self, data):
        self.data = data
        self.header = {}
        self.string_ids = []
        self.strings = []

    def parse(self):
        self.parse_header()
        self.parse_string_ids()
        self.parse_strings()

    def parse_header(self):
        header_data = self.data[:112]
        self.header = {
            'string_ids_size': struct.unpack('<I', header_data[56:60])[0],
            'string_ids_off': struct.unpack('<I', header_data[60:64])[0],
        }

    def parse_string_ids(self):
        offset = self.header['string_ids_off']
        for i in range(self.header['string_ids_size']):
            string_data_off = struct.unpack('<I', self.data[offset:offset + 4])[0]
            self.string_ids.append(string_data_off)
            offset += 4

    def parse_strings(self):
        for string_data_off in self.string_ids:
            size, offset = self.read_uleb128(string_data_off)
            string_data = self.data[offset:offset + size].decode('utf-8', errors='replace')
            self.strings.append(string_data)

    def read_uleb128(self, offset):
        result = 0
        shift = 0
        size = 0
        while True:
            byte = self.data[offset]
            offset += 1
            size += 1
            result |= (byte & 0x7f) << shift
            if byte & 0x80 == 0:
                break
            shift += 7
        return result, offset

def extract_apk_dex_files(apk_path):
    """Extract DEX files from APK"""
    dex_files = []
    with zipfile.ZipFile(apk_path, 'r') as z:
        for filename in z.namelist():
            if filename.endswith('.dex'):
                dex_data = z.read(filename)
                dex_files.append(dex_data)
    return dex_files
