from loguru import logger

from ai_teacher_robot.repositories.db_client import db_manager


class CurriculumRepository:

    async def get_context(
        self,
        topic: str,
        grade: int,
        subject: str,
    ) -> str:

        db = await db_manager.get_db()
        context = []

        try:
            cursor = db.curriculum_documents.find(
                {
                    "$or": [
                        {"class": grade},
                        {"class": str(grade)},
                    ],
                    "subject": {
                        "$regex": subject,
                        "$options": "i",
                    },
                }
            ).limit(3)

            async for doc in cursor:

                text = (
                    doc.get("text")
                    or doc.get("content")
                )

                if text:
                    context.append(text[:600])

        except Exception as exc:
            logger.warning(
                f"Curriculum retrieval failed: {exc}"
            )

        return (
            "\n\n".join(context)
            if context
            else f"General textbooks context for '{topic}'."
        )