from typing import Any, Annotated, Optional
from bson.objectid import ObjectId
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, PlainSerializer
from .document import PyObjectId

class CurriculumChunk(BaseModel):
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)
    
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    document_id: PyObjectId
    chunk_text: str
    page_number: int
    chapter: str
    topic: Optional[str] = "General"
    embedding_id: Optional[str] = None # Maps to Qdrant vector point ID

    def to_mongo(self) -> dict[str, Any]:
        data = self.model_dump(by_alias=True, exclude_none=True)
        if "_id" in data and isinstance(data["_id"], str):
            data["_id"] = ObjectId(data["_id"])
        if "document_id" in data and isinstance(data["document_id"], str):
            data["document_id"] = ObjectId(data["document_id"])
        return data

    @classmethod
    def from_mongo(cls, data: dict[str, Any] | None):
        if not data:
            return None
        data_copy = dict(data)
        if "_id" in data_copy and "id" not in data_copy:
            data_copy["id"] = data_copy["_id"]
        return cls.model_validate(data_copy)
