from typing import Optional, Dict, Any
from bson.objectid import ObjectId
from loguru import logger
from ai_teacher_robot.repositories.db_client import db_manager

class ConfigRepository:
    """Manages the curriculum_config collection in MongoDB for tracking active versions."""
    def __init__(self) -> None:
        self.collection_name = "curriculum_config"

    async def _get_collection(self):
        db = await db_manager.get_db()
        return db[self.collection_name]

    async def set_active_version(self, subject: str, grade: int, active_version: str) -> str:
        col = await self._get_collection()
        doc_filter = {"subject": subject, "grade": int(grade)}
        update_data = {
            "subject": subject,
            "grade": int(grade),
            "active_version": active_version
        }
        
        res = await col.update_one(
            doc_filter,
            {"$set": update_data},
            upsert=True
        )
        logger.info(f"Set active version for {subject} Grade {grade} to {active_version} in MongoDB.")
        # Retrieve updated document to get ID
        doc = await col.find_one(doc_filter)
        return str(doc["_id"]) if doc is not None else ""

    async def get_active_version(self, subject: str, grade: int) -> Optional[str]:
        col = await self._get_collection()
        doc_filter = {"subject": subject, "grade": int(grade)}
        
        doc = await col.find_one(doc_filter)
        if doc is not None:
            return doc.get("active_version")
        return None

