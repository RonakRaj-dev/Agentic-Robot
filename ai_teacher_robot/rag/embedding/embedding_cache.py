import sqlite3
import json
import os
from typing import List, Optional
from loguru import logger

class EmbeddingCache:
    """SQLite-backed cache for text embeddings to prevent redundant LLM/local model calls."""
    def __init__(self, cache_db_path: str = "state/embedding_cache.db") -> None:
        self.cache_db_path = cache_db_path
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.cache_db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        try:
            self.conn = sqlite3.connect(self.cache_db_path)
            self.cursor = self.conn.cursor()
            self.cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS embeddings (
                    text_hash TEXT PRIMARY KEY,
                    vector TEXT
                )
                """
            )
            self.conn.commit()
            logger.info(f"Initialized embedding cache at {self.cache_db_path}")
        except Exception as e:
            logger.warning(f"Failed to initialize SQLite cache database: {e}. Falling back to in-memory dictionary.")
            self.conn = None
            self._memory_cache = {}

    def _get_hash(self, text: str) -> str:
        import hashlib
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def get_embedding(self, text: str) -> Optional[List[float]]:
        text_hash = self._get_hash(text)
        if self.conn:
            try:
                self.cursor.execute("SELECT vector FROM embeddings WHERE text_hash = ?", (text_hash,))
                row = self.cursor.fetchone()
                if row:
                    return json.loads(row[0])
            except Exception as e:
                logger.error(f"Error querying embedding cache: {e}")
        else:
            return self._memory_cache.get(text_hash)
        return None

    def add_embedding(self, text: str, vector: List[float]) -> None:
        text_hash = self._get_hash(text)
        vector_str = json.dumps(vector)
        if self.conn:
            try:
                self.cursor.execute(
                    "INSERT OR REPLACE INTO embeddings (text_hash, vector) VALUES (?, ?)",
                    (text_hash, vector_str),
                )
                self.conn.commit()
            except Exception as e:
                logger.error(f"Error inserting into embedding cache: {e}")
        else:
            self._memory_cache[text_hash] = vector

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None
