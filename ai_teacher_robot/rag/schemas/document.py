from datetime import datetime
from typing import Any, Annotated, Optional, List
from bson.objectid import ObjectId
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, PlainSerializer

def validate_object_id(value: Any) -> ObjectId:
    if isinstance(value, ObjectId):
        return value
    if isinstance(value, str) and ObjectId.is_valid(value):
        return ObjectId(value)
    raise ValueError("Invalid ObjectId")

PyObjectId = Annotated[
    ObjectId,
    BeforeValidator(validate_object_id),
    PlainSerializer(func=str, return_type=str),
]

class EmbeddedSource(BaseModel):
    pdf_path: str
    author: Optional[str] = None
    edition: Optional[str] = None
    publisher: Optional[str] = None

class EmbeddedChunk(BaseModel):
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)
    id: PyObjectId = Field(default_factory=ObjectId, alias="id")
    chunk_text: str
    page_number: int
    chapter: str
    topic: Optional[str] = "General"
    embedding_id: Optional[str] = None

class CurriculumDocument(BaseModel):
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)
    
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    title: str
    subject: str
    class_level: str = Field(..., alias="class")
    board: str
    chapter: str
    uploaded_by: str = "Teacher"
    curriculum_version: Optional[str] = "2026.1"
    book_title: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Embedded Document Pattern components
    source: Optional[EmbeddedSource] = None
    chunks: List[EmbeddedChunk] = Field(default_factory=list)
    toc: List[dict[str, Any]] = Field(default_factory=list)
    run_metadata: Optional[dict[str, Any]] = None

    def to_mongo(self) -> dict[str, Any]:
        data = self.model_dump(by_alias=True, exclude_none=True)
        if "_id" in data and isinstance(data["_id"], str):
            data["_id"] = ObjectId(data["_id"])
        if "source" in data and data["source"]:
            if "_id" in data["source"] and isinstance(data["source"]["_id"], str):
                data["source"]["_id"] = ObjectId(data["source"]["_id"])
        if "chunks" in data:
            for ch in data["chunks"]:
                if "id" in ch and isinstance(ch["id"], str):
                    ch["id"] = ObjectId(ch["id"])
                if "document_id" in ch and isinstance(ch["document_id"], str):
                    ch["document_id"] = ObjectId(ch["document_id"])
        return data

    @classmethod
    def from_mongo(cls, data: dict[str, Any] | None):
        if not data:
            return None
        data_copy = dict(data)
        if "_id" in data_copy and "id" not in data_copy:
            data_copy["id"] = data_copy["_id"]
        return cls.model_validate(data_copy)

class CurriculumSource(BaseModel):
    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)
    
    id: Optional[PyObjectId] = Field(default=None, alias="_id") # Same as document_id
    pdf_path: str
    author: Optional[str] = None
    edition: Optional[str] = None
    publisher: Optional[str] = None

    def to_mongo(self) -> dict[str, Any]:
        data = self.model_dump(by_alias=True, exclude_none=True)
        if "_id" in data and isinstance(data["_id"], str):
            data["_id"] = ObjectId(data["_id"])
        return data

    @classmethod
    def from_mongo(cls, data: dict[str, Any] | None):
        if not data:
            return None
        data_copy = dict(data)
        if "_id" in data_copy and "id" not in data_copy:
            data_copy["id"] = data_copy["_id"]
        return cls.model_validate(data_copy)
