from typing import List, Dict, Any, Optional
from loguru import logger
from ai_teacher_robot.rag.embedding.embedding_generator import EmbeddingGenerator
from ai_teacher_robot.rag.retrieval.hybrid_search import HybridSearch
from ai_teacher_robot.rag.retrieval.reranking import Reranking
from ai_teacher_robot.rag.schemas.retrieval_result import RetrievalResult


class RetrievalPipeline:
    """Dual Query Hybrid Retrieval Pipeline coordinating embedding generation, Qdrant dense vector search, MongoDB BM25 sparse search, and BAAI cross-encoder reranker."""

    def __init__(self) -> None:
        self.embedding_generator = EmbeddingGenerator()
        self.hybrid_search = HybridSearch(
            collection_name="curriculum_embeddings",
            dimension=self.embedding_generator.get_dimension()
        )
        self.reranking = Reranking()

    async def retrieve(
        self,
        query: str,
        bm25_query: Optional[str] = None,
        strategy: str = "hybrid",
        limit: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        original_query: Optional[str] = None
    ) -> List[RetrievalResult]:
        semantic_q = query
        sparse_q = bm25_query or query
        logger.info(f"Starting dual retrieval: semantic='{semantic_q[:40]}...', bm25='{sparse_q[:40]}...'")

        # 1. Generate dense query vector from semantic_query
        query_vector = await self.embedding_generator.generate_embedding_async(semantic_q)

        # 2. Dual Search
        if strategy == "semantic":
            raw_results = await self.hybrid_search.semantic_search.search(
                vector=query_vector,
                limit=limit * 2,
                filters=filters
            )
        elif strategy == "bm25":
            raw_results = await self.hybrid_search.bm25_search.search(
                query=sparse_q,
                limit=limit * 2,
                filters=filters
            )
        else:
            raw_results = await self.hybrid_search.search(
                vector=query_vector,
                bm25_query=sparse_q,
                limit=15,
                filters=filters
            )

        # 3. Fast BAAI Cross-Encoder Rerank
        rerank_q = original_query or semantic_q
        reranked_results = await self.reranking.rerank_async(rerank_q, raw_results)

        final_results = reranked_results[:limit]
        logger.info(f"Retrieval complete. Retained top-{len(final_results)} chunks.")
        return final_results
