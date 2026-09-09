import time
import json
import os
import re
from typing import Any
import models.compat

from loguru import logger
from agentscope.agent import Agent
from agentscope.message import Msg

try:
    from motor.motor_asyncio import AsyncIOMotorClient
except ImportError:
    AsyncIOMotorClient = None
from ai_teacher_robot.repositories.db_client import db_manager

from .. import LLMGateway
from state.agentState import AgentStateManager
from models.schemas import AgentResult, QuizCardResponse, get_content_str
from .prompts import build_quiz_prompt


class QuizAgent(Agent):
    """
    Quiz Agent: Dynamically retrieves contextual topic data from MongoDB and generates
    unique 4-option multiple-choice questions formatted as Flag Cards.
    """
    def __init__(self, name: str = "QuizAgent", mongo_uri: str = None, db_name: str = None, **kwargs: Any) -> None:
        super().__init__()
        self.name = name
        self.state_manager = AgentStateManager()
        from .. import LLMGateway
        self.gateway = LLMGateway()
        self.mongo_uri = mongo_uri or os.environ.get("MONGO_URI", "mongodb://localhost:27017")
        self.db_name = db_name or os.environ.get("MONGO_DB_NAME", "SiliconRag")

    async def _get_db(self):
        return await db_manager.get_db()

    async def _fetch_mongodb_context(self, topic: str, grade: int | str | None, subject: str | None) -> str:
        db = await self._get_db()

        context_texts = []
        query_filter = {}
        if grade:
            match = re.search(r'\d+', str(grade))
            if match:
                grade_num = int(match.group(0))
                query_filter["$or"] = [
                    {"class": grade_num},
                    {"class": str(grade_num)},
                    {"class_level": grade_num},
                    {"class_level": str(grade_num)}
                ]

        if subject:
            subj_clean = subject.strip()
            query_filter["subject"] = {"$regex": subj_clean, "$options": "i"}

        try:
            cursor = db.curriculum_documents.find(query_filter).limit(5)
            async for doc in cursor:
                text = doc.get("text") or doc.get("content") or doc.get("title")
                if text:
                    context_texts.append(text[:500])

            if not context_texts and topic:
                regex_pattern = topic.split()[0] if topic.split() else topic
                cursor = db.chunks.find({"text": {"$regex": regex_pattern, "$options": "i"}}).limit(3)
                async for doc in cursor:
                    text = doc.get("text")
                    if text:
                        context_texts.append(text[:500])

        except Exception as e:
            logger.warning(f"MongoDB query encountered warning: {e}. Fallback to dynamic context generation.")

        if context_texts:
            return "\n---\n".join(context_texts)
        return f"Topic context: {topic or 'General knowledge'} (Class: {grade or 'General'}, Subject: {subject or 'General'})"

    async def reply(self, x: Any = None) -> Msg:
        start_time = time.time()
        raw_query = get_content_str(x)
        
        session_id = "default_sess"
        metadata = {}
        if isinstance(x, dict):
            metadata = x.get("metadata", {})
            session_id = metadata.get("session_id", "default_sess")
        elif hasattr(x, "metadata"):
            metadata = getattr(x, "metadata", {}) or {}
            session_id = metadata.get("session_id", "default_sess")

        topic = raw_query.strip() or "General Knowledge"
        grade_val = metadata.get("grade") or metadata.get("class") or metadata.get("planner_result", {}).get("class")
        subject = metadata.get("subject") or metadata.get("planner_result", {}).get("subject") or "General Science"

        card_count = metadata.get("count", 4)
        previous_questions = metadata.get("previous_questions", [])

        grade = None
        if grade_val is not None:
            match = re.search(r'\d+', str(grade_val))
            if match:
                grade = int(match.group(0))

        try:
            db_context = await self._fetch_mongodb_context(topic, grade, subject)
            class_prompt = self.state_manager.get_class_subject_prompt(grade, subject)

            prev_q_str = ""
            if previous_questions:
                prev_q_str = "\nCRITICAL: DO NOT repeat any of the following previously generated questions:\n" + "\n".join(f"- {q}" for q in previous_questions) + "\n"

            prompt = build_quiz_prompt(
                class_prompt=class_prompt,
                db_context=db_context,
                card_count=card_count,
                grade=grade,
                topic=topic,
                subject=subject,
                prev_q_str=prev_q_str,
            )

            model_config = self.state_manager.get_model_config("QuizAgent")
            if not model_config:
                model_config = {"temperature": 0.75, "max_tokens": 1600}
            model_config = dict(model_config)
            model_config["temperature"] = 0.8
            model_config["max_tokens"] = max(model_config.get("max_tokens", 1600), 1600)
            model_config["response_format"] = {"type": "json_object"}

            raw_response = await self.gateway.generate(prompt, **model_config)

            cleaned = raw_response.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            parsed_data = json.loads(cleaned)

            def strip_quiz_prefixes(q_str: str) -> str:
                if not q_str:
                    return ""
                pattern = r'^(?:In\s+Chapter\s+\d+[^,:]*[,:]\s*|According\s+to\s+Chapter\s+\d+[^,:]*[,:]\s*|Based\s+on\s+Class\s+\d+[^,:]*[,:]\s*|According\s+to\s+the\s+textbook[,:]\s*|Disclaimer:[^\n]*\n?|Pre-announced:[^\n]*\n?)'
                cleaned = re.sub(pattern, '', q_str, flags=re.IGNORECASE).strip()
                if cleaned and cleaned[0].islower():
                    cleaned = cleaned[0].upper() + cleaned[1:]
                return cleaned

            validated_cards = []
            if isinstance(parsed_data, dict) and "cards" in parsed_data:
                for c in parsed_data["cards"]:
                    if isinstance(c, dict) and "question" in c:
                        c["question"] = strip_quiz_prefixes(c["question"])
                    try:
                        validated_cards.append(QuizCardResponse(**c).model_dump())
                    except Exception:
                        validated_cards.append(c)
            elif isinstance(parsed_data, list):
                for c in parsed_data:
                    if isinstance(c, dict) and "question" in c:
                        c["question"] = strip_quiz_prefixes(c["question"])
                    try:
                        validated_cards.append(QuizCardResponse(**c).model_dump())
                    except Exception:
                        validated_cards.append(c)
            else:
                if isinstance(parsed_data, dict) and "question" in parsed_data:
                    parsed_data["question"] = strip_quiz_prefixes(parsed_data["question"])
                try:
                    single_card = QuizCardResponse(**parsed_data).model_dump()
                    validated_cards.append(single_card)
                except Exception:
                    validated_cards.append(parsed_data)

            final_data = {
                "card_type": "flag_quiz_card_set",
                "topic": topic,
                "subject": subject,
                "class_level": grade,
                "count": len(validated_cards),
                "cards": validated_cards
            }

            execution_time = time.time() - start_time
            result = AgentResult(
                success=True,
                data=final_data,
                execution_time=execution_time
            )

            logger.info(
                f"QuizAgent generated {len(validated_cards)} flag cards successfully",
                agent=self.name,
                count=len(validated_cards),
                execution_time=round(execution_time, 3),
                session_id=session_id
            )

            return Msg(
                name=self.name,
                content=result.model_dump_json(),
                metadata={"agent_result": result.model_dump()}
            )

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(
                "Exception in QuizAgent: {}",
                str(e),
                agent=self.name,
                execution_time=round(execution_time, 3),
                session_id=session_id
            )
            result = AgentResult(
                success=False,
                data=None,
                error=f"Quiz generation exception: {str(e)}",
                execution_time=execution_time
            )
            return Msg(
                name=self.name,
                content=result.model_dump_json(),
                metadata={"agent_result": result.model_dump()}
            )
