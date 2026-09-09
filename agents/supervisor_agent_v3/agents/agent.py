import time
import json
import re
import asyncio
from typing import Any, Dict
from loguru import logger

import models.compat
from agentscope.agents import Agent
from agentscope.message import UserMsg, AssistantMsg

from models.schemas import AgentResult, get_content_str
from state.sessionState import SessionStateManager
from state.agentState import AgentStateManager

from agents.validator_agent import ValidationAgent
from agents.safety_agent import SafetyAgent
from agents.retrieval.retrieval_planner_agent import RetrievalPlannerAgent
from agents.retrieval.curriculum_rag_agent import CurriculumRAGAgent
from agents.teaching_agent import TeachingAgent
from agents.verification.fact_verification_agent import FactVerificationAgent
from agents.response_agent import ResponseAgent
from agents.quiz_agent import QuizAgent
from agents.video_agent import VideoAgent
from ai_teacher_robot.repositories.interaction_repository import InteractionRepository
from ai_teacher_robot.repositories.source_repository import SourceRepository

from agents.adaptive_learning_agent import AdaptiveLearningAgent
from agents.memory_agent import MemoryAgent
from agents.analytics_agent import AnalyticsAgent
from agents.assessment_agent import AssessmentAgent
from agents.classroom_interaction_agent import ClassroomInteractionAgent
from agents.content_generation_agent import ContentGenerationAgent
from agents.summary_agent import SummaryAgent
from agents.planner_agent import PlannerAgent
from ai_teacher_robot.repositories.v3_repositories import LearningHistoryRepository

from agents.orchestration import OrchestrationEngine


