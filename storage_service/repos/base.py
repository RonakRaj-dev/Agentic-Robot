from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Optional
from db.models.base import MongoBase, PyObjectId

T = TypeVar("T", bound=MongoBase)


class AbstractRepository(ABC, Generic[T]):
    """Read/write contract for a single MongoDB collection."""

    @abstractmethod
    async def exists(self, filter_: dict) -> bool: ...
    @abstractmethod
    async def insert(self, document: T) -> PyObjectId: ...
    @abstractmethod
    async def find_by_id(self, doc_id: PyObjectId | str) -> Optional[T]: ...
    @abstractmethod
    async def find_many(self, filter_: dict, limit: int = 100) -> list[T]: ...
    @abstractmethod
    async def update(self, doc_id: str, updates: dict) -> bool: ...
    @abstractmethod
    async def delete(self, doc_id: str) -> bool: ...
    @abstractmethod
    async def insert_many(self, documents: list[T]) -> list[PyObjectId]: ...
    @abstractmethod
    async def count(self, filter_: dict) -> int: ...
