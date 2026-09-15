import pytest
import os
import numpy as np
from unittest.mock import MagicMock, patch, AsyncMock
from agentscope.message import Msg, UserMsg

import models.compat
from agents.validatorAgent import ValidationAgent
from ai_teacher_robot.rag.schemas.retrieval_result import RetrievalResult
from ai_teacher_robot.rag.retrieval.hybrid_search import HybridSearch
from ai_teacher_robot.agents.verification.fact_verification_agent import FactVerificationAgent
from agents.supervisorAgentV2 import ClassroomSupervisorAgentV2

@pytest.fixture(autouse=True)
def setup_mock_env():
    os.environ["MONGO_URI"] = "mongodb://mock-host:9999"
    os.environ["REDIS_HOST"] = "mock-host"
    os.environ["GROQ_API_KEY"] = "mock-key"
    yield

@pytest.mark.anyio
async def test_validation_agent_length_check():
    agent = ValidationAgent(name="ValAgent")
    
    # 1. Short query check
    msg = Msg(name="Student", content="hi", metadata={"session_id": "test_sess"})
    reply = await agent.reply(msg)
    res = reply.metadata["agent_result"]
    assert res["success"] is False
    assert "at least 3 characters" in res["error"]

    # 2. Empty query check
    msg = Msg(name="Student", content="   ", metadata={"session_id": "test_sess"})
    reply = await agent.reply(msg)
    res = reply.metadata["agent_result"]
    assert res["success"] is False
    assert "empty or missing" in res["error"]

@pytest.mark.anyio
async def test_hybrid_search_rrf():
    # Instantiate HybridSearch
    hs = HybridSearch()
    
    # Mock search results for semantic and bm25
    chunk1 = RetrievalResult(chunk_id="c1", document_id="d1", chunk_text="NCERT Math Chapter 1 Shapes.", page_number=2, chapter="1", topic="Shapes", score=0.9, metadata={})
    chunk2 = RetrievalResult(chunk_id="c2", document_id="d1", chunk_text="NCERT Math Chapter 1 Space.", page_number=3, chapter="1", topic="Space", score=0.85, metadata={})
    
    # Case A: c1 is rank 1 in semantic, rank 2 in bm25. c2 is rank 2 in semantic, rank 1 in bm25
    hs.semantic_search.search = AsyncMock(return_value=[chunk1, chunk2])
    hs.bm25_search.search = AsyncMock(return_value=[chunk2, chunk1])
    
    merged = await hs.search(query="shapes", vector=[0.1]*384, limit=2)
    assert len(merged) == 2
    
    # Check that scores are merged using RRF formula: 1 / (60 + rank_sem) + 1 / (60 + rank_bm25)
    # c1 score: 1/(60+1) + 1/(60+2) = 1/61 + 1/62
    # c2 score: 1/(60+2) + 1/(60+1) = 1/62 + 1/61
    expected_score = 1.0/61.0 + 1.0/62.0
    assert abs(merged[0].score - expected_score) < 1e-6
    assert abs(merged[1].score - expected_score) < 1e-6

@pytest.mark.anyio
@patch("ai_teacher_robot.rag.embedding.embedding_generator.EmbeddingGenerator.generate_embeddings")
async def test_fact_verification_agent_programmatic(mock_embs):
    # Mock embeddings such that sentence 1 matches chunk 1 (similarity > 0.6), but sentence 2 does not.
    # Sentence 1: "Shapes are round." -> vector [1, 0]
    # Sentence 2: "Planets are far." -> vector [0, 1]
    # Chunk 1: "Shapes are round structures." -> vector [0.99, 0.1]
    # Similarity S1-C1 = 0.99, Similarity S2-C1 = 0.1
    mock_embs.side_effect = lambda texts: [
        [1.0, 0.0] if "round" in t else [0.0, 1.0]
        for t in texts
    ] if len(texts) > 1 else [[0.99, 0.1]]
    
    agent = FactVerificationAgent(name="VerifyAgent")
    
    msg = Msg(
        name="Supervisor",
        content="Shapes are round. Planets are far.",
        metadata={
            "session_id": "test_verify_sess",
            "retrieved_chunks": [
                {"chunk_text": "Shapes are round structures.", "chapter": "1", "page_number": 2, "chunk_id": "c1"}
            ]
        }
    )
    
    reply = await agent.reply(msg)
    res = reply.metadata["agent_result"]
    
    assert res["success"] is True
    assert res["data"]["status"] == "Unsupported"
    assert len(res["data"]["unsupported_claims"]) == 1
    assert "Planets are far." in res["data"]["unsupported_claims"]
    assert "Planets are far." not in res["data"]["verified_answer"]
    assert "Shapes are round." in res["data"]["verified_answer"]

