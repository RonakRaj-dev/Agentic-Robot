from typing import List
from ai_teacher_robot.rag.schemas.retrieval_result import RetrievalResult
from ai_teacher_robot.agents.retrieval.context_builder import ContextBuilder as AgentContextBuilder

class ContextBuilder:
    """Combines RetrievalResult items into a formatted text context for the Teach system."""
    def __init__(self) -> None:
        self.builder = AgentContextBuilder()

    def build_context(self, results: List[RetrievalResult]) -> str:
        chunks = []
        for r in results:
            chunks.append({
                "chunk_text": r.chunk_text,
                "page_number": r.page_number,
                "chapter": r.chapter,
                "topic": r.topic
            })
        return self.builder.build_context(chunks)
