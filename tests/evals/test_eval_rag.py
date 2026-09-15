import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from agents.retrieval.curriculum_rag_agent import CurriculumRAGAgent

@pytest.mark.asyncio
async def test_eval_rag_retrieval_grounding():
    """Evaluates RAG retrieval relevance, score calculation, and context grounding."""
    mock_search_results = [
        {"chunk_text": "Photosynthesis is the process by which green plants use sunlight to synthesize nutrients from carbon dioxide and water.", "chapter": "1", "page_number": 5, "score": 0.92, "topic": "Photosynthesis"},
        {"chunk_text": "Chlorophyll absorbs light energy during photosynthesis in plant leaves.", "chapter": "1", "page_number": 6, "score": 0.88, "topic": "Chlorophyll"}
    ]
    
    with patch("agents.retrieval.curriculum_rag_agent.RetrievalPipeline"):
        rag_agent = CurriculumRAGAgent(name="EvalRAGAgent")
        with patch.object(rag_agent.retrieval_pipeline, "retrieve", new=AsyncMock(return_value=mock_search_results)), \
             patch.object(rag_agent, "_generate_dual_queries", new=AsyncMock(return_value=("How do plants make food?", "plants food"))):
            msg = await rag_agent.reply({
                "content": "How do plants make food?",
                "metadata": {"session_id": "eval_rag_sess", "planner_result": {"class": "6", "subject": "Science"}}
            })
            
            agent_result = msg.metadata.get("agent_result", {})
            assert agent_result.get("success") is True, "CurriculumRAGAgent query failed"
            
            chunks = agent_result.get("data", {}).get("chunks", [])
            assert len(chunks) == 2, f"Expected 2 chunks, got {len(chunks)}"
            assert chunks[0]["score"] >= 0.8, f"Top chunk score too low: {chunks[0]['score']}"
            assert "Photosynthesis" in chunks[0]["chunk_text"], "Top chunk text missing expected keyword"