class ClassroomSupervisorAgentV3(Agent):
    """
    ClassroomSupervisorAgentV3: Orchestrates the full autonomous AI Teaching Assistant (V3)
    pipeline using the unified multi-agent OrchestrationEngine (supporting Sequential, Concurrent,
    Group Chat, Hands-off, and Magnetic Attractor patterns).
    """
    def __init__(self, name: str = "ClassroomSupervisorAgentV3", **kwargs: Any) -> None:
        super().__init__()
        self.name = name
        self.session_manager = SessionStateManager()
        self.agent_state_manager = AgentStateManager()
        
        self.validation_agent = ValidationAgent(name="ValidationAgent")
        self.safety_agent = SafetyAgent(name="SafetyAgent")
        self.planner_agent = PlannerAgent(name="PlannerAgent")
        self.rag_agent = CurriculumRAGAgent(name="CurriculumRAGAgent")
        self.teaching_agent = TeachingAgent(name="TeachingAgent")
        self.verification_agent = FactVerificationAgent(name="FactVerificationAgent")
        self.response_agent = ResponseAgent(name="ResponseAgent")
        self.quiz_agent = QuizAgent(name="QuizAgent")
        self.video_agent = VideoAgent(name="VideoAgent")
        self.interaction_repo = InteractionRepository()
        self.source_repo = SourceRepository()
        
        self.memory_agent = MemoryAgent(name="MemoryAgent")
        self.adaptive_agent = AdaptiveLearningAgent(name="AdaptiveLearningAgent")
        self.assessment_agent = AssessmentAgent(name="AssessmentAgent")
        self.interaction_game_agent = ClassroomInteractionAgent(name="ClassroomInteractionAgent")
        self.content_gen_agent = ContentGenerationAgent(name="ContentGenerationAgent")
        self.summary_agent = SummaryAgent(name="SummaryAgent")
        self.analytics_agent = AnalyticsAgent(name="AnalyticsAgent")
        
        self.learning_repo = LearningHistoryRepository()

        # Initialize unified Multi-Agent Orchestration Engine
        self.agent_registry = {
            "validation_agent": self.validation_agent,
            "safety_agent": self.safety_agent,
            "planner_agent": self.planner_agent,
            "rag_agent": self.rag_agent,
            "teaching_agent": self.teaching_agent,
            "verification_agent": self.verification_agent,
            "response_agent": self.response_agent,
            "quiz_agent": self.quiz_agent,
            "video_agent": self.video_agent,
            "memory_agent": self.memory_agent,
            "adaptive_agent": self.adaptive_agent,
            "assessment_agent": self.assessment_agent,
            "ClassroomInteractionAgent": self.interaction_game_agent,
            "AssessmentAgent": self.assessment_agent,
            "ContentGenerationAgent": self.content_gen_agent,
            "summary_agent": self.summary_agent,
            "analytics_agent": self.analytics_agent,
        }
        
        self.orchestrator = OrchestrationEngine(self.agent_registry)

    async def reply(self, x: Any = None) -> AssistantMsg:
        start_time = time.time()
        query = get_content_str(x)
        
        session_id = "default_sess"
        metadata_dict = {}
        if isinstance(x, dict):
            session_id = x.get("metadata", {}).get("session_id", "default_sess")
            metadata_dict = x.get("metadata", {})
        elif hasattr(x, "metadata"):
            session_id = getattr(x, "metadata", {}).get("session_id", "default_sess")
            metadata_dict = getattr(x, "metadata", {}) or {}

        auth_grade = metadata_dict.get("grade") or 5
        auth_subject = metadata_dict.get("subject") or "General"
        student_id = metadata_dict.get("student_id") or metadata_dict.get("username") or "default_student"

        if not query.strip():
            execution_time = time.time() - start_time
            result = AgentResult(
                success=False,
                data=None,
                error="Input query to supervisor is empty.",
                execution_time=execution_time
            )
            return AssistantMsg(
                name=self.name,
                content=result.model_dump_json(),
                metadata={"agent_result": result.model_dump()}
            )

        lock_name = f"session:{session_id}"
        if not self.session_manager.acquire_lock(lock_name, expire_seconds=30):
            execution_time = time.time() - start_time
            logger.warning(f"Lock active for session {session_id}. Rejecting concurrent query.")
            result = AgentResult(
                success=False,
                data=None,
                error="Concurrent message error: session is locked processing another request.",
                execution_time=execution_time
            )
            return AssistantMsg(
                name=self.name,
                content=result.model_dump_json(),
                metadata={"agent_result": result.model_dump()}
            )

        try:
            self.session_manager.save_message(session_id, sender="User", content=query)
            pipeline_metadata = {
                "session_id": session_id,
                "grade": auth_grade,
                "subject": auth_subject,
                "student_id": student_id,
                "role": metadata_dict.get("role", "student"),
                "intent": metadata_dict.get("intent", ""),
                "game_mode": metadata_dict.get("game_mode"),
                "action": metadata_dict.get("action"),
                "enable_group_chat": metadata_dict.get("enable_group_chat", False),
                "enable_magnetic_attractor": metadata_dict.get("enable_magnetic_attractor", True),
            }

            # ----------------------------------------------------
            # ORCHESTRATION PATTERN 1: SEQUENTIAL GUARDRAILS
            # ----------------------------------------------------
            is_safe, fail_msg = await self.orchestrator.execute_sequential_guardrails(query, pipeline_metadata)
            if not is_safe and fail_msg:
                return fail_msg

            # ----------------------------------------------------
            # ORCHESTRATION PATTERN 2: CONCURRENT PRE-FETCH
            # ----------------------------------------------------
            prefetch_res = await self.orchestrator.execute_concurrent_prefetch(query, pipeline_metadata)
            
            memory_data = prefetch_res.get("memory", {}).get("data") or {}
            adaptive_data = prefetch_res.get("adaptive", {}).get("data") or {
                "difficulty_level": "Intermediate", "teaching_style": "Conceptual", "recommended_learning_path": []
            }
            plan_data = prefetch_res.get("planner", {}).get("data") or {
                "need_quiz": False, "need_story": False, "need_diagram": False, "need_video": False,
                "need_homework": False, "need_summary": False, "teaching_strategy": "Direct Explain", "execution_plan": ["TeachingAgent"]
            }

            # ----------------------------------------------------
            # ORCHESTRATION PATTERN 4: HANDS-OFF DYNAMIC ROUTING
            # ----------------------------------------------------
            handoff_signal = self.orchestrator.check_hands_off_routing(query, pipeline_metadata, plan_data)
            if handoff_signal:
                logger.info(f"SupervisorV3: Hands-off router triggered -> {handoff_signal.target_agent}")
                target_msg = UserMsg(name="Supervisor", content=query, metadata=pipeline_metadata)
                reply = await self.orchestrator.handoff_manager.execute_handoff(handoff_signal, target_msg)
                if reply:
                    self.session_manager.release_lock(lock_name)
                    return reply

            # Execute RAG Retrieval
            retrieved_chunks = []
            if "RAGAgent" in plan_data.get("execution_plan", []) or not (metadata_dict.get("game_mode") or metadata_dict.get("action")):
                rag_planner_data = {
                    "class": str(auth_grade),
                    "subject": auth_subject,
                    "rewritten_query": query,
                    "top_k": 3
                }
                rag_msg = UserMsg(name="Supervisor", content=query, metadata={"session_id": session_id, "planner_result": rag_planner_data})
                rag_reply = await self.rag_agent.reply(rag_msg)
                rag_res_dict = getattr(rag_reply, "metadata", {}).get("agent_result", {})
                if rag_res_dict.get("success", False):
                    retrieved_chunks = rag_res_dict.get("data", {}).get("chunks", [])

            final_confidence = 0.5
            if retrieved_chunks:
                scores = [c.get("score", 0.0) for c in retrieved_chunks[:3]]
                avg_score = sum(scores) / len(scores)
                final_confidence = min(max(avg_score, 0.0), 1.0)

            context_blocks = []
            for idx, chunk in enumerate(retrieved_chunks):
                context_blocks.append(f"[Source #{idx+1}] Chapter {chunk.get('chapter')}, Page {chunk.get('page_number')}:\n{chunk.get('chunk_text')}")
            context_str = "\n\n".join(context_blocks)

            teaching_explanation = ""
            citations_payload = []
            v_data = {}

            # ----------------------------------------------------
            # ORCHESTRATION PATTERN 3 & 5: GROUP CHAT / MAGNETIC ATTRACTOR
            # ----------------------------------------------------
            if pipeline_metadata.get("enable_group_chat"):
                logger.info("SupervisorV3: Engaging GROUP CHAT dialogue for lesson refinement...")
                chat_res = await self.orchestrator.execute_group_chat_dialogue(
                    query=query,
                    context_str=context_str,
                    adaptive_data=adaptive_data,
                    pipeline_metadata=pipeline_metadata,
                )
                teaching_explanation = chat_res.get("final_explanation", "")

            else:
                level_style_prep = (
                    f"ADAPTIVE SETTING FOR EXPLANATION:\n"
                    f"- Difficulty Level Target: {adaptive_data.get('difficulty_level', 'Intermediate')}\n"
                    f"- Teaching Style Preferred: {adaptive_data.get('teaching_style', 'Conceptual')}\n"
                    f"- Student Working memory summary: {memory_data.get('working_memory', '')}\n"
                    f"- Student Long-term struggles: {memory_data.get('long_term_memory', '')}\n"
                    f"Please adapt explanations and vocabulary strictly targeting this profile.\n\n"
                )
                
                grounded_query = f"{level_style_prep}Reference Context:\n{context_str}\n\nQuestion: {query}" if context_str else f"{level_style_prep}Question: {query}"
                
                teach_msg = UserMsg(name="Supervisor", content=grounded_query, metadata=pipeline_metadata)
                teach_reply = await self.teaching_agent.reply(teach_msg)
                teach_res_dict = getattr(teach_reply, "metadata", {}).get("agent_result", {})
                if not teach_res_dict.get("success", False):
                    return self._failed_msg(teach_res_dict.get("error", "Teaching Agent failed."), start_time)

                initial_explanation = teach_res_dict.get("data", {}).get("explanation", "")

                if pipeline_metadata.get("enable_magnetic_attractor", True) and len(retrieved_chunks) > 0:
                    logger.info("SupervisorV3: Engaging MAGNETIC ATTRACTOR convergence loop...")
                    attractor_res = await self.orchestrator.execute_magnetic_attractor_convergence(
                        initial_explanation=initial_explanation,
                        retrieved_chunks=retrieved_chunks,
                        grounded_query=grounded_query,
                        pipeline_metadata=pipeline_metadata,
                    )
                    teaching_explanation = attractor_res.get("final_explanation", initial_explanation)
                    v_data = attractor_res.get("verification_data", {})
                else:
                    teaching_explanation = initial_explanation

            if not v_data and len(retrieved_chunks) > 0:
                verify_msg = UserMsg(name="Supervisor", content=teaching_explanation, metadata={"session_id": session_id, "retrieved_chunks": retrieved_chunks})
                verify_reply = await self.verification_agent.reply(verify_msg)
                verify_res_dict = getattr(verify_reply, "metadata", {}).get("agent_result", {})
                v_data = verify_res_dict.get("data", {}) if verify_res_dict.get("success", False) else {}

            citations = v_data.get("citations", [])
            response_content = teaching_explanation
            if citations:
                response_content = f"{response_content}\n\nCitations:\n" + "\n".join([f"- {c}" for c in citations])
            
            # Format Final Output Egress Contract (Pattern 1 Sequential Egress)
            response_msg = UserMsg(name="Supervisor", content=response_content, metadata=pipeline_metadata)
            response_reply = await self.response_agent.reply(response_msg)
            response_res_dict = getattr(response_reply, "metadata", {}).get("agent_result", {})
            final_data = response_res_dict.get("data", {}) if response_res_dict.get("success", False) else {"answer": response_content}

            for chunk in retrieved_chunks:
                doc_id = chunk.get("document_id")
                source_file = "Unknown Source"
                if doc_id:
                    try:
                        source = await self.source_repo.get_source(doc_id)
                        if source:
                            import os
                            source_file = os.path.basename(source.pdf_path)
                    except Exception:
                        pass
                
                if source_file == "Unknown Source":
                    b_title = chunk.get("book_title") or f"NCERT {chunk.get('subject', 'General')} Class {chunk.get('class', '1')}"
                    ch_title = chunk.get("chapter_name") or f"Chapter {chunk.get('chapter', '1')}"
                    if ch_title.lower().startswith("chapter"):
                        source_file = f"{b_title}, {ch_title}"
                    else:
                        source_file = f"{b_title}, Chapter {chunk.get('chapter', '1')}: {ch_title}"
                citations_payload.append({
                    "source_file": source_file,
                    "page_number": int(chunk.get("page_number", 1)),
                    "chapter": str(chunk.get("chapter", "1")),
                    "content": chunk.get("chunk_text") or chunk.get("text", "")
                })

            final_answer_text = final_data.get("answer", "")
            
            mastery_score = 0.85 if retrieved_chunks else 0.65
            await self.learning_repo.update_mastery(
                student_id=student_id,
                topic=query.split()[-1] if len(query.split()) > 0 else query,
                subject=auth_subject,
                grade=auth_grade,
                mastery_score=mastery_score
            )

            # ----------------------------------------------------
            # ORCHESTRATION PATTERN 2: CONCURRENT POST-ASSET ENRICHMENT
            # ----------------------------------------------------
            asset_res = await self.orchestrator.execute_concurrent_asset_generation(
                query=query,
                final_answer=final_answer_text,
                plan_data=plan_data,
                pipeline_metadata=pipeline_metadata,
            )

            response_payload = {
                "answer": final_answer_text,
                "citations": citations_payload,
                "confidence_score": float(final_confidence),
                "flagged": False,
                "session_id": session_id,
                "adaptive_profile": adaptive_data,
                "planning_strategy": plan_data.get("teaching_strategy", ""),
                "video_blueprint": asset_res.get("video", {}).get("data"),
                "quiz_cards": asset_res.get("quiz", {}).get("data"),
                "session_summary": asset_res.get("summary", {}).get("data")
            }

            retrieved_chunk_ids = [c.get("chunk_id") for c in retrieved_chunks]
            await self.interaction_repo.log_interaction(
                session_id=session_id,
                student_query=query,
                rewritten_query=query,
                retrieved_chunk_ids=retrieved_chunk_ids,
                final_answer=response_payload["answer"],
                confidence_score=final_confidence,
                flagged=False
            )
            
            self.session_manager.save_message(session_id, sender="Supervisor", content=response_payload["answer"])
            
            duration = time.time() - start_time
            result = AgentResult(
                success=True,
                data=response_payload,
                execution_time=duration
            )
            return AssistantMsg(
                name=self.name,
                content=result.model_dump_json(),
                metadata={"agent_result": result.model_dump()}
            )

        except Exception as e:
            logger.error("Supervisor V3 exception: {}", str(e))
            return self._failed_msg(f"Supervisor V3 system error: {str(e)}", start_time)
        finally:
            self.session_manager.release_lock(lock_name)

    def _failed_msg(self, error: str, start_time: float) -> AssistantMsg:
        duration = time.time() - start_time
        result = AgentResult(
            success=False,
            data={
                "answer": error,
                "citations": [],
                "confidence_score": 0.0,
                "flagged": False,
                "session_id": "default_sess"
            },
            error=error,
            execution_time=duration
        )
        return AssistantMsg(
            name=self.name,
            content=result.model_dump_json(),
            metadata={"agent_result": result.model_dump()}
        )