@pytest.mark.anyio
@patch("agents.validatorAgent.LLMGateway")
@patch("agents.safetyAgent.LLMGateway")
@patch("ai_teacher_robot.agents.retrieval.retrieval_planner_agent.LLMGateway")
@patch("agents.supervisorAgentV2.CurriculumRAGAgent.reply")
@patch("agents.teachingAgent.LLMGateway")
@patch("ai_teacher_robot.agents.verification.fact_verification_agent.LLMGateway")
@patch("agents.responseAgent.LLMGateway")
async def test_supervisor_v2_auth_and_subject(
    mock_resp_gw,
    mock_verify_gw,
    mock_teach_gw,
    mock_rag_reply_method,
    mock_plan_gw,
    mock_safety_gw,
    mock_val_gw
):
    mock_val_gw.return_value.generate = AsyncMock(return_value='{"valid": true}')
    mock_safety_gw.return_value.generate = AsyncMock(return_value='{"safe": true}')
    
    planner_json = '{"rag_required": true, "subject": "Science", "class": "10", "board": "NCERT", "chapter": "1", "search_strategy": "hybrid"}'
    mock_plan_gw.return_value.generate = AsyncMock(return_value=planner_json)
    
    teaching_json = "Grounded soil science explanation."
    mock_teach_gw.return_value.generate = AsyncMock(return_value=teaching_json)
    
    response_json = '{"answer": "Final response about soil.", "summary": "", "key_points": [], "teaching_mode": "", "diagram_required": false, "video_required": false, "quiz_generated": false, "confidence_score": 0.9}'
    mock_resp_gw.return_value.generate = AsyncMock(return_value=response_json)

    captured_planner_data = []
    async def mock_reply(msg):
        captured_planner_data.append(msg.metadata.get("planner_result", {}))
        return Msg(
            name="CurriculumRAGAgent",
            content="",
            metadata={
                "agent_result": {
                    "success": True,
                    "data": {
                        "chunks": [
                            {
                                "chunk_id": "c1",
                                "document_id": "d1",
                                "chunk_text": "Grounded soil science explanation.",
                                "page_number": 1,
                                "chapter": "1",
                                "score": 0.8,
                                "metadata": {}
                            }
                        ]
                    }
                }
            }
        )
    mock_rag_reply_method.side_effect = mock_reply

    supervisor = ClassroomSupervisorAgentV2(name="SupervisorV2")

    # Case 1: Authenticated for Grade 5, no explicit subject (should fallback to semantic Science)
    msg1 = Msg(
        name="Student",
        content="Tell me about soil.",
        metadata={"session_id": "sess_1", "grade": 5}
    )
    await supervisor.reply(msg1)
    
    assert len(captured_planner_data) == 1
    assert captured_planner_data[0]["class"] == "5"
    assert captured_planner_data[0]["subject"] == "Science"

    # Case 2: Authenticated for Grade 5, with explicit subject override "Geography"
    captured_planner_data.clear()
    msg2 = Msg(
        name="Student",
        content="Tell me about soil.",
        metadata={"session_id": "sess_2", "grade": 5, "subject": "Geography"}
    )
    await supervisor.reply(msg2)
    
    assert len(captured_planner_data) == 1
    assert captured_planner_data[0]["class"] == "5"
    assert captured_planner_data[0]["subject"] == "Geography"

