import sqlite3
import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Any


"""
User Profile Manager Module

This module provides functionality to manage user profiles in a SQLite database.
It handles user data such as personality traits, preferences, relationship scores,
and memory counts, supporting multi-threaded access.
"""
class UserProfileManager:
    """
    Manager class for handling user profiles using SQLite database.

    This class provides methods to create, retrieve, and update user profiles,
    storing data like personality traits, preferences, and interaction history.
    It uses thread-local connections to ensure thread safety.
    """
    def __init__(self, profile_db_path: str):
        """
        Initialize the UserProfileManager.

        Args:
            profile_db_path (str): Path to the SQLite database file.
        """
        self.profile_db_path = Path(profile_db_path)
        self.local = threading.local()


    def _get_conn(self):
        """
        Get or create a thread-local SQLite connection.

        Returns:
            sqlite3.Connection: The thread-local database connection.
        """
        if not hasattr(self.local, 'conn') or self.local.conn is None:
            print(f"[UserProfileManager] Creating SQLite connection in thread {threading.get_ident()}")
            conn = sqlite3.connect(str(self.profile_db_path), check_same_thread=True)
            conn.execute("PRAGMA foreign_keys = ON")
            self._create_table(conn)
            self.local.conn = conn
            print(f"[UserProfileManager] Thread ID for DB: {threading.get_ident()}")
        return self.local.conn



    def _create_table(self, conn):
        """
        Create the profiles table if it doesn't exist.

        This method sets up the database schema for storing user profiles,
        including fields for user ID, timestamps, memory counts, traits, scores, and preferences.

        Args:
            conn (sqlite3.Connection): The database connection to use.
        """
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS profiles (
            user_id TEXT PRIMARY KEY,
            first_seen TEXT NOT NULL,
            total_memories INTEGER DEFAULT 0,
            personality_traits TEXT DEFAULT '{}',
            relationship_score REAL DEFAULT 0.0,
            last_seen TEXT NOT NULL,
            preferences TEXT DEFAULT '{}'
        )
        """
        conn.execute(create_table_sql)
        conn.commit()


    def get_user_profile(self, user_id: str) -> Dict[str, Any]:
        """
        Retrieve or create a user profile by user ID.

        If the profile doesn't exist, a new one is created with default values.

        Args:
            user_id (str): The unique identifier for the user.

        Returns:
            Dict[str, Any]: A dictionary containing the user's profile data.
        """
        conn = self._get_conn()
        cursor = conn.execute("SELECT * FROM profiles WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            personality_traits = json.loads(row[3]) if row[3] else {}
            preferences = json.loads(row[6]) if row[6] else {}
            return {
                "user_id": row[0],
                "first_seen": row[1],
                "total_memories": row[2],
                "personality_traits": personality_traits,
                "relationship_score": row[4],
                "last_seen": row[5],
                "preferences": preferences
            }
        else:
            now = datetime.now().isoformat()
            conn.execute("""
                INSERT INTO profiles (user_id, first_seen, last_seen, total_memories, personality_traits, relationship_score, preferences)
                VALUES (?, ?, ?, 0, '{}', 0.0, '{}')
            """, (user_id, now, now))
            conn.commit()
            return {
                "user_id": user_id,
                "first_seen": now,
                "last_seen": now,
                "total_memories": 0,
                "personality_traits": {},
                "relationship_score": 0.0,
                "preferences": {}
            }

    def __del__(self):
        """
        Clean up by closing the thread-local database connection on object destruction.
        """
        if hasattr(self.local, 'conn') and self.local.conn:
            self.local.conn.close()

    def update_user_profile(self, user_id: str,
                            personality_trait: str = None, preference: Dict[str, Any] = None,
                            last_seen: str = None) -> None:
        """
        Update a user's profile with new personality traits, preferences, or last seen time.

        Args:
            user_id (str): The unique identifier for the user.
            personality_trait (str, optional): A personality trait to increment. Defaults to None.
            preference (Dict[str, Any], optional): A dictionary of preferences to update. Defaults to None.
            last_seen (str, optional): ISO formatted timestamp for last seen. Defaults to current time.
        """
        profile = self.get_user_profile(user_id)

        new_last_seen = last_seen if last_seen else datetime.now().isoformat()

        if personality_trait:
            personality_traits = profile.get("personality_traits", {})
            personality_traits[personality_trait] = personality_traits.get(personality_trait, 0) + 1
            new_personality_traits = json.dumps(personality_traits)
        else:
            new_personality_traits = json.dumps(profile.get("personality_traits", {}))

        if preference:
            profile_preferences = profile.get("preferences", {})
            profile_preferences.update(preference)
            new_preferences = json.dumps(profile_preferences)
        else:
            new_preferences = json.dumps(profile.get("preferences", {}))

        conn = self._get_conn()
        conn.execute("""
            UPDATE profiles
            SET last_seen = ?, personality_traits = ?, preferences = ?
            WHERE user_id = ?
        """, (new_last_seen, new_personality_traits, new_preferences, user_id))
        conn.commit()

    def _update_user_profile(self, user_id: str, content: str, memory_type: str = "semantic"):
        """
        Update user profile based on memory content and type.

        This method increments memory count and adjusts relationship score based on emotional content.

        Args:
            user_id (str): The unique identifier for the user.
            content (str): The content of the memory.
            memory_type (str, optional): Type of memory ('semantic' or 'episodic'). Defaults to 'semantic'.
        """
        profile = self.get_user_profile(user_id)

        new_last_seen = datetime.now().isoformat()
        new_total_memories = profile["total_memories"] + 1
        new_relationship_score = profile["relationship_score"]

        if memory_type == "episodic":
            emotional_words = {
                "happy": 0.8, "excited": 0.7, "love": 0.9,
                "sad": -0.6, "angry": -0.8, "hate": -0.9
            }

            for word, valence in emotional_words.items():
                if word in content.lower():
                    new_relationship_score += valence * 0.1
                    break

        conn = self._get_conn()
        conn.execute("""
            UPDATE profiles
            SET last_seen = ?, total_memories = ?, relationship_score = ?
            WHERE user_id = ?
        """, (new_last_seen, new_total_memories, new_relationship_score, user_id))
        conn.commit()