import os
import asyncio
from typing import List, Dict, Any, Optional
from loguru import logger
from bson.objectid import ObjectId
from dotenv import load_dotenv

load_dotenv()

try:
    from motor.motor_asyncio import AsyncIOMotorClient
    from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
    MOTOR_AVAILABLE = True
except ImportError:
    AsyncIOMotorClient = None
    ConnectionFailure = Exception
    ServerSelectionTimeoutError = Exception
    MOTOR_AVAILABLE = False


class InMemoryCursor:
    def __init__(self, data: List[Dict[str, Any]]):
        self.data = data
        self.index = 0

    def sort(self, key: str, direction: int = 1):
        self.data = sorted(self.data, key=lambda x: x.get(key, 0), reverse=(direction == -1))
        return self

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.index < len(self.data):
            val = self.data[self.index]
            self.index += 1
            return val
        raise StopAsyncIteration

    async def to_list(self, length: int):
        return self.data[:length]


class InMemoryCollection:
    def __init__(self, db, name: str):
        self.db = db
        self.name = name
        self.docs: List[Dict[str, Any]] = []

    async def insert_one(self, doc: Dict[str, Any]):
        doc_copy = dict(doc)
        if "_id" not in doc_copy:
            doc_copy["_id"] = ObjectId()
        self.docs.append(doc_copy)
        class InsertResult:
            inserted_id = doc_copy["_id"]
        return InsertResult()

    async def insert_many(self, docs: List[Dict[str, Any]]):
        inserted_ids = []
        for doc in docs:
            doc_copy = dict(doc)
            if "_id" not in doc_copy:
                doc_copy["_id"] = ObjectId()
            self.docs.append(doc_copy)
            inserted_ids.append(doc_copy["_id"])
        return inserted_ids

    def _match_filter(self, doc: Dict[str, Any], filt: Optional[Dict[str, Any]]) -> bool:
        if not filt:
            return True
        for k, v in filt.items():
            if k == "$or":
                matched_any = False
                for sub_f in v:
                    if self._match_filter(doc, sub_f):
                        matched_any = True
                        break
                if not matched_any:
                    return False
            else:
                doc_val = doc.get(k)
                if str(doc_val) != str(v):
                    return False
        return True

    async def find_one(self, filt: Optional[Dict[str, Any]]):
        for doc in self.docs:
            if self._match_filter(doc, filt):
                return doc
        return None

    def find(self, filt: Optional[Dict[str, Any]] = None):
        matched = []
        for doc in self.docs:
            if self._match_filter(doc, filt):
                matched.append(doc)
        return InMemoryCursor(matched)

    async def update_one(self, filt: Dict[str, Any], update: Dict[str, Any], upsert: bool = False):
        matched_doc = None
        for doc in self.docs:
            if self._match_filter(doc, filt):
                matched_doc = doc
                break
        
        if not matched_doc:
            if upsert:
                new_doc = {}
                for k, v in filt.items():
                    if k != "$or":
                        new_doc[k] = v
                
                if "$set" in update:
                    new_doc.update(update["$set"])
                if "$push" in update:
                    for pk, pv in update["$push"].items():
                        if isinstance(pv, dict) and "$each" in pv:
                            new_doc[pk] = list(pv["$each"])
                        else:
                            new_doc[pk] = [pv]
                
                if "_id" not in new_doc:
                    new_doc["_id"] = ObjectId()
                self.docs.append(new_doc)
                class UpdateResult:
                    matched_count = 0
                    modified_count = 1
                    upserted_id = new_doc["_id"]
                return UpdateResult()
            else:
                class UpdateResult:
                    matched_count = 0
                    modified_count = 0
                    upserted_id = None
                return UpdateResult()
        
        if "$set" in update:
            matched_doc.update(update["$set"])
        if "$push" in update:
            for pk, pv in update["$push"].items():
                if pk not in matched_doc or not isinstance(matched_doc[pk], list):
                    matched_doc[pk] = []
                if isinstance(pv, dict) and "$each" in pv:
                    matched_doc[pk].extend(pv["$each"])
                else:
                    matched_doc[pk].append(pv)
                
        class UpdateResult:
            matched_count = 1
            modified_count = 1
            upserted_id = None
        return UpdateResult()

    async def delete_one(self, filt: Dict[str, Any]):
        for idx, doc in enumerate(self.docs):
            if self._match_filter(doc, filt):
                self.docs.pop(idx)
                class DeleteResult:
                    deleted_count = 1
                return DeleteResult()
        class DeleteResult:
            deleted_count = 0
        return DeleteResult()

    async def delete_many(self, filt: Dict[str, Any]):
        initial = len(self.docs)
        self.docs = [doc for doc in self.docs if not self._match_filter(doc, filt)]
        deleted = initial - len(self.docs)
        class DeleteResult:
            deleted_count = deleted
        return DeleteResult()

    async def distinct(self, field: str, filt: Optional[Dict[str, Any]] = None):
        values = set()
        for doc in self.docs:
            if self._match_filter(doc, filt):
                val = doc.get(field)
                if val is not None:
                    values.add(val)
        return list(values)

    async def create_index(self, keys, **kwargs):
        pass


