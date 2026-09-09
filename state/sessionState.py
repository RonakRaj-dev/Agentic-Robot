import os
import time
import datetime
import threading
from typing import Any, Dict, List, Optional
from loguru import logger

try:
    from pymongo import MongoClient
    from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError, DuplicateKeyError
    MOTOR_AVAILABLE = True
except ImportError:
    MongoClient = None
    ConnectionFailure = Exception
    ServerSelectionTimeoutError = Exception
    DuplicateKeyError = Exception
    MOTOR_AVAILABLE = False

class SessionStateManager:
    """
    Manages conversation history and locks with automatic in-memory fallbacks when MongoDB is down.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if not cls._instance:
                cls._instance = super(SessionStateManager, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, mongo_uri: Optional[str] = None, redis_host: Optional[str] = None, redis_port: Optional[int] = None) -> None:
        if self._initialized:
            return

        self.mongo_uri = mongo_uri or os.environ.get("MONGO_URI", "mongodb://localhost:27017")
        self.mongo_client = None
        self.db = None

        # In-memory storage for fallbacks
        self._in_memory_history = {}  # session_id -> list of message dicts
        self._in_memory_states = {}   # session_id -> state doc dict
        self._in_memory_locks = {}    # lock_name -> expire_at datetime
        
        self.use_in_memory_mongo = False
        self.use_in_memory_redis = True  # Always fallback for redis (V1 legacy compat)

        # Setup MongoDB Connection
        if MongoClient is None:
            logger.warning("pymongo package is not installed. Using in-memory fallback.")
            self.use_in_memory_mongo = True
        else:
            try:
                self.mongo_client = MongoClient(self.mongo_uri, serverSelectionTimeoutMS=2000)
                # Quick server ping check
                self.mongo_client.admin.command('ping')
                self.db = self.mongo_client["classroom_teaching_robot"]
                logger.info("MongoDB client connected successfully.")
                
                # Setup TTL index for locks collection
                self.db["locks"].create_index("expire_at", expireAfterSeconds=0)
            except Exception as e:
                logger.warning(f"MongoDB connection failed ({e}). Falling back to local in-memory storage.")
                self.mongo_client = None
                self.db = None
                self.use_in_memory_mongo = True

        self._initialized = True

    def save_message(self, session_id: str, sender: str, content: str) -> None:
        """Saves a message to persistent storage."""
        if self.use_in_memory_mongo:
            if session_id not in self._in_memory_history:
                self._in_memory_history[session_id] = []
            self._in_memory_history[session_id].append({
                "sender": sender,
                "content": content,
                "timestamp": time.time()
            })
            return

        history_col = self.db["chat_history"]
        history_col.insert_one({
            "session_id": session_id,
            "sender": sender,
            "content": content,
            "timestamp": time.time()
        })

    def get_history(self, session_id: str) -> List[Dict[str, Any]]:
        """Retrieves history for the current session."""
        if self.use_in_memory_mongo:
            history = self._in_memory_history.get(session_id, [])
            sorted_hist = sorted(history, key=lambda x: x["timestamp"])
            return [{"sender": doc["sender"], "content": doc["content"], "timestamp": doc["timestamp"]} for doc in sorted_hist]

        history_col = self.db["chat_history"]
        cursor = history_col.find({"session_id": session_id}).sort("timestamp", 1)
        return [{"sender": doc["sender"], "content": doc["content"], "timestamp": doc["timestamp"]} for doc in cursor]

    def save_execution_state(self, session_id: str, agent: str, status: str, execution_time: float, error: Optional[str] = None) -> None:
        """Saves session execution steps for auditing/analytics."""
        state_data = {
            "agent": agent,
            "status": status,
            "execution_time": execution_time,
            "error": error,
            "timestamp": time.time()
        }

        if self.use_in_memory_mongo:
            if session_id not in self._in_memory_states:
                self._in_memory_states[session_id] = {
                    "session_id": session_id,
                    "steps": [],
                    "last_updated": time.time()
                }
            self._in_memory_states[session_id]["steps"].append(state_data)
            self._in_memory_states[session_id]["last_updated"] = time.time()
            return

        # Save to MongoDB for historical tracking
        states_col = self.db["session_states"]
        states_col.update_one(
            {"session_id": session_id},
            {"$push": {"steps": state_data}, "$set": {"last_updated": time.time()}},
            upsert=True
        )

    def get_execution_state(self, session_id: str) -> Dict[str, Any]:
        """Retrieves execution details for a given session."""
        if self.use_in_memory_mongo:
            doc = self._in_memory_states.get(session_id)
            if doc and "steps" in doc:
                return {step["agent"]: step for step in doc["steps"]}
            return {}

        states_col = self.db["session_states"]
        doc = states_col.find_one({"session_id": session_id})
        if doc and "steps" in doc:
            return {step["agent"]: step for step in doc["steps"]}
        return {}

    def acquire_lock(self, lock_name: str, expire_seconds: int = 10) -> bool:
        """Acquires a message processing lock using MongoDB TTL index or in-memory map."""
        now = datetime.datetime.now(datetime.UTC)
        if self.use_in_memory_mongo:
            # Clean up expired locks
            expired = [k for k, v in self._in_memory_locks.items() if v < now]
            for k in expired:
                del self._in_memory_locks[k]

            if lock_name in self._in_memory_locks:
                return False

            self._in_memory_locks[lock_name] = now + datetime.timedelta(seconds=expire_seconds)
            return True

        try:
            # Clean up any expired locks immediately just in case TTL index hasn't run yet
            self.db["locks"].delete_many({"expire_at": {"$lt": now}})
            
            expire_at = now + datetime.timedelta(seconds=expire_seconds)
            self.db["locks"].insert_one({
                "_id": lock_name,
                "expire_at": expire_at
            })
            return True
        except DuplicateKeyError:
            return False
        except Exception as e:
            logger.warning(f"Lock acquisition error: {e}")
            return False

    def release_lock(self, lock_name: str) -> None:
        """Releases a lock."""
        if self.use_in_memory_mongo:
            if lock_name in self._in_memory_locks:
                del self._in_memory_locks[lock_name]
            return

        try:
            self.db["locks"].delete_one({"_id": lock_name})
        except Exception as e:
            logger.warning(f"Lock release error: {e}")
