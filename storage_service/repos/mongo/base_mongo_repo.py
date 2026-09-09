from __future__ import annotations
from datetime import datetime, timezone
from typing import Generic, Optional, TypeVar, Type
from bson.objectid import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from core.exceptions import DuplicateDocumentError, RepositoryError
from core.logging import get_logger
from db.models.base import MongoBase, PyObjectId
from repos.base import AbstractRepository
from utils.oid_utils import to_oid
from .client import get_database

T = TypeVar("T", bound=MongoBase)
logger = get_logger(__name__)


class BaseMongoRepository(AbstractRepository[T], Generic[T]):
    """Base class for all MongoDB repositories.

    Subclasses set ``collection_name`` and ``model_class``.  All writes
    go through ``self._col`` (the motor collection).  Services talk to
    repositories through the intent-revealing methods defined here and
    on subclasses — they never reach into ``_col`` or ``_db`` directly.
    """

    collection_name: str
    model_class: Type[T]

    def __init__(self, db: Optional[AsyncIOMotorDatabase] = None) -> None:
        self._db = db if db is not None else get_database()

    @property
    def _col(self):
        return self._db[self.collection_name]

    def _oid(self, value: str | PyObjectId) -> ObjectId:
        """Coerce str / PyObjectId into a bson.ObjectId (single source of truth)."""
        return to_oid(value)

    # ── atomic writes ────────────────────────────────────────────────

    async def insert(self, document: T) -> PyObjectId:
        data = document.to_mongo()
        try:
            result = await self._col.insert_one(data)
            logger.debug(
                "inserted", collection=self.collection_name, id=str(result.inserted_id)
            )
            return result.inserted_id
        except Exception as exc:
            if "duplicate key" in str(exc).lower():
                raise DuplicateDocumentError(self.collection_name, str(exc)) from exc
            raise RepositoryError(f"Insert failed: {exc}") from exc

    async def insert_many(self, documents: list[T]) -> list[PyObjectId]:
        if not documents:
            return []
        try:
            result = await self._col.insert_many(
                [doc.to_mongo() for doc in documents], ordered=False
            )
            return result.inserted_ids
        except Exception as exc:
            raise RepositoryError(f"insert_many failed: {exc}") from exc

    async def find_by_id(self, doc_id: str | PyObjectId) -> Optional[T]:
        try:
            raw = await self._col.find_one({"_id": self._oid(doc_id)})
        except Exception as exc:
            raise RepositoryError(f"find_by_id failed: {exc}") from exc
        return self._deserialise(raw) if raw else None

    async def find_many(self, filter_: dict, limit: int = 100) -> list[T]:
        try:
            cursor = self._col.find(filter_).limit(limit)
            return [self._deserialise(doc) async for doc in cursor]
        except Exception as exc:
            raise RepositoryError(f"find_many failed: {exc}") from exc

    async def update(self, doc_id: str | PyObjectId, updates: dict) -> bool:
        """``$set`` update on a single document by ``_id``.

        ``updated_at`` is stamped automatically ONLY when the model
        actually has that field — checked via ``model_fields`` so we
        don't write a stray ``updated_at`` onto models like
        ``PipelineRun`` / ``IngestionJob`` / ``Exam`` that don't carry it.
        """
        try:
            payload = dict(updates)
            if "updated_at" in self.model_class.model_fields:
                payload.setdefault("updated_at", datetime.now(timezone.utc))
            result = await self._col.update_one(
                {"_id": self._oid(doc_id)}, {"$set": payload}
            )
            return result.matched_count > 0
        except Exception as exc:
            raise RepositoryError(f"update failed: {exc}") from exc

    async def delete(self, doc_id: str | PyObjectId) -> bool:
        try:
            result = await self._col.delete_one({"_id": self._oid(doc_id)})
            return result.deleted_count > 0
        except Exception as exc:
            raise RepositoryError(f"delete failed: {exc}") from exc

    async def count(self, filter_: dict) -> int:
        try:
            return await self._col.count_documents(filter_)
        except Exception as exc:
            raise RepositoryError(f"count failed: {exc}") from exc

    async def exists(self, filter_: dict) -> bool:
        try:
            return await self._col.count_documents(filter_, limit=1) > 0
        except Exception as exc:
            raise RepositoryError(f"exists failed: {exc}") from exc

    async def increment_fields(
        self, doc_id: str | PyObjectId, increments: dict[str, int],
    ) -> bool:
        """Atomically ``$inc`` one or more numeric fields on a document.

        Used by services that need to bump progress counters without
        reaching into ``self._col`` themselves.  Skips the call when
        ``increments`` is empty (no-op).
        """
        inc = {k: v for k, v in increments.items() if v}
        if not inc:
            return True
        try:
            result = await self._col.update_one(
                {"_id": self._oid(doc_id)}, {"$inc": inc},
            )
            return result.matched_count > 0
        except Exception as exc:
            raise RepositoryError(f"increment_fields failed: {exc}") from exc

    def _deserialise(self, raw: dict) -> T:
        return self.model_class.model_validate(raw)
