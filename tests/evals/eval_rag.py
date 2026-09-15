import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from agents.retrieval.rag_agent import RAGAgent

@pytest.mark.asyncio
async def test_eval_rag_retrieval_grounding():
    """Evaluates RAG retrieval relevance, score calculation, and context grounding."""
    rag_agent = RAGAgent(name="EvalRAGAgent")
    
    mock_search_results = [
        {"chunk_text": "Photosynthesis is the process by which green plants use sunlight to synthesize nutrients from carbon dioxide and water.", "chapter": "1", "page_number": 5, "score": 0.92, "topic": "Photosynthesis"},
        {"chunk_text": "Chlorophyll absorbs light energy during photosynthesis in plant leaves.", "chapter": "1", "page_number": 6, "score": 0.88, "topic": "Chlorophyll"}
    ]
    
    with patch.object(rag_agent.vector_store, "search", new=AsyncMock(return_value=mock_search_results)):
        msg = await rag_agent.reply({
            "content": "How do plants make food?",
            "metadata": {"session_id": "eval_rag_sess", "planner_result": {"class": "6", "subject": "Science"}}
        })
        
        agent_result = msg.metadata.get("agent_result", {})
        assert agent_result.get("success") is True, "RAGAgent query failed"
        
        chunks = agent_result.get("data", {}).get("chunks", [])
        assert len(chunks) == 2, f"Expected 2 chunks, got {len(chunks)}"
        assert chunks[0]["score"] >= 0.8, f"Top chunk score too low: {chunks[0]['score']}"
        assert "Photosynthesis" in chunks[0]["chunk_text"], "Top chunk text missing expected keyword"
