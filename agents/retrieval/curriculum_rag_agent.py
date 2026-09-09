import time
import json
import re
from typing import Dict, Any, List, Tuple
import models.compat
from loguru import logger
from agentscope.agent import Agent
from agentscope.message import Msg
from models.llm_gateway import LLMGateway
from state.agentState import AgentStateManager
from models.schemas import AgentResult, get_content_str
from pipelines.retrieval_pipeline import RetrievalPipeline
from ai_teacher_robot.utils.text_cleaner import strain_text


class CurriculumRAGAgent(Agent):
    """CurriculumRAGAgent: Executes Dual Query Expansion, invokes hybrid retrieval pipeline, 
    deduplicates chunks, filters by threshold, and attaches curriculum metadata.
    """

    def __init__(self, name: str = "CurriculumRAGAgent", **kwargs: Any) -> None:
        super().__init__()
        self.name = name
        self.state_manager = AgentStateManager()
        self.gateway = LLMGateway()
        self.retrieval_pipeline = RetrievalPipeline()
        from ai_teacher_robot.repositories.config_repository import ConfigRepository
        self.config_repo = ConfigRepository()

    async def reply(self, x: dict = None) -> dict:
        start_time = time.time()
        query = get_content_str(x)

        metadata = {}
        if isinstance(x, dict):
            metadata = x.get("metadata", {})
        elif hasattr(x, "metadata"):
            metadata = getattr(x, "metadata", {}) or {}

        session_id = metadata.get("session_id", "default_sess")
        planner_data = metadata.get("planner_result", {})

        if not query.strip():
            execution_time = time.time() - start_time
            result = AgentResult(
                success=False,
                data=None,
                error="Input query to RAG is empty.",
                execution_time=execution_time
            )
            return Msg(
                name=self.name,
                content=result.model_dump_json(),
                metadata={"agent_result": result.model_dump()}
            )

        try:
            # 1. Dual Query Expansion Strategy
            semantic_q, bm25_q = await self._generate_dual_queries(query)
            logger.info(f"Dual Query Expansion | Original: '{query}' | Semantic: '{semantic_q}' | BM25: '{bm25_q}'")

            # 2. Build Stage 1 (Strict) Filters
            strategy = planner_data.get("search_strategy", "hybrid")
            filter_dict = {}
            if planner_data.get("subject"):
                filter_dict["subject"] = planner_data["subject"]
            if planner_data.get("class"):
                filter_dict["class"] = str(planner_data["class"])
            
            # Only restrict chapter if query explicitly mentions a chapter number
            if planner_data.get("chapter") and re.search(r'\b(?:chapter|ch\.?)\s*\d+\b', query, re.IGNORECASE):
                filter_dict["chapter"] = str(planner_data["chapter"])

            if planner_data.get("board"):
                filter_dict["board"] = planner_data["board"]

            logger.info(f"Stage 1 Strict Retrieval | Filters: {filter_dict}")
            raw_results = await self.retrieval_pipeline.retrieve(
                query=semantic_q,
                bm25_query=bm25_q,
                strategy=strategy,
                limit=5,
                filters=filter_dict,
                original_query=query
            )

            # Stage 2 (Cross-Grade / Cross-Chapter Adaptive Fallback)
            # If Stage 1 produced zero or low-relevance results (< 0.45 score), expand search across all grade curriculum
            def _get_max_score(res_list):
                if not res_list: return 0.0
                return max([r.get("score", 0.0) if isinstance(r, dict) else getattr(r, "score", 0.0) for r in res_list])

            stage1_top_score = _get_max_score(raw_results)
            if stage1_top_score < 0.45:
                logger.warning(f"Stage 1 top score ({stage1_top_score:.2f}) < 0.45. Triggering Stage 2 Cross-Grade Expansion...")
                relaxed_filters = {}
                if planner_data.get("subject"):
                    relaxed_filters["subject"] = planner_data["subject"]
                
                stage2_results = await self.retrieval_pipeline.retrieve(
                    query=semantic_q,
                    bm25_query=bm25_q,
                    strategy=strategy,
                    limit=5,
                    filters=relaxed_filters,
                    original_query=query
                )
                if _get_max_score(stage2_results) > stage1_top_score:
                    logger.info("Stage 2 Cross-Grade Expansion retrieved higher relevance chunks!")
                    raw_results = stage2_results

            # 3. Deduplication and confidence threshold check (min_score = 0.40)
            unique_chunks = self._deduplicate_and_filter(raw_results, min_score=0.40)

            # 4. Format outputs & preserve metadata fields
            retrieved_data = []
            def _g(obj, k, d=""):
                if isinstance(obj, dict):
                    val = obj.get(k) or obj.get("metadata", {}).get(k)
                    return str(val) if val is not None and str(val).strip() else str(d)
                meta = getattr(obj, "metadata", {}) or {}
                val = meta.get(k) if isinstance(meta, dict) else None
                if val is None or val == "":
                    val = getattr(obj, k, None)
                return str(val) if val is not None and str(val).strip() else str(d)

            ch_cls = planner_data.get("class") or 7
            ch_subj = planner_data.get("subject") or "English"
            ch_num = planner_data.get("chapter") or 3

            for item in unique_chunks:
                retrieved_data.append({
                    "chunk_id": _g(item, "chunk_id", ""),
                    "document_id": _g(item, "document_id", ""),
                    "class": _g(item, "class", _g(item, "class_no", str(ch_cls))),
                    "subject": _g(item, "subject", ch_subj),
                    "chapter": _g(item, "chapter", str(ch_num)),
                    "board": _g(item, "board", "NCERT"),
                    "chunk_text": strain_text(_g(item, "chunk_text", "")),
                    "page_number": int(_g(item, "page_number", 1) or 1),
                    "topic": _g(item, "topic", "General"),
                    "score": float(_g(item, "score", 0.0) or 0.0),
                    "metadata": _g(item, "metadata", {})
                })

            from ai_teacher_robot.repositories.chapter_metadata import get_chapter_metadata_info
            meta_info = get_chapter_metadata_info(ch_cls, ch_subj, ch_num)
            if meta_info:
                meta_chunk = {
                    "chunk_id": "chapter_metadata_header",
                    "document_id": "meta_header",
                    "class": str(ch_cls),
                    "subject": str(ch_subj),
                    "chapter": str(ch_num),
                    "board": "NCERT",
                    "page_number": 1,
                    "topic": "Chapter Overview & Author Info",
                    "chunk_text": f"[Chapter Overview | Book: Class {ch_cls} {ch_subj} (NCERT) | Chapter {ch_num}: {meta_info.get('title')} | Author: {meta_info.get('author')}]\nChapter Title: {meta_info.get('title')}\nAuthor: {meta_info.get('author')}\nGenre/Type: {meta_info.get('type')}",
                    "score": 1.0,
                    "metadata": meta_info
                }
                retrieved_data.insert(0, meta_chunk)

            execution_time = time.time() - start_time
            result = AgentResult(
                success=True,
                data={
                    "semantic_query": semantic_q,
                    "bm25_query": bm25_q,
                    "chunks": retrieved_data
                },
                execution_time=execution_time
            )

            logger.info(f"RAG agent retrieved {len(retrieved_data)} chunks.")
            return Msg(
                name=self.name,
                content=result.model_dump_json(),
                metadata={"agent_result": result.model_dump()}
            )

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Exception in CurriculumRAGAgent: {e}")
            result = AgentResult(
                success=False,
                data=None,
                error=f"RAG system exception: {str(e)}",
                execution_time=execution_time
            )
            return Msg(
                name=self.name,
                content=result.model_dump_json(),
                metadata={"agent_result": result.model_dump()}
            )

    async def _generate_dual_queries(self, query: str) -> Tuple[str, str]:
        """Generates dual query representations for Vector (semantic) and BM25 (keyword) searches."""
        prompt = f"""
Analyze the following educational query and output a JSON object with two fields:
1. "semantic_query": A expanded natural language phrasing retaining conceptual prepositions, scientific definitions, and full context for dense vector similarity.
2. "bm25_query": A space-separated list of exact keywords, terms, and textbook synonyms for sparse BM25 text index matching.

Query: "{query}"

Respond strictly with a JSON object:
{{"semantic_query": "...", "bm25_query": "..."}}
"""
        try:
            model_config = self.state_manager.get_model_config("CurriculumRAGAgent")
            model_config_copy = dict(model_config)
            model_config_copy["temperature"] = 0.0
            model_config_copy["response_format"] = {"type": "json_object"}

            raw = await self.gateway.generate(prompt, **model_config_copy)
            cleaned = raw.strip()
            cleaned = re.sub(r'<think>.*?</think>', '', cleaned, flags=re.DOTALL).strip()
            if "```" in cleaned:
                cleaned = re.sub(r'```(?:json)?\s*', '', cleaned)
                cleaned = cleaned.replace("```", "").strip()
            json_match = re.search(r'\{.*\}', cleaned, flags=re.DOTALL)
            if json_match:
                cleaned = json_match.group(0)

            parsed = json.loads(cleaned)
            semantic_q = parsed.get("semantic_query") or query
            bm25_q = parsed.get("bm25_query") or query
            return semantic_q, bm25_q
        except Exception as e:
            logger.warning(f"Dual query generation exception: {e}. Falling back to raw query.")
            return query, query

    def _deduplicate_and_filter(self, results: List[Any], min_score: float = 0.40) -> List[Any]:
        seen_texts = set()
        unique = []
        for item in results:
            txt_val = item.get("chunk_text", "") if isinstance(item, dict) else getattr(item, "chunk_text", "")
            score_val = item.get("score", 0.0) if isinstance(item, dict) else getattr(item, "score", 0.0)
            txt = str(txt_val).strip().lower()
            if txt in seen_texts:
                continue
            if score_val < min_score:
                continue
            seen_texts.add(txt)
            unique.append(item)
        return unique
