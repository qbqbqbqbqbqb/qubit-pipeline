import sqlite3
import tempfile
import os


def test_create_metadata_table_creates_table():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "memory_index.db")
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS memory_index (
            id TEXT PRIMARY KEY,
            timestamp TEXT,
            user_id TEXT,
            type TEXT,
            collection TEXT
        )
        """)

        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='memory_index'")
        result = cur.fetchone()
        assert result is not None
        assert result[0] == 'memory_index'

        conn.close()


def test_create_metadata_table_creates_indexes():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "memory_index.db")
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS memory_index (
            id TEXT PRIMARY KEY,
            timestamp TEXT,
            user_id TEXT,
            type TEXT,
            collection TEXT
        )
        """)

        cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_timestamp
        ON memory_index(timestamp)
        """)

        cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_memory_type_timestamp
        ON memory_index(type, timestamp DESC)
        """)

        cur.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_timestamp'")
        result = cur.fetchone()
        assert result is not None

        cur.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_memory_type_timestamp'")
        result = cur.fetchone()
        assert result is not None

        conn.close()


def test_create_metadata_table_accepts_insert():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "memory_index.db")
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS memory_index (
            id TEXT PRIMARY KEY,
            timestamp TEXT,
            user_id TEXT,
            type TEXT,
            collection TEXT
        )
        """)

        cur.execute(
            "INSERT INTO memory_index (id, timestamp, user_id, type, collection) VALUES (?, ?, ?, ?, ?)",
            ("test-id", "2024-01-01", "user1", "chat", "reflections")
        )
        conn.commit()

        cur.execute("SELECT * FROM memory_index WHERE id = 'test-id'")
        result = cur.fetchone()
        assert result == ("test-id", "2024-01-01", "user1", "chat", "reflections")

        conn.close()