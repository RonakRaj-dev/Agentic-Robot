import pytest
import os
import shutil
from unittest.mock import MagicMock, patch, AsyncMock
from bson import ObjectId
from agentscope.message import Msg, AssistantMsg, TextBlock

import models.compat
from ai_teacher_robot.rag.schemas.document import CurriculumDocument
from ai_teacher_robot.rag.schemas.chunk import CurriculumChunk
from ai_teacher_robot.rag.ingestion.pdf_loader import PDFLoader
from ai_teacher_robot.rag.ingestion.text_cleaner import TextCleaner
from ai_teacher_robot.rag.chunking.recursive_chunker import RecursiveChunker
from ai_teacher_robot.rag.embedding.embedding_generator import EmbeddingGenerator
from ai_teacher_robot.rag.vector_store.qdrant_store import QdrantStore
from ai_teacher_robot.repositories.curriculum_repository import CurriculumRepository
from ai_teacher_robot.pipelines.curriculum_ingestion_pipeline import CurriculumIngestionPipeline
from agents.supervisorAgentV2 import ClassroomSupervisorAgentV2

@pytest.fixture(autouse=True)
def setup_mock_env():
    os.environ["MONGO_URI"] = "mongodb://mock-host:9999"
    os.environ["REDIS_HOST"] = "mock-host"
    os.environ["GROQ_API_KEY"] = "mock-key"
    yield
    # Cleanup
    if os.path.exists("state/embedding_cache.db"):
        try:
            os.remove("state/embedding_cache.db")
        except Exception:
            pass

def test_text_cleaner():
    cleaner = TextCleaner()
    raw_text = "This is a clean- \ntext with page number \n12\nand double  spaces."
    cleaned = cleaner.clean_text(raw_text)
    assert "12" not in cleaned
    assert "double spaces" in cleaned
    assert "cleantext" in cleaned

def test_recursive_chunker():
    chunker = RecursiveChunker(chunk_size=50, chunk_overlap=10)
    text = "The quick brown fox jumps over the lazy dog. A quick test for recursive splits."
    chunks = chunker.split_text(text)
    assert len(chunks) > 1
    assert all(len(c) <= 50 for c in chunks)

def test_embedding_generator_and_cache():
    generator = EmbeddingGenerator()
    vector = generator.generate_embedding("Hello education world")
    assert len(vector) == 384
    assert isinstance(vector[0], float)

def test_qdrant_store_fallback():
    store = QdrantStore()
    chunk = {
        "chunk_id": "chunk_001",
        "document_id": "doc_001",
        "chunk_text": "NCERT Mathematics Chapter 1 Shapes",
        "page_number": 5,
        "chapter": "1",
        "topic": "Shapes"
    }
    vec = [0.1] * 384
    
    # Store
    ids = store.add_chunks([chunk], [vec])
    assert len(ids) == 1
    
    # Query search
    query_vec = [0.1] * 384
    res = store.search(query_vec, limit=1)
    assert len(res) == 1
    assert res[0].chunk_text == "NCERT Mathematics Chapter 1 Shapes"

@pytest.mark.anyio
async def test_curriculum_repository():
    repo = CurriculumRepository()
    doc = CurriculumDocument(
        title="Chapter 1 Shapes",
        subject="Mathematics",
        class_level="1",
        board="NCERT",
        chapter="1",
        uploaded_by="Teacher"
    )
    doc_id = await repo.insert_document(doc)
    assert doc_id is not None
    
    fetched = await repo.get_document(doc_id)
    assert fetched is not None
    assert fetched.title == "Chapter 1 Shapes"

@pytest.mark.anyio
@patch('ai_teacher_robot.rag.ingestion.pdf_loader.PDFLoader.load_pdf')
@patch('models.llm_gateway.LLMGateway.generate')
async def test_ingestion_pipeline(mock_llm, mock_load):
    # Mock PDF loading
    mock_load.return_value = [
        {"page_number": 1, "plain_text": "NCERT Math Class 1 Chapter 1 Shapes and Space."}
    ]
    # Mock LLM metadata response
    mock_llm.return_value = '{"title": "Shapes and Space", "subject": "Mathematics", "class": "1", "board": "NCERT", "chapter": "1", "difficulty": "Easy"}'
    
    pipeline = CurriculumIngestionPipeline()
    doc_id = await pipeline.ingest_pdf("Math_1/aejm101.pdf")
    
    assert doc_id is not None
    
    # Verify DB contains chunks
    chunks = await pipeline.chunk_repo.get_chunks_for_document(doc_id)
    assert len(chunks) > 0
    assert "Shapes and Space" in chunks[0].chunk_text

@pytest.mark.anyio
@patch("agents.validatorAgent.LLMGateway")
@patch("agents.safetyAgent.LLMGateway")
@patch("ai_teacher_robot.agents.retrieval.retrieval_planner_agent.LLMGateway")
@patch("agents.supervisorAgentV2.CurriculumRAGAgent.reply")
@patch("agents.teachingAgent.LLMGateway")
@patch("ai_teacher_robot.agents.verification.fact_verification_agent.LLMGateway")
@patch("agents.responseAgent.LLMGateway")
async def test_supervisor_v2_loop(
    mock_resp_gw,
    mock_verify_gw,
    mock_teach_gw,
    mock_rag_reply_method,
    mock_plan_gw,
    mock_safety_gw,
    mock_val_gw
):
    # Mock LLM calls for each agent individually
    mock_val_gw.return_value.generate = AsyncMock(return_value='{"valid": true, "reason": ""}')
    mock_safety_gw.return_value.generate = AsyncMock(return_value='{"safe": true, "reason": ""}')
    
    planner_json = '{"rag_required": true, "subject": "Mathematics", "class": "1", "board": "NCERT", "chapter": "1", "search_strategy": "hybrid"}'
    mock_plan_gw.return_value.generate = AsyncMock(return_value=planner_json)
    
    # Mock RAG agent reply returning a valid chunk with score >= 0.35
    mock_rag_reply = Msg(
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
                            "chunk_text": "This is a fun shape breakdown explanation.",
                            "page_number": 5,
                            "chapter": "1",
                            "score": 0.8,
                            "metadata": {}
                        }
                    ]
                }
            }
        }
    )
    mock_rag_reply_method.return_value = mock_rag_reply
    
    teaching_json = "This is a fun shape breakdown explanation."
    mock_teach_gw.return_value.generate = AsyncMock(return_value=teaching_json)
    
    verification_json = '{"status": "Supported", "reason": "Factually correct", "confidence_percentage": 95, "corrected_answer": null, "warnings": null}'
    mock_verify_gw.return_value.generate = AsyncMock(return_value=verification_json)
    
    response_json = '{"answer": "Here is your explanation about shapes.", "summary": "Shapes summary.", "key_points": ["Circle", "Triangle"], "teaching_mode": "visual", "diagram_required": false, "video_required": false, "quiz_generated": false, "confidence_score": 0.95}'
    mock_resp_gw.return_value.generate = AsyncMock(return_value=response_json)

    supervisor = ClassroomSupervisorAgentV2(name="ClassroomSupervisorAgentV2")
    user_msg = Msg(
        name="Student",
        content="Tell me about shapes.",
        metadata={"session_id": "test_sess_v2"}
    )
    
    reply = await supervisor.reply(user_msg)
    agent_res = reply.metadata["agent_result"]
    
    assert agent_res["success"] is True
    assert "shapes" in agent_res["data"]["answer"].lower()
