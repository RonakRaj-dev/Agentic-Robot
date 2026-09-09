from typing import Optional, Dict, Any
from bson.objectid import ObjectId
from loguru import logger
from ai_teacher_robot.repositories.db_client import db_manager

class MetadataRepository:
    """Manages system configurations and Ingestion metadata run logs (embedded under curriculum_documents) in MongoDB."""
    def __init__(self) -> None:
        self.collection_name = "curriculum_documents"

    async def _get_collection(self):
        db = await db_manager.get_db()
        return db[self.collection_name]

    async def save_run_metadata(self, run_id: str, metadata: Dict[str, Any]) -> None:
        col = await self._get_collection()
        doc_id = metadata.get("document_id") or run_id.replace("run_", "")
        
        await col.update_one(
            {"_id": ObjectId(doc_id)},
            {"$set": {"run_metadata": metadata}}
        )
        logger.info(f"Saved embedded run metadata for {doc_id} to MongoDB.")

    async def get_run_metadata(self, run_id: str) -> Optional[Dict[str, Any]]:
        col = await self._get_collection()
        doc_id = run_id.replace("run_", "")
        res = await col.find_one({"_id": ObjectId(doc_id)})
        if res and "run_metadata" in res:
            return res["run_metadata"]
        return None

