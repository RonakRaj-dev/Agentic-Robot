from typing import List
from ai_teacher_robot.rag.schemas.retrieval_result import RetrievalResult
from agents.retrieval.reranker import Reranker

class Reranking:
    """Wrapper component to rerank raw search retrieval outputs for RAG pipelines."""
    def __init__(self) -> None:
        self.reranker = Reranker()

    def rerank(self, query: str, results: List[RetrievalResult]) -> List[RetrievalResult]:
        # Convert RetrievalResults to dicts for Reranker
        chunks_dict = []
        for r in results:
            chunks_dict.append({
                "chunk_id": r.chunk_id,
                "document_id": r.document_id,
                "chunk_text": r.chunk_text,
                "page_number": r.page_number,
                "chapter": r.chapter,
                "topic": r.topic,
                "score": r.score,
                "metadata": r.metadata
            })
            
        reranked_dicts = self.reranker.rerank(query, chunks_dict)
        
        # Map back to RetrievalResult
        final_results = []
        for d in reranked_dicts:
            final_results.append(
                RetrievalResult(
                    chunk_id=d["chunk_id"],
                    document_id=d["document_id"],
                    chunk_text=d["chunk_text"],
                    page_number=d["page_number"],
                    chapter=d["chapter"],
                    topic=d["topic"],
                    score=d.get("combined_score", d["score"]),
                    metadata=d["metadata"]
                )
            )
        return final_results

    async def rerank_async(self, query: str, results: List[RetrievalResult]) -> List[RetrievalResult]:
        chunks_dict = []
        for r in results:
            chunks_dict.append({
                "chunk_id": r.chunk_id,
                "document_id": r.document_id,
                "chunk_text": r.chunk_text,
                "page_number": r.page_number,
                "chapter": r.chapter,
                "topic": r.topic,
                "score": r.score,
                "metadata": r.metadata
            })
            
        reranked_dicts = await self.reranker.rerank_async(query, chunks_dict)
        
        final_results = []
        for d in reranked_dicts:
            final_results.append(
                RetrievalResult(
                    chunk_id=d["chunk_id"],
                    document_id=d["document_id"],
                    chunk_text=d["chunk_text"],
                    page_number=d["page_number"],
                    chapter=d["chapter"],
                    topic=d["topic"],
                    score=d.get("combined_score", d["score"]),
                    metadata=d["metadata"]
                )
            )
        return final_results
