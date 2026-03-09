import sqlite3
import os

os.makedirs("memories/sql", exist_ok=True)
conn = sqlite3.connect("memories/sql/memory_index.db")
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

conn.commit()