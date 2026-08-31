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
"""
This module provides utilities for managing concurrency and resources.
As it is a research project, we expect few users but are trying to run with minimal costs.
Helps prevent too many analyses from running at the same time, which can overload the server.
"""
import os
import time
import logging

logger = logging.getLogger(__name__)

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    logger.warning("psutil not available, using fallback concurrency settings")

SESSION_TIMEOUT = 1800  # in seconds

def get_max_concurrent_users():
    """Determine the maximum number of concurrent users based on system resources"""
    try:
        if not HAS_PSUTIL:
            return 5  # Default if psutil not available
        
        # Get system resources
        cpu_count = os.cpu_count() or 4  # Default to 4 if cannot determine
        available_memory_gb = psutil.virtual_memory().available / (1024 * 1024 * 1024)

        # The formula is a simple estimate - adjust based on actual usage
        max_by_cpu = max(1, cpu_count - 1)
        max_by_memory = max(1, int(available_memory_gb / 1.5))
        
        # Use the more limiting factor
        suggested_max = min(max_by_cpu, max_by_memory)
        
        # Cap at reasonable limits
        return max(1, min(20, suggested_max))  # Min 1, Max 20
    except Exception as e:
        logger.error(f"Error determining max concurrent users: {e}")
        # If there's any error, use 5
        return 5

# Global variables for concurrency control
MAX_CONCURRENT_USERS = get_max_concurrent_users()  # Dynamic based on system resources
active_sessions = {}  # Dictionary to track active analysis sessions

def clean_stale_sessions():
    """Remove sessions that have been active for too long"""
    current_time = time.time()
    stale_sessions = []
    
    for session_id, session_data in active_sessions.items():
        if current_time - session_data['start_time'] > SESSION_TIMEOUT:
            stale_sessions.append(session_id)
    
    for session_id in stale_sessions:
        logger.info(f"Removing stale session: {session_id}")
        del active_sessions[session_id]
    
    if stale_sessions:
        logger.info(f"Removed {len(stale_sessions)} stale sessions. Active sessions: {len(active_sessions)}")

def register_session(session_id, data):
    """Register a new analysis session"""
    active_sessions[session_id] = {
        'start_time': time.time(),
        **data
    }
    logger.info(f"Registered session {session_id}. Current active sessions: {len(active_sessions)}")
    return True

def remove_session(session_id):
    """Remove a session when it's complete"""
    if session_id in active_sessions:
        del active_sessions[session_id]
        logger.info(f"Removed session {session_id}. Current active sessions: {len(active_sessions)}")
        return True
    return False

def has_capacity():
    """Check if the server has capacity for more sessions"""
    return len(active_sessions) < MAX_CONCURRENT_USERS
