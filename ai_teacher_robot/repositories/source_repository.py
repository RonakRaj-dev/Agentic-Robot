from typing import Optional, Dict, Any
from bson.objectid import ObjectId
from loguru import logger
from ai_teacher_robot.rag.schemas.document import CurriculumSource
from ai_teacher_robot.repositories.db_client import db_manager

class SourceRepository:
    """Manages the curriculum_sources (embedded under curriculum_documents) in MongoDB."""
    def __init__(self) -> None:
        self.collection_name = "curriculum_documents"

    async def _get_collection(self):
        db = await db_manager.get_db()
        return db[self.collection_name]

    async def insert_source(self, source: CurriculumSource) -> str:
        col = await self._get_collection()
        source_dict = source.to_mongo()
        
        # Ensure doc_id is set
        doc_id = source_dict.pop("_id", source.id)
        if not doc_id:
            doc_id = ObjectId()
            
        # Update the parent document by setting the embedded 'source' field
        res = await col.update_one(
            {"_id": doc_id},
            {"$set": {"source": source_dict}}
        )
        inserted_id = str(doc_id)
        logger.info(f"Embedded source in document {inserted_id} in MongoDB.")
        return inserted_id

    async def get_source(self, doc_id: str) -> Optional[CurriculumSource]:
        col = await self._get_collection()
        res = await col.find_one({"_id": ObjectId(doc_id)})
        if res and "source" in res:
            source_data = dict(res["source"])
            source_data["_id"] = res["_id"]
            # For schema parsing compatibility
            from ai_teacher_robot.rag.schemas.document import CurriculumSource
            return CurriculumSource.model_validate(source_data)
        return None

    async def delete_source(self, doc_id: str) -> bool:
        col = await self._get_collection()
        res = await col.update_one({"_id": ObjectId(doc_id)}, {"$unset": {"source": ""}})
        return res.modified_count > 0

