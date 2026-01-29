"""
Database Connection Manager
Simple SQLite with WAL mode - no queues needed
"""
import sqlite3
import threading
from contextlib import contextmanager
from config import Config
from utils.logger import logger

class DatabaseManager:
    """Simple SQLite connection manager"""
    
    def __init__(self):
        self.db_path = Config.DB_PATH
        self._local = threading.local()
        logger.info(f"Database initialized: {self.db_path}")
    
    def get_connection(self):
        """Get thread-local connection"""
        if not hasattr(self._local, 'connection'):
            self._local.connection = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                timeout=30.0
            )
            self._local.connection.row_factory = sqlite3.Row
        return self._local.connection
    
    @contextmanager
    def get_cursor(self):
        """Context manager for cursor"""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise
        finally:
            cursor.close()
    
    def close(self):
        """Close connection"""
        if hasattr(self._local, 'connection'):
            self._local.connection.close()
            del self._local.connection

def init_database(conn):
    """Initialize database with schema"""
    from database.schema import init_schema
    init_schema(conn)
    logger.info("Database schema initialized")
