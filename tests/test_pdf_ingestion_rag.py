import pytest
from pathlib import Path
from ai_teacher_robot.rag.chunking.curriculum_chunker import CurriculumChunker
from storage_service.services.pymupdf.pymupdf_service import PyMuPDFService
from agents.retrieval.reranker import Reranker


def test_structure_aware_chunker():
    chunker = CurriculumChunker(max_chunk_tokens=100, overlap_tokens=20)
    
    sample_md = """# Chapter 1: Laws of Motion

## Section 1.1: Newton's First Law
Every object persists in its state of rest or uniform motion unless acted upon by an external force.

| Concept | Formula | Unit |
| --- | --- | --- |
| Force | F = m * a | Newton (N) |

## Section 1.2: Momentum
Mass in motion is defined as momentum. p = m * v.
"""

    metadata = {
        "book_title": "Class 9 Physics",
        "class_no": 9,
        "subject": "Physics",
        "chapter_no": 1,
        "chapter_name": "Laws of Motion",
        "board": "NCERT"
    }

    chunks = chunker.chunk_markdown(sample_md, metadata=metadata)
    assert len(chunks) >= 2
    
    # Verify Context Header prepended
    first_chunk = chunks[0]
    assert "[Context: Book: Class 9 Physics | Class: 9 | Subject: Physics | Chapter 1: Laws of Motion" in first_chunk["chunk_text"]
    assert "Section 1.1: Newton's First Law" in first_chunk["chunk_text"]
    assert "| Concept | Formula | Unit |" in first_chunk["chunk_text"]


@pytest.mark.asyncio
async def test_reranker_candidates_capping():
    reranker = Reranker(max_candidates=3)
    query = "What is force?"
    
    candidates = [
        {"chunk_id": f"c_{i}", "chunk_text": f"Force is mass times acceleration sample {i}", "score": 0.5}
        for i in range(10)
    ]
    
    res = await reranker.rerank_async(query, candidates)
    assert len(res) == 10
    assert "combined_score" in res[0]