class InMemoryMongoDatabase:
    def __init__(self):
        self.collections = {}

    def __getitem__(self, name: str):
        if name not in self.collections:
            self.collections[name] = InMemoryCollection(self, name)
        return self.collections[name]


class MongoDatabaseManager:
    _instance = None
    _lock = asyncio.Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(MongoDatabaseManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self.mongo_uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
        self.db_name = os.environ.get("MONGO_DB_NAME", "SiliconRag")
        self.client = None
        self.db = None
        self.use_in_memory = False
        self._in_memory_db = InMemoryMongoDatabase()
        self._initialized = True

    async def get_db(self):
        try:
            current_loop = asyncio.get_running_loop()
            active_uri = os.environ.get("MONGO_URI") or self.mongo_uri
            active_db_name = os.environ.get("MONGO_DB_NAME") or self.db_name

            # Reset connection if loop changed or if mongo_uri/db_name changed
            if self.client is not None and (getattr(self, "_bound_loop", None) != current_loop or getattr(self, "_active_uri", None) != active_uri):
                logger.info("Event loop or MongoDB URI changed. Resetting AsyncIOMotorClient connection.")
                self.client = None
                self.db = None

            if self.db is not None:
                return self.db
            
            if not MOTOR_AVAILABLE:
                logger.warning("motor package is not installed. Using in-memory fallback database.")
                self.db = self._in_memory_db
                self.use_in_memory = True
                self._bound_loop = current_loop
                return self.db
            
            try:
                logger.info(f"Connecting to MongoDB URI: {active_uri} (db: {active_db_name})")
                self.client = AsyncIOMotorClient(
                    active_uri,
                    serverSelectionTimeoutMS=10000,
                    connectTimeoutMS=10000,
                    socketTimeoutMS=10000,
                    retryWrites=True,
                    retryReads=True,
                    minPoolSize=1,
                    maxPoolSize=50
                )
                # Test connection
                await self.client.admin.command('ping')
                self.db = self.client[active_db_name]
                self._bound_loop = current_loop
                self._active_uri = active_uri
                self.use_in_memory = False
                logger.info(f"Successfully connected to MongoDB database: {active_db_name}")
                return self.db
            except Exception as e:
                logger.warning(f"Failed to connect to MongoDB ({e}). Falling back to local in-memory database mock.")
                self.client = None
                self.db = self._in_memory_db
                self._bound_loop = current_loop
                self.use_in_memory = True
                return self.db
        except Exception as outer_e:
            logger.error(f"Outer exception in get_db: {outer_e}")
            return self._in_memory_db

    async def close(self) -> None:
        """Close MongoDB connection client gracefully."""
        if self.client is not None:
            logger.info("Closing MongoDB AsyncIOMotorClient connections.")
            self.client.close()
            self.client = None
            self.db = None


# Singleton helper
db_manager = MongoDatabaseManager()
