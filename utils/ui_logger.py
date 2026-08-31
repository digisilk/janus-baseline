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
import logging
from io import StringIO
import uuid
import threading

class UILogger:
    # Class variable to store loggers for different sessions
    _loggers = {}
    
    @classmethod
    def get_logger(cls, session_id):
        """Get or create a logger for a specific session"""
        if session_id not in cls._loggers:
            cls._loggers[session_id] = cls._create_new_logger()
            
            # Clean up old sessions (keep only the most recent 100)
            if len(cls._loggers) > 100:
                oldest_session = list(cls._loggers.keys())[0]
                del cls._loggers[oldest_session]
                
        return cls._loggers[session_id]
    
    @classmethod
    def _create_new_logger(cls):
        """Create a new logger instance"""
        log_capture = StringIO()
        ch = logging.StreamHandler(log_capture)
        ch.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        
        new_logger = logging.getLogger(f'UILogger-{uuid.uuid4()}')
        new_logger.setLevel(logging.INFO)
        new_logger.addHandler(ch)
        
        return {
            'logger': new_logger,
            'capture': log_capture
        }
    
    @classmethod
    def get_logs(cls, session_id=None):
        """Get logs for a specific session"""
        if session_id and session_id in cls._loggers:
            return cls._loggers[session_id]['capture'].getvalue()
        elif session_id is None and hasattr(cls, 'default_capture'):
            return cls.default_capture.getvalue()
        return "No logs available for this session."

ui_logger = UILogger()
ui_logger.default_capture = StringIO()
ui_logger.logger = logging.getLogger('UILogger-Default')
handler = logging.StreamHandler(ui_logger.default_capture)
handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
ui_logger.logger.addHandler(handler)

_process_registry = {}

def register_process(session_id, process):
    """Register a process for a specific session"""
    _process_registry[session_id] = process

def get_process(session_id):
    """Get the process for a specific session"""
    return _process_registry.get(session_id)

def should_cancel(session_id=None):
    """Check if the current process should be cancelled"""
    # If no session ID provided, nothing to cancel
    if session_id is None:
        return False
    
    # Get the registered thread for this session
    registered_thread = _process_registry.get(session_id)
    
    # The current thread that's executing this code
    current_thread = threading.current_thread()
    
    # If no thread is registered, don't cancel - this prevents false cancellations during initialisation
    if registered_thread is None:
        # Log that we're not cancelling despite no registered thread
        if session_id in UILogger._loggers:
            UILogger._loggers[session_id]['logger'].info(
                f"Continuing execution despite no registered thread. "
                f"current={current_thread.name}/{current_thread.ident}, registered=None"
            )
        return False
    
    # Check if the current thread is the registered thread
    result = registered_thread != current_thread
    
    # Log the comparison if we're cancelling
    if result and session_id in UILogger._loggers:
        UILogger._loggers[session_id]['logger'].info(
            f"Should cancel check: result={result}, "
            f"current={current_thread.name}/{current_thread.ident}, "
            f"registered={registered_thread.name}/{registered_thread.ident}"
        )
    
    return result

def cancel_process(session_id):
    """Mark a process for cancellation by removing it from the registry"""
    if session_id in _process_registry:
        # Log the cancellation
        if session_id in UILogger._loggers:
            registered_thread = _process_registry.get(session_id)
            thread_info = "None" if registered_thread is None else f"{registered_thread.name}/{registered_thread.ident}"
            UILogger._loggers[session_id]['logger'].info(f"Process marked for cancellation: {thread_info}")
        
        # Simply remove from registry to trigger cancellation
        del _process_registry[session_id]
        return True
    return False
