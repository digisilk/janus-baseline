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
import sqlite3
import threading
import logging

logger = logging.getLogger(__name__)

class SQLiteConnectionPool:
    """A simple connection pool for SQLite"""
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        """Singleton pattern to ensure only one pool exists"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(SQLiteConnectionPool, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self, db_path, max_connections=10):
        """Initialise the connection pool if not already initialised"""
        if self._initialized:
            return
            
        self.db_path = db_path
        self.max_connections = max_connections
        self._connections = []
        self._in_use = {}
        self._lock = threading.Lock()
        self._initialized = True
        logger.info(f"Initialised SQLite connection pool for {db_path} with max {max_connections} connections")
    
    def get_connection(self):
        """Get a connection from the pool or create a new one if needed"""
        thread_id = threading.get_ident()
        
        # If this thread already has a connection, return it
        if thread_id in self._in_use:
            return self._in_use[thread_id]
            
        with self._lock:
            # Try to get an existing connection
            if self._connections:
                conn = self._connections.pop()
                self._in_use[thread_id] = conn
                return conn
                
            # Create a new connection if under the limit
            if len(self._in_use) < self.max_connections:
                try:
                    conn = sqlite3.connect(self.db_path, check_same_thread=False)
                    # Enable foreign keys
                    conn.execute("PRAGMA foreign_keys = ON")
                    # Set busy timeout to avoid database locked errors
                    conn.execute("PRAGMA busy_timeout = 30000")  # 30 seconds
                    self._in_use[thread_id] = conn
                    return conn
                except Exception as e:
                    logger.error(f"Error creating database connection: {str(e)}")
                    raise
            
            # If we reach here, we've hit the connection limit
            logger.warning(f"Connection pool exhausted (max: {self.max_connections})")
            raise Exception("Database connection pool exhausted")
    
    def release_connection(self, conn=None):
        """Release a connection back to the pool"""
        thread_id = threading.get_ident()
        
        with self._lock:
            # If no connection specified, try to get the one for this thread
            if conn is None and thread_id in self._in_use:
                conn = self._in_use[thread_id]
                
            # If we found a connection, release it
            if thread_id in self._in_use:
                # Return connection to the pool
                self._connections.append(conn)
                # Remove from in-use dict
                del self._in_use[thread_id]
    
    def close_all(self):
        """Close all connections in the pool"""
        with self._lock:
            # Close all available connections
            for conn in self._connections:
                try:
                    conn.close()
                except Exception as e:
                    logger.error(f"Error closing connection: {str(e)}")
            
            # Close all in-use connections
            for thread_id, conn in self._in_use.items():
                try:
                    conn.close()
                except Exception as e:
                    logger.error(f"Error closing in-use connection: {str(e)}")
            
            # Clear the collections
            self._connections = []
            self._in_use = {}
            
            logger.info("Closed all database connections")

_pool = None

def initialize_pool(db_path, max_connections=10):
    """Initialise the global connection pool"""
    global _pool
    _pool = SQLiteConnectionPool(db_path, max_connections)
    return _pool

def get_connection():
    """Get a connection from the global pool"""
    if _pool is None:
        raise Exception("Database connection pool not initialised")
    return _pool.get_connection()

def release_connection(conn=None):
    """Release a connection back to the global pool"""
    if _pool is not None:
        _pool.release_connection(conn)

def close_all_connections():
    """Close all connections in the global pool"""
    if _pool is not None:
        _pool.close_all()

def execute_query(query, params=(), fetch_all=False, fetch_one=False, commit=False):
    """
    Execute a query using a connection from the pool and automatically release it
    
    Args:
        query: SQL query to execute
        params: Parameters for the query
        fetch_all: Whether to return all results
        fetch_one: Whether to return one result
        commit: Whether to commit the transaction
        
    Returns:
        Query results if fetch_all or fetch_one is True, otherwise None
    """
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        
        result = None
        if fetch_all:
            result = cursor.fetchall()
        elif fetch_one:
            result = cursor.fetchone()
            
        if commit:
            conn.commit()
            
        return result
    except Exception as e:
        logger.error(f"Error executing query: {str(e)}")
        if conn and commit:
            conn.rollback()
        raise
    finally:
        release_connection(conn)
