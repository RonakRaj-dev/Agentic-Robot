"""Comprehensive test script to diagnose why the model cannot answer 'Who is the author of this chapter?'
and test fixes across all system perspectives.
"""

from __future__ import annotations
import asyncio
import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))
load_dotenv()

from agentscope.message import Msg
from agents.supervisor_agent_v3.agents.agent import ClassroomSupervisorAgentV3
from agents.retrieval.curriculum_rag_agent import CurriculumRAGAgent
from agents.verification.citation_generator import CitationGenerator
from ai_teacher_robot.repositories.db_client import db_manager

async def run_author_perspective_test():
    print("=" * 90)
    print("      DIAGNOSTIC TEST: 'Who is the author of this chapter?' PERSPECTIVE ANALYSIS")
    print("=" * 90)

    # 1. DATABASE METADATA PERSPECTIVE
    print("\n--- PERSPECTIVE 1: MONGODB METADATA INSPECTION ---")
    db = await db_manager.get_db()
    book = await db.BOOKS.find_one({"class_no": 7, "subject": "English"})
    print(f"Book found: {book.get('title') if book else 'None'}")
    
    chapter_doc = None
    if book:
        chapter_doc = await db.CHAPTERS.find_one({"book_id": str(book["_id"]), "chapter_no": 3})
        print(f"Chapter 3 doc: {chapter_doc}")

    # 2. RAG RETRIEVAL PERSPECTIVE
    print("\n--- PERSPECTIVE 2: RAG RETRIEVAL TEST ---")
    rag_agent = CurriculumRAGAgent()
    msg = Msg(
        name="Student",
        content="[Chapter: 3] Who is the author of this chapter ?",
        metadata={
            "session_id": "test_sess_author",
            "grade": 7,
            "subject": "English",
            "chapter": "3",
            "planner_result": {
                "class": 7,
                "subject": "English",
                "chapter": 3,
                "search_strategy": "hybrid"
            }
        }
    )
    rag_reply = await rag_agent.reply(msg)
    rag_data = getattr(rag_reply, "metadata", {}).get("agent_result", {}).get("data", {})
    chunks = rag_data.get("chunks", [])
    print(f"Total chunks retrieved: {len(chunks)}")
    for idx, c in enumerate(chunks[:5]):
        txt = c.get("chunk_text") or c.get("raw_text", "")
        print(f"  Chunk #{idx+1} (Page {c.get('page_number')} | Topic: {c.get('topic')}): {txt[:150]}...")

    # 3. CITATION GENERATOR PERSPECTIVE
    print("\n--- PERSPECTIVE 3: CITATION GENERATOR TEST ---")
    cit_gen = CitationGenerator()
    citations = cit_gen.generate_citations(chunks)
    print("Generated Citations:")
    for cit in citations:
        print(f"  • {cit}")

    # 4. END-TO-END SUPERVISOR V3 AGENT PERSPECTIVE
    print("\n--- PERSPECTIVE 4: END-TO-END SUPERVISOR V3 EXECUTION ---")
    sup_agent = ClassroomSupervisorAgentV3()
    user_msg = Msg(
        name="Student",
        content="[Chapter: 3] Who is the author of this chapter ?",
        metadata={
            "session_id": "test_sess_author_e2e",
            "grade": 7,
            "subject": "English",
            "chapter": "3",
            "student_id": "test_student",
            "intent": "conceptual_query"
        }
    )
    e2e_reply = await sup_agent.reply(user_msg)
    e2e_data = getattr(e2e_reply, "metadata", {}).get("agent_result", {}).get("data", {})
    print("\nFinal Model Answer Output:")
    print(json.dumps(e2e_data, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    asyncio.run(run_author_perspective_test())
