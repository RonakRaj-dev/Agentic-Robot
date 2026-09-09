import datetime
from typing import Optional, Dict, Any, List
from bson.objectid import ObjectId
from loguru import logger
from ai_teacher_robot.repositories.db_client import db_manager

class LearningHistoryRepository:
    """Manages the learning_history collection in MongoDB for tracking concept mastery."""
    def __init__(self) -> None:
        self.collection_name = "learning_history"

    async def _get_collection(self):
        db = await db_manager.get_db()
        return db[self.collection_name]

    async def get_mastery(self, student_id: str, topic: str) -> Optional[Dict[str, Any]]:
        col = await self._get_collection()
        doc = await col.find_one({"student_id": student_id, "topic": topic})
        if doc is not None:
            doc["_id"] = str(doc["_id"])
        return doc

    async def get_all_student_history(self, student_id: str) -> List[Dict[str, Any]]:
        col = await self._get_collection()
        cursor = col.find({"student_id": student_id})
        res = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            res.append(doc)
        return res

    async def update_mastery(
        self,
        student_id: str,
        topic: str,
        subject: str,
        grade: int,
        mastery_score: float,
        mistake: Optional[str] = None
    ) -> None:
        col = await self._get_collection()
        now = datetime.datetime.now(datetime.UTC)
        
        # Build update document
        update_set = {
            "subject": subject,
            "grade": int(grade),
            "mastery_score": float(mastery_score),
            "last_interaction": now
        }
        
        update_doc = {
            "$set": update_set,
            "$inc": {"questions_asked": 1}
        }
        
        if mistake:
            update_doc["$push"] = {"mistakes_logged": mistake}

        await col.update_one(
            {"student_id": student_id, "topic": topic},
            update_doc,
            upsert=True
        )
        logger.info(f"Updated learning history for student {student_id} on topic '{topic}'.")


class AssessmentHistoryRepository:
    """Manages the assessment_history and quiz_results collections in MongoDB."""
    def __init__(self) -> None:
        self.collection_name = "assessment_history"

    async def _get_collection(self):
        db = await db_manager.get_db()
        return db[self.collection_name]

    async def log_assessment(
        self,
        session_id: str,
        student_id: str,
        topic: str,
        questions: List[Dict[str, Any]],
        score: float,
        max_score: float,
        weak_topics: List[str],
        revision_plan: str
    ) -> str:
        col = await self._get_collection()
        doc = {
            "session_id": session_id,
            "student_id": student_id,
            "topic": topic,
            "questions": questions,
            "score": float(score),
            "max_score": float(max_score),
            "weak_topics": weak_topics,
            "revision_plan": revision_plan,
            "timestamp": datetime.datetime.now(datetime.UTC)
        }
        res = await col.insert_one(doc)
        inserted_id = str(res.inserted_id)
        logger.info(f"Logged assessment {inserted_id} for student {student_id} on topic '{topic}'.")
        return inserted_id

    async def get_student_assessments(self, student_id: str) -> List[Dict[str, Any]]:
        col = await self._get_collection()
        cursor = col.find({"student_id": student_id})
        res = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            res.append(doc)
        return res


class GeneratedMaterialsRepository:
    """Manages the generated_materials collection for worksheets, handouts, and lesson notes."""
    def __init__(self) -> None:
        self.collection_name = "generated_materials"

    async def _get_collection(self):
        db = await db_manager.get_db()
        return db[self.collection_name]

    async def log_material(
        self,
        teacher_id: str,
        grade: int,
        subject: str,
        topic: str,
        material_type: str,
        format_type: str,
        content: str,
        file_path: Optional[str] = None
    ) -> str:
        col = await self._get_collection()
        doc = {
            "teacher_id": teacher_id,
            "grade": int(grade),
            "subject": subject,
            "topic": topic,
            "material_type": material_type,
            "format": format_type,
            "content": content,
            "file_path": file_path,
            "created_at": datetime.datetime.now(datetime.UTC)
        }
        res = await col.insert_one(doc)
        inserted_id = str(res.inserted_id)
        logger.info(f"Logged generated material {inserted_id} ({material_type}) for teacher {teacher_id}.")
        return inserted_id


class ClassroomSessionRepository:
    """Manages class session metadata, aggregate reports, and session histories."""
    def __init__(self) -> None:
        self.collection_name = "class_reports"

    async def _get_collection(self):
        db = await db_manager.get_db()
        return db[self.collection_name]

    async def log_session_report(
        self,
        session_id: str,
        subject: str,
        grade: int,
        questions_asked: int,
        average_difficulty: str,
        weak_topics: List[str],
        topic_statistics: Dict[str, int],
        summary: str
    ) -> str:
        col = await self._get_collection()
        doc = {
            "session_id": session_id,
            "subject": subject,
            "grade": int(grade),
            "questions_asked": int(questions_asked),
            "average_difficulty": average_difficulty,
            "weak_topics": weak_topics,
            "topic_statistics": topic_statistics,
            "summary": summary,
            "created_at": datetime.datetime.now(datetime.UTC)
        }
        res = await col.insert_one(doc)
        inserted_id = str(res.inserted_id)
        logger.info(f"Logged session report {inserted_id} for session {session_id}.")
        return inserted_id

    async def get_session_report(self, session_id: str) -> Optional[Dict[str, Any]]:
        col = await self._get_collection()
        doc = await col.find_one({"session_id": session_id})
        if doc is not None:
            doc["_id"] = str(doc["_id"])
        return doc
