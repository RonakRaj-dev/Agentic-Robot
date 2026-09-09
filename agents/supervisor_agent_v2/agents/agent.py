import time
import json
from typing import Any, Dict, Optional
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


class ClassroomSupervisorAgentV2(Agent):
    """
    ClassroomSupervisorAgentV2: Directs the V2 educational pipeline including:
    Validation -> Safety -> Specialized Routing (Quiz/Video/Teaching) -> Response formatting.
    """
    def __init__(self, name: str = "ClassroomSupervisorAgentV2", **kwargs: Any) -> None:
        super().__init__()
        self.name = name
        self.session_manager = SessionStateManager()
        self.agent_state_manager = AgentStateManager()
        
        self.validation_agent = ValidationAgent(name="ValidationAgent")
        self.safety_agent = SafetyAgent(name="SafetyAgent")
        self.planner_agent = RetrievalPlannerAgent(name="RetrievalPlannerAgent")
        self.rag_agent = CurriculumRAGAgent(name="CurriculumRAGAgent")
        self.teaching_agent = TeachingAgent(name="TeachingAgent")
        self.verification_agent = FactVerificationAgent(name="FactVerificationAgent")
        self.response_agent = ResponseAgent(name="ResponseAgent")
        self.quiz_agent = QuizAgent(name="QuizAgent")
        self.video_agent = VideoAgent(name="VideoAgent")
        self.interaction_repo = InteractionRepository()
        self.source_repo = SourceRepository()

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
            metadata_dict = getattr(x, "metadata", {})

        auth_grade = metadata_dict.get("grade")
        auth_subject = metadata_dict.get("subject")

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
                "role": metadata_dict.get("role")
            }

            # 1. VALIDATION
            step_start = time.time()
            val_msg = UserMsg(name="Supervisor", content=query, metadata=pipeline_metadata)
            val_reply = await self.validation_agent.reply(val_msg)
            val_res_dict = getattr(val_reply, "metadata", {}).get("agent_result", {})
            val_success = val_res_dict.get("success", False)
            
            self.session_manager.save_execution_state(
                session_id=session_id, agent="ValidationAgent",
                status="success" if val_success else "failed",
                execution_time=time.time() - step_start,
                error=val_res_dict.get("error")
            )
            if not val_success:
                return self._failed_msg(val_res_dict.get("error", "Sanitization failed."), start_time)

            # 2. SAFETY
            step_start = time.time()
            safety_msg = UserMsg(name="Supervisor", content=query, metadata=pipeline_metadata)
            safety_reply = await self.safety_agent.reply(safety_msg)
            safety_res_dict = getattr(safety_reply, "metadata", {}).get("agent_result", {})
            safety_success = safety_res_dict.get("success", False)
            
            self.session_manager.save_execution_state(
                session_id=session_id, agent="SafetyAgent",
                status="success" if safety_success else "failed",
                execution_time=time.time() - step_start,
                error=safety_res_dict.get("error")
            )
            if not safety_success:
                return self._failed_msg(safety_res_dict.get("error", "Safety check failed."), start_time)

            # 2.5 SPECIALIZED ROUTING (QUIZ & VIDEO AGENTS)
            query_lower = query.lower()
            intent_req = metadata_dict.get("intent")

            if intent_req == "quiz" or any(kw in query_lower for kw in ["quiz", "flag card", "mcq", "quiz card"]):
                logger.info(f"Routing request to QuizAgent for session {session_id}")
                quiz_msg = UserMsg(name="Supervisor", content=query, metadata=pipeline_metadata)
                quiz_reply = await self.quiz_agent.reply(quiz_msg)
                self.session_manager.release_lock(lock_name)
                return quiz_reply

            if intent_req == "video" or any(kw in query_lower for kw in ["video", "generate video", "make video"]):
                logger.info(f"Routing request to VideoAgent for session {session_id}")
                video_msg = UserMsg(name="Supervisor", content=query, metadata=pipeline_metadata)
                video_reply = await self.video_agent.reply(video_msg)
                self.session_manager.release_lock(lock_name)
                return video_reply

            # 3. RETRIEVAL PLANNING
            step_start = time.time()
            planner_msg = UserMsg(name="Supervisor", content=query, metadata=pipeline_metadata)
            planner_reply = await self.planner_agent.reply(planner_msg)
            planner_res_dict = getattr(planner_reply, "metadata", {}).get("agent_result", {})
            planner_success = planner_res_dict.get("success", False)
            
            self.session_manager.save_execution_state(
                session_id=session_id, agent="RetrievalPlannerAgent",
                status="success" if planner_success else "failed",
                execution_time=time.time() - step_start,
                error=planner_res_dict.get("error")
            )
            if not planner_success:
                return self._failed_msg(planner_res_dict.get("error", "Planning failed."), start_time)

            planner_data = planner_res_dict.get("data", {})
            if not isinstance(planner_data, dict):
                planner_data = {}

            if auth_grade is not None:
                planner_data["class"] = str(auth_grade)
            if auth_subject is not None and auth_subject != "":
                planner_data["subject"] = auth_subject

            rag_required = planner_data.get("rag_required", True)

            # 4. CURRICULUM RAG
            retrieved_chunks = []
            if rag_required:
                step_start = time.time()
                rag_msg = UserMsg(
                    name="Supervisor", 
                    content=query, 
                    metadata={
                        "session_id": session_id,
                        "planner_result": planner_data
                    }
                )
                rag_reply = await self.rag_agent.reply(rag_msg)
                rag_res_dict = getattr(rag_reply, "metadata", {}).get("agent_result", {})
                rag_success = rag_res_dict.get("success", False)
                
                self.session_manager.save_execution_state(
                    session_id=session_id, agent="CurriculumRAGAgent",
                    status="success" if rag_success else "failed",
                    execution_time=time.time() - step_start,
                    error=rag_res_dict.get("error")
                )
                if rag_success:
                    retrieved_chunks = rag_res_dict.get("data", {}).get("chunks", [])

                top_score = retrieved_chunks[0].get("score", 0.0) if retrieved_chunks else 0.0
                if not retrieved_chunks or top_score < 0.35:
                    has_restrictions = planner_data.get("chapter") is not None or planner_data.get("board") is not None
                    
                    if has_restrictions:
                        logger.info(f"Top chunk score ({top_score:.3f}) < 0.35. Retrying with broadened filters (dropping chapter/board)...")
                        broad_planner_data = dict(planner_data)
                        broad_planner_data["chapter"] = None
                        broad_planner_data["board"] = None
                        
                        step_start = time.time()
                        rag_msg = UserMsg(
                            name="Supervisor", 
                            content=query, 
                            metadata={
                                "session_id": session_id,
                                "planner_result": broad_planner_data
                            }
                        )
                        rag_reply = await self.rag_agent.reply(rag_msg)
                        rag_res_dict = getattr(rag_reply, "metadata", {}).get("agent_result", {})
                        rag_success = rag_res_dict.get("success", False)
                        
                        self.session_manager.save_execution_state(
                            session_id=session_id, agent="CurriculumRAGAgent_Retry",
                            status="success" if rag_success else "failed",
                            execution_time=time.time() - step_start,
                            error=rag_res_dict.get("error")
                        )
                        if rag_success:
                            retrieved_chunks = rag_res_dict.get("data", {}).get("chunks", [])
                    
                    top_score = retrieved_chunks[0].get("score", 0.0) if retrieved_chunks else 0.0
                    if not retrieved_chunks or top_score < 0.35:
                        has_subject = planner_data.get("subject") is not None
                        if has_subject:
                            logger.info(f"Top chunk score ({top_score:.3f}) < 0.35. Retrying with global class search (dropping subject)...")
                            global_planner_data = dict(planner_data)
                            global_planner_data["subject"] = None
                            global_planner_data["chapter"] = None
                            global_planner_data["board"] = None
                            
                            step_start = time.time()
                            rag_msg = UserMsg(
                                name="Supervisor", 
                                content=query, 
                                metadata={
                                    "session_id": session_id,
                                    "planner_result": global_planner_data
                                }
                            )
                            rag_reply = await self.rag_agent.reply(rag_msg)
                            rag_res_dict = getattr(rag_reply, "metadata", {}).get("agent_result", {})
                            rag_success = rag_res_dict.get("success", False)
                            
                            self.session_manager.save_execution_state(
                                session_id=session_id, agent="CurriculumRAGAgent_GlobalRetry",
                                status="success" if rag_success else "failed",
                                execution_time=time.time() - step_start,
                                error=rag_res_dict.get("error")
                            )
                            if rag_success:
                                retrieved_chunks = rag_res_dict.get("data", {}).get("chunks", [])
                    
                    top_score = retrieved_chunks[0].get("score", 0.0) if retrieved_chunks else 0.0
                    if not retrieved_chunks or top_score < 0.35:
                        logger.info(f"Rerank score ({top_score:.3f}) under 0.35 threshold. Proceeding with direct LLM TeachingAgent generation.")
                        retrieved_chunks = []

            final_confidence = 0.5
            if retrieved_chunks:
                scores = [c.get("score", 0.0) for c in retrieved_chunks[:3]]
                avg_score = sum(scores) / len(scores)
                final_confidence = min(max(avg_score, 0.0), 1.0)

            # 5. TEACHING
            step_start = time.time()
            context_blocks = []
            for idx, chunk in enumerate(retrieved_chunks):
                context_blocks.append(f"[Source #{idx+1}] Chapter {chunk.get('chapter')}, Page {chunk.get('page_number')}:\n{chunk.get('chunk_text')}")
            
            context_str = "\n\n".join(context_blocks)
            grounded_query = query
            if context_str:
                grounded_query = f"Reference Context:\n{context_str}\n\nQuestion: {query}"

            teach_msg = UserMsg(name="Supervisor", content=grounded_query, metadata=pipeline_metadata)
            teach_reply = await self.teaching_agent.reply(teach_msg)
            teach_res_dict = getattr(teach_reply, "metadata", {}).get("agent_result", {})
            teach_success = teach_res_dict.get("success", False)
            
            self.session_manager.save_execution_state(
                session_id=session_id, agent="TeachingAgent",
                status="success" if teach_success else "failed",
                execution_time=time.time() - step_start,
                error=teach_res_dict.get("error")
            )
            if not teach_success:
                return self._failed_msg(teach_res_dict.get("error", "Teaching agent failed."), start_time)

            teaching_explanation = teach_res_dict.get("data", {}).get("explanation", "")

            # 6. FACT VERIFICATION & RETRY
            run_verification = rag_required and len(retrieved_chunks) > 0
            
            v_data = {}
            status = "Supported"
            verified_explanation = teaching_explanation
            unsupported_claims = []

            if run_verification:
                step_start = time.time()
                verify_msg = UserMsg(
                    name="Supervisor", 
                    content=teaching_explanation, 
                    metadata={
                        "session_id": session_id,
                        "retrieved_chunks": retrieved_chunks
                    }
                )
                verify_reply = await self.verification_agent.reply(verify_msg)
                verify_res_dict = getattr(verify_reply, "metadata", {}).get("agent_result", {})
                verify_success = verify_res_dict.get("success", False)
                
                self.session_manager.save_execution_state(
                    session_id=session_id, agent="FactVerificationAgent",
                    status="success" if verify_success else "failed",
                    execution_time=time.time() - step_start,
                    error=verify_res_dict.get("error")
                )
                
                v_data = verify_res_dict.get("data", {}) if verify_success else {}
                status = v_data.get("status", "Supported")
                verified_explanation = v_data.get("verified_answer", teaching_explanation)
                unsupported_claims = v_data.get("unsupported_claims", [])

                if status != "Supported" or unsupported_claims:
                    logger.info("Fact verification failed. Retrying explanation with strictly grounded prompts...")
                    step_start = time.time()
                    retry_grounded_query = f"Question: {query}\n\nOnly use the following verified source text, do not add any fact not present in it:\n{context_str}"
                    teach_msg = UserMsg(name="Supervisor", content=retry_grounded_query, metadata=pipeline_metadata)
                    teach_reply = await self.teaching_agent.reply(teach_msg)
                    teach_res_dict = getattr(teach_reply, "metadata", {}).get("agent_result", {})
                    teach_success = teach_res_dict.get("success", False)
                    
                    self.session_manager.save_execution_state(
                        session_id=session_id, agent="TeachingAgent_Retry",
                        status="success" if teach_success else "failed",
                        execution_time=time.time() - step_start,
                        error=teach_res_dict.get("error")
                    )
                    if teach_success:
                        teaching_explanation = teach_res_dict.get("data", {}).get("explanation", "")
                        
                        step_start = time.time()
                        verify_msg = UserMsg(
                            name="Supervisor", 
                            content=teaching_explanation, 
                            metadata={
                                "session_id": session_id,
                                "retrieved_chunks": retrieved_chunks
                            }
                        )
                        verify_reply = await self.verification_agent.reply(verify_msg)
                        verify_res_dict = getattr(verify_reply, "metadata", {}).get("agent_result", {})
                        verify_success = verify_res_dict.get("success", False)
                        
                        self.session_manager.save_execution_state(
                            session_id=session_id, agent="FactVerificationAgent_Retry",
                            status="success" if verify_success else "failed",
                            execution_time=time.time() - step_start,
                            error=verify_res_dict.get("error")
                        )
                        
                        if verify_success:
                            v_data = verify_res_dict.get("data", {})
                            status = v_data.get("status", "Supported")
                            unsupported_claims = v_data.get("unsupported_claims", [])
                            
                            if status != "Supported" or unsupported_claims:
                                logger.warning(f"Fact verification still failed after retry. Stripping {len(unsupported_claims)} unsupported sentences.")
                                verified_explanation = v_data.get("verified_answer", teaching_explanation)
                                import re
                                total_sentences = len([s.strip() for s in re.split(r'(?<=[.!?])\s+', teaching_explanation) if s.strip()])
                                verified_sentences = len([s.strip() for s in re.split(r'(?<=[.!?])\s+', verified_explanation) if s.strip()])
                                ratio = verified_sentences / total_sentences if total_sentences else 1.0
                                final_confidence = final_confidence * ratio
                            else:
                                verified_explanation = teaching_explanation
                        else:
                            verified_explanation = teaching_explanation
                    else:
                        verified_explanation = teaching_explanation

            # 7. SAFETY CHECK (RESPONSE-SIDE)
            step_start = time.time()
            safety_msg = UserMsg(name="Supervisor", content=verified_explanation, metadata=pipeline_metadata)
            safety_reply = await self.safety_agent.reply(safety_msg)
            safety_res_dict = getattr(safety_reply, "metadata", {}).get("agent_result", {})
            safety_success = safety_res_dict.get("success", False)
            
            self.session_manager.save_execution_state(
                session_id=session_id, agent="SafetyAgent_Response",
                status="success" if safety_success else "failed",
                execution_time=time.time() - step_start,
                error=safety_res_dict.get("error")
            )
            flagged_status = not safety_success
            if flagged_status:
                logger.warning(f"Unsafe response content flagged: {safety_res_dict.get('error')}. Refusing response.")
                await self.interaction_repo.log_interaction(
                    session_id=session_id,
                    student_query=query,
                    rewritten_query=planner_data.get("rewritten_query", query) if planner_data else query,
                    retrieved_chunk_ids=[c.get("chunk_id") for c in retrieved_chunks],
                    final_answer="Response rejected due to safety violations.",
                    confidence_score=0.0,
                    flagged=True
                )
                return self._failed_msg("I'm sorry, but I cannot provide that information as it may violate classroom safety guidelines.", start_time, flagged=True)

            # 8. RESPONSE STRUCTURING & API PAYLOAD
            step_start = time.time()
            citations = v_data.get("citations", [])
            warnings = v_data.get("warnings")
            
            response_content = verified_explanation
            if warnings:
                response_content = f"{warnings}\n\n{response_content}"
            if citations:
                response_content = f"{response_content}\n\nCitations:\n" + "\n".join([f"- {c}" for c in citations])

            response_msg = UserMsg(name="Supervisor", content=response_content, metadata=pipeline_metadata)
            response_reply = await self.response_agent.reply(response_msg)
            response_res_dict = getattr(response_reply, "metadata", {}).get("agent_result", {})
            response_success = response_res_dict.get("success", False)
            
            self.session_manager.save_execution_state(
                session_id=session_id, agent="ResponseAgent",
                status="success" if response_success else "failed",
                execution_time=time.time() - step_start,
                error=response_res_dict.get("error")
            )
            if not response_success:
                return self._failed_msg(response_res_dict.get("error", "Response structuring failed."), start_time)

            final_data = response_res_dict.get("data", {})

            citations_payload = []
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
                citations_payload.append({
                    "source_file": source_file,
                    "page_number": int(chunk.get("page_number", 1)),
                    "chapter": str(chunk.get("chapter", "1")),
                    "content": chunk.get("chunk_text") or chunk.get("text", "")
                })

            response_payload = {
                "answer": final_data.get("answer", ""),
                "citations": citations_payload,
                "confidence_score": float(final_confidence),
                "flagged": flagged_status,
                "session_id": session_id
            }

            retrieved_chunk_ids = [c.get("chunk_id") for c in retrieved_chunks]
            await self.interaction_repo.log_interaction(
                session_id=session_id,
                student_query=query,
                rewritten_query=planner_data.get("rewritten_query", query) if planner_data else query,
                retrieved_chunk_ids=retrieved_chunk_ids,
                final_answer=response_payload["answer"],
                confidence_score=final_confidence,
                flagged=flagged_status
            )
            
            duration = time.time() - start_time
            self.session_manager.save_message(
                session_id=session_id,
                sender="Supervisor",
                content=response_payload["answer"]
            )
            
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
            duration = time.time() - start_time
            logger.error(f"Supervisor V2 exception: {e}")
            return self._failed_msg(f"Supervisor system error: {str(e)}", start_time)
        finally:
            self.session_manager.release_lock(lock_name)

    def _failed_msg(self, error: str, start_time: float, flagged: bool = False) -> AssistantMsg:
        duration = time.time() - start_time
        result = AgentResult(
            success=False,
            data={
                "answer": error,
                "citations": [],
                "confidence_score": 0.0,
                "flagged": flagged,
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
