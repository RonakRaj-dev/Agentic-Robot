import datetime
from typing import Optional, Dict, Any, List
from bson.objectid import ObjectId
from loguru import logger
from ai_teacher_robot.repositories.db_client import db_manager

class InteractionRepository:
    """Manages the interaction_logs collection in MongoDB for logging student sessions."""
    def __init__(self) -> None:
        self.collection_name = "interaction_logs"

    async def _get_collection(self):
        db = await db_manager.get_db()
        return db[self.collection_name]

    async def log_interaction(
        self,
        session_id: str,
        student_query: str,
        rewritten_query: str,
        retrieved_chunk_ids: List[str],
        final_answer: str,
        confidence_score: float,
        flagged: bool
    ) -> str:
        col = await self._get_collection()
        log_doc = {
            "session_id": session_id,
            "student_query": student_query,
            "rewritten_query": rewritten_query,
            "retrieved_chunk_ids": retrieved_chunk_ids,
            "final_answer": final_answer,
            "confidence_score": float(confidence_score),
            "flagged": bool(flagged),
            "timestamp": datetime.datetime.now(datetime.UTC)
        }
        
        res = await col.insert_one(log_doc)
        inserted_id = str(res.inserted_id)
        logger.info(f"Logged interaction {inserted_id} for session {session_id} in MongoDB.")
        return inserted_id

    async def get_interaction(self, log_id: str) -> Optional[Dict[str, Any]]:
        col = await self._get_collection()
        doc = await col.find_one({"_id": ObjectId(log_id)})
        if doc is not None:
            doc["_id"] = str(doc["_id"])
        return doc

